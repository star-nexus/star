"""Scale Test Harness for orthogonal large-world workload experiments.

This module is intentionally outside the normal agent/Hub path. When explicitly
mounted, it exposes a tiny Unix Domain Socket control plane while all workload
execution stays on the ENV main thread. Commands prepare movement plans and start
prepared batches without WebSocket, observations, LLMs, or worker-thread ECS
mutation.
"""

from __future__ import annotations

import json
import math
import os
import random
import socket
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from framework import System
from framework.ecs import profiling

from ..components import HexPosition, MovementAnimation, Unit, UnitCount
from ..systems.movement_planning import (
    MovePlan,
    MovementPlanningPolicy,
)
from ..utils.hex_utils import HexMath
from ..utils.map_query import board_hexes, impassable_terrain

Hex = Tuple[int, int]
SUSTAINED_PHASES = {"synchronized", "staggered"}


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    lo = int(rank)
    hi = min(len(ordered) - 1, lo + 1)
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


@dataclass
class PreparedMoveBatch:
    batch_id: int
    seed: int
    density: float
    target_radius: int
    policy: MovementPlanningPolicy
    correct_unreachable: bool
    living_units_at_prepare: int
    requested_units: int
    requested_targets: Dict[int, Hex]
    plans: List[MovePlan]
    failures: Counter = field(default_factory=Counter)
    target_generation_ms: float = 0.0
    planning_snapshot_ms: float = 0.0
    batch_planning_ms: float = 0.0
    plan_samples_ms: List[float] = field(default_factory=list)

    @property
    def corrected_units(self) -> int:
        return sum(1 for plan in self.plans if plan.corrected)

    @property
    def budget_corrected_units(self) -> int:
        return sum(1 for plan in self.plans if plan.correction_reason == "budget")

    @property
    def unreachable_corrected_units(self) -> int:
        return sum(1 for plan in self.plans if plan.correction_reason == "unreachable")

    def summary(self) -> Dict[str, Any]:
        samples = self.plan_samples_ms
        prepared = len(self.plans)
        return {
            "batch_id": self.batch_id,
            "seed": self.seed,
            "density": self.density,
            "target_radius": self.target_radius,
            "policy": self.policy.value,
            "correct_unreachable": self.correct_unreachable,
            "living_units_at_prepare": self.living_units_at_prepare,
            "requested_units": self.requested_units,
            "prepared_units": prepared,
            "preparation_success_ratio": (
                prepared / self.requested_units if self.requested_units else 0.0
            ),
            "prepared_world_density": (
                prepared / self.living_units_at_prepare
                if self.living_units_at_prepare
                else 0.0
            ),
            "corrected_units": self.corrected_units,
            "budget_corrected_units": self.budget_corrected_units,
            "unreachable_corrected_units": self.unreachable_corrected_units,
            "failed_units": self.requested_units - prepared,
            "failure_reasons": dict(self.failures),
            "target_generation_ms": round(self.target_generation_ms, 3),
            "planning_snapshot_ms": round(self.planning_snapshot_ms, 3),
            "batch_planning_ms": round(self.batch_planning_ms, 3),
            "plan_p50_ms": round(_percentile(samples, 0.50), 4),
            "plan_p95_ms": round(_percentile(samples, 0.95), 4),
            "plan_p99_ms": round(_percentile(samples, 0.99), 4),
        }


class ScaleHarnessSystem(System):
    """Main-thread UDS control plane for dynamic-world scale tests."""

    def __init__(self, movement_system, socket_path: str):
        # After GameTime (10), before AnimationSystem (15): a start command can
        # activate all prepared animations before that frame's animation update.
        super().__init__(priority=12)
        self.movement_system = movement_system
        self.socket_path = os.path.abspath(os.path.expanduser(socket_path))
        self.server: Optional[socket.socket] = None
        self.clients: Dict[socket.socket, bytearray] = {}
        self.prepared: Optional[PreparedMoveBatch] = None
        self._next_batch_id = 1
        self._sustained_entities: set[int] = set()
        self._sustained_batch_id: Optional[int] = None
        self._sustained_duration_seconds: float = 0.0
        self._sustained_phase: Optional[str] = None
        self._sustained_phase_seed: Optional[int] = None

    def initialize(self, world) -> None:
        self.world = world
        directory = os.path.dirname(self.socket_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.setblocking(False)
        server.bind(self.socket_path)
        server.listen(4)
        self.server = server
        profiling.profiler.set_metadata(
            scale_harness=True,
            scale_harness_socket=self.socket_path,
        )
        print(f"[ScaleHarness] UDS ready: {self.socket_path}")

    def subscribe_events(self):
        pass

    def cleanup(self) -> None:
        self._stop_sustained_motion()
        for client in list(self.clients):
            try:
                client.close()
            except OSError:
                pass
        self.clients.clear()
        if self.server is not None:
            try:
                self.server.close()
            except OSError:
                pass
            self.server = None
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass

    def update(self, delta_time: float) -> None:
        self._accept_clients()
        self._read_commands()
        profiling.profiler.set_frame_metric(
            "scale_prepared_units", len(self.prepared.plans) if self.prepared else 0
        )

    # ------------------------------------------------------------------
    # UDS control plane
    # ------------------------------------------------------------------
    def _accept_clients(self) -> None:
        if self.server is None:
            return
        for _ in range(4):
            try:
                client, _ = self.server.accept()
            except BlockingIOError:
                break
            client.setblocking(False)
            self.clients[client] = bytearray()

    def _read_commands(self) -> None:
        for client in list(self.clients):
            try:
                chunk = client.recv(65536)
            except BlockingIOError:
                continue
            except OSError:
                self._drop_client(client)
                continue

            if not chunk:
                self._drop_client(client)
                continue
            buffer = self.clients.get(client)
            if buffer is None:
                continue
            buffer.extend(chunk)

            while b"\n" in buffer:
                raw, _, rest = buffer.partition(b"\n")
                self.clients[client] = bytearray(rest)
                buffer = self.clients[client]
                if not raw.strip():
                    continue
                response = self._dispatch_raw(raw)
                self._send_response(client, response)

    def _dispatch_raw(self, raw: bytes) -> Dict[str, Any]:
        try:
            command = json.loads(raw.decode("utf-8"))
            if not isinstance(command, dict):
                raise ValueError("command must be a JSON object")
            return self.handle_command(command)
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__, "message": str(exc)}

    def _send_response(self, client: socket.socket, response: Dict[str, Any]) -> None:
        payload = (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            client.sendall(payload)
        except (BlockingIOError, BrokenPipeError, OSError):
            self._drop_client(client)

    def _drop_client(self, client: socket.socket) -> None:
        self.clients.pop(client, None)
        try:
            client.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Public command surface
    # ------------------------------------------------------------------
    def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "prepare_random_moves":
            return self._prepare_random_moves(command)
        if op == "start_prepared_batch":
            return self._start_prepared_batch(command)
        if op == "start_sustained_batch":
            return self._start_sustained_batch(command)
        if op == "stop_sustained":
            stopped = self._stop_sustained_motion()
            return {"ok": True, "stopped_units": stopped}
        if op == "status":
            return {"ok": True, **self._status()}
        if op == "clear":
            stopped = self._stop_sustained_motion()
            self.prepared = None
            return {"ok": True, "cleared": True, "stopped_units": stopped}
        return {"ok": False, "error": "unknown_command", "command": op}

    # ------------------------------------------------------------------
    # Phase 1/2: target generation + planning/correction
    # ------------------------------------------------------------------
    def _prepare_random_moves(self, command: Dict[str, Any]) -> Dict[str, Any]:
        density = max(0.0, min(1.0, float(command.get("density", 1.0))))
        seed = int(command.get("seed", 42))
        target_radius = max(1, int(command.get("target_radius", 12)))
        correct_unreachable = bool(command.get("correct_unreachable", True))
        policy = MovementPlanningPolicy.coerce(
            command.get("policy", MovementPlanningPolicy.STRESS_STACK_ENDPOINT.value)
        )

        living = self._living_units()
        requested_count = min(len(living), int(round(len(living) * density)))
        rng = random.Random(seed)
        selected = (
            rng.sample(living, requested_count)
            if requested_count < len(living)
            else list(living)
        )
        selected.sort()

        # Phase 1 deliberately uses only static board geometry. Dynamic occupancy
        # is captured later in one PlanningSnapshot so target generation and
        # planning costs stay separately attributable.
        with profiling.profiler.time_system(
            "scale_target_generation", category="scale_planning"
        ):
            t0 = time.perf_counter_ns()
            targets = self._generate_targets(selected, rng, target_radius)
            target_generation_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        with profiling.profiler.time_system(
            "scale_planning_snapshot", category="scale_planning"
        ):
            t0 = time.perf_counter_ns()
            snapshot = self.movement_system.build_planning_snapshot()
            planning_snapshot_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        plans: List[MovePlan] = []
        failures: Counter = Counter()
        plan_samples_ms: List[float] = []
        with profiling.profiler.time_system(
            "scale_batch_planning", category="scale_planning"
        ):
            batch_t0 = time.perf_counter_ns()
            for entity in selected:
                target = targets.get(entity)
                if target is None:
                    failures["no_target_candidate"] += 1
                    continue
                one_t0 = time.perf_counter_ns()
                result = self.movement_system.plan_move(
                    entity,
                    target,
                    policy=policy,
                    snapshot=snapshot,
                    correct_to_budget=True,
                    correct_unreachable=correct_unreachable,
                )
                plan_samples_ms.append(
                    (time.perf_counter_ns() - one_t0) / 1_000_000.0
                )
                if result.success and result.plan is not None:
                    plans.append(result.plan)
                else:
                    failures[result.response.get("reason", "unknown")] += 1
            batch_planning_ms = (
                time.perf_counter_ns() - batch_t0
            ) / 1_000_000.0

        batch = PreparedMoveBatch(
            batch_id=self._next_batch_id,
            seed=seed,
            density=density,
            target_radius=target_radius,
            policy=policy,
            correct_unreachable=correct_unreachable,
            living_units_at_prepare=len(living),
            requested_units=requested_count,
            requested_targets=targets,
            plans=plans,
            failures=failures,
            target_generation_ms=target_generation_ms,
            planning_snapshot_ms=planning_snapshot_ms,
            batch_planning_ms=batch_planning_ms,
            plan_samples_ms=plan_samples_ms,
        )
        self._next_batch_id += 1
        self.prepared = batch
        summary = batch.summary()
        profiling.profiler.set_metadata(
            scale_last_batch=batch.batch_id,
            scale_requested_units=batch.requested_units,
            scale_prepared_units=len(batch.plans),
            scale_budget_corrected_units=batch.budget_corrected_units,
            scale_unreachable_corrected_units=batch.unreachable_corrected_units,
            scale_target_generation_ms=summary["target_generation_ms"],
            scale_planning_snapshot_ms=summary["planning_snapshot_ms"],
            scale_batch_planning_ms=summary["batch_planning_ms"],
            scale_plan_p95_ms=summary["plan_p95_ms"],
            scale_plan_p99_ms=summary["plan_p99_ms"],
        )
        profiling.profiler.set_frame_metric("scale_requested_units", batch.requested_units)
        profiling.profiler.set_frame_metric("scale_prepared_units", len(batch.plans))
        profiling.profiler.set_frame_metric("scale_corrected_units", batch.corrected_units)
        profiling.profiler.set_frame_metric(
            "scale_unreachable_corrected_units", batch.unreachable_corrected_units
        )
        return {"ok": True, "phase": "prepared", **summary}

    def _generate_targets(
        self, entities: List[int], rng: random.Random, radius: int
    ) -> Dict[int, Hex]:
        board = board_hexes(self.world)
        impassable = set(impassable_terrain(self.world))
        targets: Dict[int, Hex] = {}
        for entity in entities:
            pos = self.world.get_component(entity, HexPosition)
            if pos is None:
                continue
            current = (pos.col, pos.row)
            candidates = [
                cell
                for cell in HexMath.hex_in_range(pos.col, pos.row, radius)
                if cell != current
                and cell not in impassable
                and (board is None or cell in board)
            ]
            if candidates:
                targets[entity] = rng.choice(candidates)
        return targets

    # ------------------------------------------------------------------
    # Phase 3A: normal one-shot execute, including normal move side effects
    # ------------------------------------------------------------------
    def _start_prepared_batch(self, command: Dict[str, Any]) -> Dict[str, Any]:
        batch = self.prepared
        if batch is None:
            return {"ok": False, "error": "no_prepared_batch"}
        requested_batch_id = command.get("batch_id")
        if requested_batch_id is not None and int(requested_batch_id) != batch.batch_id:
            return {
                "ok": False,
                "error": "batch_id_mismatch",
                "prepared_batch_id": batch.batch_id,
            }

        self._stop_sustained_motion()
        accepted = 0
        rejected: Counter = Counter()
        with profiling.profiler.time_system(
            "scale_batch_execute", category="scale_execution"
        ):
            t0 = time.perf_counter_ns()
            for plan in batch.plans:
                result = self.movement_system.execute_move_plan(plan, emit_log=False)
                if result.get("success"):
                    accepted += 1
                else:
                    rejected[result.get("reason", "unknown")] += 1
            execute_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        with profiling.profiler.time_system(
            "scale_active_moving_count", category="scale_execution"
        ):
            active = self._active_moving_units()

        living_now = len(self._living_units())
        actual_world_density = active / living_now if living_now else 0.0
        activation_ratio = active / batch.requested_units if batch.requested_units else 0.0
        profiling.profiler.set_metadata(
            scale_execution_mode="one_shot",
            scale_last_execute_batch=batch.batch_id,
            scale_batch_execute_ms=round(execute_ms, 3),
            scale_execute_accepted=accepted,
            scale_active_moving_units=active,
            scale_actual_density=round(actual_world_density, 4),
        )
        profiling.profiler.set_frame_metric("scale_execute_accepted", accepted)
        profiling.profiler.set_frame_metric("scale_active_moving_units", active)
        profiling.profiler.set_frame_metric(
            "scale_actual_density", round(actual_world_density, 4)
        )
        return {
            "ok": True,
            "phase": "started",
            "execution_mode": "one_shot",
            "batch_id": batch.batch_id,
            "prepared_units": len(batch.plans),
            "accepted_units": accepted,
            "rejected_units": len(batch.plans) - accepted,
            "rejection_reasons": dict(rejected),
            "living_units": living_now,
            "active_moving_units": active,
            "actual_density": actual_world_density,
            "activation_ratio": activation_ratio,
            "batch_execute_ms": round(execute_ms, 3),
            "normal_move_side_effects": True,
        }

    # ------------------------------------------------------------------
    # Phase 3B: sustained pure-motion workload, no pathfinding/resources/stats
    # ------------------------------------------------------------------
    def _start_sustained_batch(self, command: Dict[str, Any]) -> Dict[str, Any]:
        batch = self.prepared
        if batch is None:
            return {"ok": False, "error": "no_prepared_batch"}
        requested_batch_id = command.get("batch_id")
        if requested_batch_id is not None and int(requested_batch_id) != batch.batch_id:
            return {
                "ok": False,
                "error": "batch_id_mismatch",
                "prepared_batch_id": batch.batch_id,
            }

        duration_seconds = max(0.5, float(command.get("duration_seconds", 20.0)))
        phase = str(command.get("phase", "synchronized")).strip().lower()
        if phase not in SUSTAINED_PHASES:
            return {
                "ok": False,
                "error": "invalid_phase",
                "phase": phase,
                "allowed": sorted(SUSTAINED_PHASES),
            }
        phase_seed = int(command.get("phase_seed", batch.seed))
        phase_rng = random.Random(phase_seed)

        self._stop_sustained_motion()
        accepted = 0
        rejected: Counter = Counter()
        total_motion_segments = 0
        total_animation_segments = 0
        min_motion_segments: Optional[int] = None
        max_motion_segments = 0
        phase_offsets: List[float] = []

        with profiling.profiler.time_system(
            "scale_sustained_start", category="scale_execution"
        ):
            t0 = time.perf_counter_ns()
            for plan in batch.plans:
                sustained_path = self._build_sustained_path(
                    plan.entity, plan.path, duration_seconds
                )
                if sustained_path is None:
                    rejected["invalid_motion_path"] += 1
                    continue

                path_to_start = sustained_path
                initial_progress = 0.0
                if phase == "staggered":
                    # Add a zero-distance hold segment. Varying progress within
                    # that hold shifts only the time phase; speed, route and all
                    # subsequent motion semantics remain identical.
                    path_to_start = (sustained_path[0],) + sustained_path
                    initial_progress = phase_rng.random()

                result = self.movement_system.start_prepared_motion(
                    plan.entity,
                    path_to_start,
                    expected_start=plan.start,
                )
                if result.get("success"):
                    accepted += 1
                    self._sustained_entities.add(plan.entity)
                    motion_segments = len(sustained_path) - 1
                    animation_segments = len(path_to_start) - 1
                    total_motion_segments += motion_segments
                    total_animation_segments += animation_segments
                    min_motion_segments = (
                        motion_segments
                        if min_motion_segments is None
                        else min(min_motion_segments, motion_segments)
                    )
                    max_motion_segments = max(max_motion_segments, motion_segments)

                    if phase == "staggered":
                        anim = self.world.get_component(
                            plan.entity, MovementAnimation
                        )
                        if anim is not None and anim.is_moving:
                            anim.progress = initial_progress
                            phase_offsets.append(initial_progress)
                else:
                    rejected[result.get("reason", "unknown")] += 1
            start_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        self._sustained_batch_id = batch.batch_id
        self._sustained_duration_seconds = duration_seconds
        self._sustained_phase = phase
        self._sustained_phase_seed = phase_seed
        active = self._active_moving_units()
        living_now = len(self._living_units())
        actual_world_density = active / living_now if living_now else 0.0
        activation_ratio = active / batch.requested_units if batch.requested_units else 0.0

        phase_p50 = _percentile(phase_offsets, 0.50)
        phase_p95 = _percentile(phase_offsets, 0.95)

        profiling.profiler.set_metadata(
            scale_execution_mode="sustained",
            scale_sustained_phase=phase,
            scale_sustained_phase_seed=phase_seed,
            scale_sustained_batch=batch.batch_id,
            scale_sustained_duration_seconds=duration_seconds,
            scale_sustained_start_ms=round(start_ms, 3),
            scale_sustained_accepted=accepted,
            scale_sustained_segments_total=total_motion_segments,
            scale_sustained_animation_segments_total=total_animation_segments,
            scale_active_moving_units=active,
            scale_actual_density=round(actual_world_density, 4),
        )
        profiling.profiler.set_frame_metric("scale_sustained_accepted", accepted)
        profiling.profiler.set_frame_metric("scale_sustained_phase", phase)
        profiling.profiler.set_frame_metric("scale_active_moving_units", active)
        profiling.profiler.set_frame_metric(
            "scale_actual_density", round(actual_world_density, 4)
        )
        return {
            "ok": True,
            "phase": "started",
            "execution_mode": "sustained",
            "motion_phase": phase,
            "phase_seed": phase_seed,
            "phase_progress_p50": round(phase_p50, 4),
            "phase_progress_p95": round(phase_p95, 4),
            "batch_id": batch.batch_id,
            "duration_seconds": duration_seconds,
            "prepared_units": len(batch.plans),
            "accepted_units": accepted,
            "rejected_units": len(batch.plans) - accepted,
            "rejection_reasons": dict(rejected),
            "active_moving_units": active,
            "actual_density": actual_world_density,
            "activation_ratio": activation_ratio,
            "sustained_start_ms": round(start_ms, 3),
            "segments_total": total_motion_segments,
            "animation_segments_total": total_animation_segments,
            "segments_min_per_unit": min_motion_segments or 0,
            "segments_max_per_unit": max_motion_segments,
            "pathfinding_during_execution": False,
            "normal_move_side_effects": False,
        }

    def _build_sustained_path(
        self,
        entity: int,
        base_path: Tuple[Hex, ...],
        duration_seconds: float,
    ) -> Optional[Tuple[Hex, ...]]:
        """Expand one short prepared route into a forward/backward motion path.

        The resulting animation is started once. No per-frame harness loop is
        needed: AnimationSystem naturally consumes the long path while committing
        HexPosition/spatial-index changes at each segment.
        """
        route = tuple(base_path)
        if len(route) < 2:
            return None
        anim = self.world.get_component(entity, MovementAnimation)
        speed = float(getattr(anim, "speed", 2.0)) if anim is not None else 2.0
        speed = max(0.01, speed)
        segment_count = max(1, int(math.ceil(duration_seconds * speed)))

        cycle_targets = list(route[1:]) + list(reversed(route[:-1]))
        if not cycle_targets:
            return None
        expanded = [route[0]]
        for index in range(segment_count):
            expanded.append(cycle_targets[index % len(cycle_targets)])
        return tuple(expanded)

    def _stop_sustained_motion(self) -> int:
        stopped = 0
        for entity in list(self._sustained_entities):
            anim = (
                self.world.get_component(entity, MovementAnimation)
                if hasattr(self, "world")
                else None
            )
            if anim is not None and anim.is_moving:
                anim.is_moving = False
                anim.progress = 0.0
                anim.current_target_index = 0
                anim.path.clear()
                stopped += 1
        self._sustained_entities.clear()
        self._sustained_batch_id = None
        self._sustained_duration_seconds = 0.0
        self._sustained_phase = None
        self._sustained_phase_seed = None
        return stopped

    def _living_units(self) -> List[int]:
        living = []
        for entity in self.world.query().with_all(Unit, HexPosition, UnitCount).entities():
            count = self.world.get_component(entity, UnitCount)
            if count is not None and count.current_count > 0:
                living.append(entity)
        return sorted(living)

    def _active_moving_units(self) -> int:
        active = 0
        for entity in self.world.query().with_component(MovementAnimation).entities():
            anim = self.world.get_component(entity, MovementAnimation)
            if anim is not None and anim.is_moving:
                active += 1
        return active

    def _status(self) -> Dict[str, Any]:
        active = self._active_moving_units()
        living = len(self._living_units())
        payload = {
            "socket": self.socket_path,
            "living_units": living,
            "active_moving_units": active,
            "world_density": active / living if living else 0.0,
            "sustained": {
                "batch_id": self._sustained_batch_id,
                "duration_seconds": self._sustained_duration_seconds,
                "phase": self._sustained_phase,
                "phase_seed": self._sustained_phase_seed,
                "configured_units": len(self._sustained_entities),
            },
        }
        if self.prepared is not None:
            payload["prepared"] = self.prepared.summary()
        else:
            payload["prepared"] = None
        return payload
