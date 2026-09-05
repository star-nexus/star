"""Minimal main-thread control plane for STAR system-scale experiments.

The harness is mounted only by the explicit ``--scale-harness-socket`` CLI flag.
It never replaces production simulation/render systems. Route preparation is
outside the measured steady-state epoch; sustained execution is handed to the
normal AnimationSystem, which commits HexPosition through the normal window
MovementSystem and therefore exercises the production spatial/Vision/Fog/render
path.
"""

from __future__ import annotations

import json
import math
import os
import random
import socket
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from framework import System
from framework.ecs import profiling
from framework.utils.realtime_gc_policy import (
    GC_POLICY_AUTO,
    RealtimeGCPolicy,
    normalize_gc_policy,
)

from ..components import HexPosition, MovementAnimation, Unit, UnitCount
from ..utils.hex_utils import HexMath
from ..utils.map_query import board_hexes, impassable_terrain

Hex = Tuple[int, int]
_PHASES = {"synchronized", "staggered"}


@dataclass(frozen=True)
class PreparedRoute:
    entity: int
    path: Tuple[Hex, ...]


@dataclass
class PreparedRoutePool:
    batch_id: int
    seed: int
    route_steps: int
    living_units: int
    requested_units: int
    routes: List[PreparedRoute]
    failures: Counter

    def summary(self) -> Dict[str, Any]:
        prepared = len(self.routes)
        return {
            "batch_id": self.batch_id,
            "seed": self.seed,
            "route_steps": self.route_steps,
            "living_units": self.living_units,
            "requested_units": self.requested_units,
            "prepared_units": prepared,
            "failed_units": self.requested_units - prepared,
            "failure_reasons": dict(self.failures),
            "preparation_success_ratio": (
                prepared / self.requested_units if self.requested_units else 0.0
            ),
        }


class ScaleHarnessSystem(System):
    """Test-only UDS controller; production systems execute the workload."""

    def __init__(self, socket_path: str):
        # Commands are processed before AnimationSystem(priority=15), so a start
        # command can activate paths for the same frame's production update.
        super().__init__(priority=12)
        self.socket_path = os.path.abspath(os.path.expanduser(socket_path))
        self.server: Optional[socket.socket] = None
        self.clients: Dict[socket.socket, bytearray] = {}
        self.animation_system = None
        self.prepared: Optional[PreparedRoutePool] = None
        self._next_batch_id = 1
        self._sustained_entities: set[int] = set()
        self._execution_density = 0.0
        self._phase: Optional[str] = None
        self._gc_policy = RealtimeGCPolicy()

    def initialize(self, world) -> None:
        self.world = world
        self.animation_system = next(
            (
                system
                for system in world.systems
                if system.__class__.__name__ == "AnimationSystem"
                and hasattr(system, "start_unit_movement")
            ),
            None,
        )
        if self.animation_system is None:
            raise RuntimeError("ScaleHarness requires the production AnimationSystem")

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
            scale_harness_version="production-v2",
        )
        print(f"[ScaleHarness] UDS ready: {self.socket_path}")

    def subscribe_events(self):
        pass

    def cleanup(self) -> None:
        self._stop_sustained()
        self._gc_policy.restore("cleanup")
        for client in list(self.clients):
            self._drop_client(client)
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
        # Keep test-control and GC-policy bookkeeping outside the STAR-controlled
        # regression plane. The accepted realtime_defer policy moves cyclic-GC
        # maintenance to the start safe point rather than hiding its cost.
        with profiling.profiler.time_system(
            "scale_harness_control", category="diagnostic"
        ):
            self._gc_policy.tick()
            self._accept_clients()
            self._read_commands()

        profiling.profiler.set_frame_metric(
            "scale_configured_moving_units", len(self._sustained_entities)
        )
        profiling.profiler.set_frame_metric(
            "scale_execution_density", self._execution_density
        )
        if self._phase is not None:
            profiling.profiler.set_frame_metric("scale_motion_phase", self._phase)

        gc_state = self._gc_policy.snapshot()
        profiling.profiler.set_frame_metric("scale_gc_policy", gc_state["mode"])
        profiling.profiler.set_frame_metric(
            "scale_gc_defer_active", 1 if gc_state["active"] else 0
        )
        profiling.profiler.set_frame_metric(
            "scale_gc_automatic_enabled",
            1 if gc_state["automatic_gc_enabled"] else 0,
        )

    # ------------------------------------------------------------------
    # UDS
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
                if raw.strip():
                    self._send_response(client, self._dispatch_raw(raw))

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
    # Commands
    # ------------------------------------------------------------------
    def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "prepare_routes":
            return self._prepare_routes(command)
        if op == "start_sustained":
            return self._start_sustained(command)
        if op == "stop_sustained":
            stopped = self._stop_sustained()
            self._gc_policy.restore("stop_sustained")
            return {
                "ok": True,
                "stopped_units": stopped,
                "gc_policy": self._gc_policy.snapshot(),
            }
        if op == "profile_snapshot":
            return self._profile_snapshot(command)
        if op == "status":
            return {"ok": True, **self._status()}
        if op == "clear":
            stopped = self._stop_sustained()
            self._gc_policy.restore("clear")
            self.prepared = None
            return {
                "ok": True,
                "cleared": True,
                "stopped_units": stopped,
                "gc_policy": self._gc_policy.snapshot(),
            }
        return {"ok": False, "error": "unknown_command", "command": op}

    def _prepare_routes(self, command: Dict[str, Any]) -> Dict[str, Any]:
        density = max(0.0, min(1.0, float(command.get("density", 1.0))))
        seed = int(command.get("seed", 42))
        route_steps = max(1, int(command.get("route_steps", 12)))

        living = self._living_units()
        requested_count = min(len(living), int(round(len(living) * density)))
        rng = random.Random(seed)
        ordered = list(living)
        rng.shuffle(ordered)
        selected = ordered[:requested_count]

        board = board_hexes(self.world)
        impassable = set(impassable_terrain(self.world))
        routes: List[PreparedRoute] = []
        failures: Counter = Counter()
        for entity in selected:
            pos = self.world.get_component(entity, HexPosition)
            if pos is None:
                failures["missing_position"] += 1
                continue
            path = self._static_route(
                (pos.col, pos.row),
                route_steps=route_steps,
                rng=rng,
                board=board,
                impassable=impassable,
            )
            if len(path) < 2:
                failures["no_passable_neighbor"] += 1
                continue
            routes.append(PreparedRoute(entity=entity, path=tuple(path)))

        pool = PreparedRoutePool(
            batch_id=self._next_batch_id,
            seed=seed,
            route_steps=route_steps,
            living_units=len(living),
            requested_units=requested_count,
            routes=routes,
            failures=failures,
        )
        self._next_batch_id += 1
        self.prepared = pool
        summary = pool.summary()
        profiling.profiler.set_metadata(
            scale_route_seed=seed,
            scale_route_steps=route_steps,
            scale_prepared_units=len(routes),
            scale_resident_units=len(living),
        )
        return {"ok": True, "phase": "prepared", **summary}

    @staticmethod
    def _static_route(
        start: Hex,
        *,
        route_steps: int,
        rng: random.Random,
        board,
        impassable: set[Hex],
    ) -> List[Hex]:
        path = [start]
        previous: Optional[Hex] = None
        current = start
        for _ in range(route_steps):
            candidates = sorted(
                cell
                for cell in HexMath.hex_neighbors(*current)
                if cell not in impassable and (board is None or cell in board)
            )
            if previous is not None and len(candidates) > 1:
                non_backtracking = [cell for cell in candidates if cell != previous]
                if non_backtracking:
                    candidates = non_backtracking
            if not candidates:
                break
            nxt = rng.choice(candidates)
            path.append(nxt)
            previous, current = current, nxt
        return path

    def _start_sustained(self, command: Dict[str, Any]) -> Dict[str, Any]:
        pool = self.prepared
        if pool is None:
            return {"ok": False, "error": "no_prepared_routes"}
        requested_batch_id = command.get("batch_id")
        if requested_batch_id is not None and int(requested_batch_id) != pool.batch_id:
            return {
                "ok": False,
                "error": "batch_id_mismatch",
                "prepared_batch_id": pool.batch_id,
            }

        execution_density = max(
            0.0, min(1.0, float(command.get("execution_density", 1.0)))
        )
        duration_seconds = max(0.5, float(command.get("duration_seconds", 20.0)))
        phase = str(command.get("phase", "staggered")).strip().lower()
        if phase not in _PHASES:
            return {
                "ok": False,
                "error": "invalid_phase",
                "phase": phase,
                "allowed": sorted(_PHASES),
            }
        try:
            requested_gc_policy = normalize_gc_policy(
                command.get("gc_policy", GC_POLICY_AUTO)
            )
        except ValueError as exc:
            return {"ok": False, "error": "invalid_gc_policy", "message": str(exc)}

        phase_seed = int(command.get("phase_seed", pool.seed))
        phase_rng = random.Random(phase_seed)

        self._gc_policy.restore("replaced")
        self._stop_sustained()
        requested = int(round(len(pool.routes) * execution_density))
        selected = pool.routes[:requested]
        accepted = 0
        rejected: Counter = Counter()
        phase_offsets: List[float] = []

        for prepared in selected:
            pos = self.world.get_component(prepared.entity, HexPosition)
            if pos is None or (pos.col, pos.row) != prepared.path[0]:
                rejected["start_position_changed"] += 1
                continue
            sustained = self._build_sustained_path(
                prepared.entity, prepared.path, duration_seconds
            )
            if sustained is None:
                rejected["invalid_route"] += 1
                continue

            path_to_start = list(sustained)
            initial_progress = 0.0
            if phase == "staggered":
                # A zero-distance first target shifts phase only; route/speed and
                # subsequent production AnimationSystem semantics stay identical.
                path_to_start = [sustained[0], *sustained]
                initial_progress = phase_rng.random()

            self.animation_system.start_unit_movement(prepared.entity, path_to_start)
            anim = self.world.get_component(prepared.entity, MovementAnimation)
            if anim is None or not anim.is_moving:
                rejected["animation_not_started"] += 1
                continue
            if phase == "staggered":
                anim.progress = initial_progress
                phase_offsets.append(initial_progress)
            self._sustained_entities.add(prepared.entity)
            accepted += 1

        # Historical Realtime-GC case established this exact placement: after
        # kickoff allocation, before the latency-critical window. The full Gen2
        # collection therefore happens at a diagnostic safe point, then automatic
        # cyclic GC is boundedly deferred while ordinary refcounting continues.
        gc_state = self._gc_policy.activate(requested_gc_policy, duration_seconds)

        self._execution_density = execution_density
        self._phase = phase
        resident = pool.living_units
        achieved_density = accepted / resident if resident else 0.0
        profiling.profiler.set_metadata(
            scale_execution_mode="sustained_production_animation",
            scale_execution_density=execution_density,
            scale_accepted_moving_units=accepted,
            scale_achieved_density=round(achieved_density, 6),
            scale_motion_phase=phase,
            scale_phase_seed=phase_seed,
            scale_duration_seconds=duration_seconds,
            scale_gc_policy=requested_gc_policy,
            scale_gc_full_collect_ms=gc_state["full_collect_ms"],
            scale_gc_full_collect_collected=gc_state["full_collect_collected"],
        )
        return {
            "ok": True,
            "phase": "started",
            "batch_id": pool.batch_id,
            "motion_phase": phase,
            "phase_seed": phase_seed,
            "duration_seconds": duration_seconds,
            "execution_density": execution_density,
            "requested_moving_units": requested,
            "accepted_moving_units": accepted,
            "rejected_units": requested - accepted,
            "rejection_reasons": dict(rejected),
            "resident_units": resident,
            "achieved_density": achieved_density,
            "phase_progress_p50": self._percentile(phase_offsets, 0.50),
            "phase_progress_p95": self._percentile(phase_offsets, 0.95),
            "pathfinding_during_execution": False,
            "normal_move_resources_and_stats": False,
            "production_animation_and_commits": True,
            "gc_policy": gc_state,
        }

    def _build_sustained_path(
        self, entity: int, route: Tuple[Hex, ...], duration_seconds: float
    ) -> Optional[Tuple[Hex, ...]]:
        if len(route) < 2:
            return None
        anim = self.world.get_component(entity, MovementAnimation)
        speed = max(0.01, float(getattr(anim, "speed", 2.0))) if anim else 2.0
        segment_count = max(1, int(math.ceil(duration_seconds * speed)))
        cycle_targets = list(route[1:]) + list(reversed(route[:-1]))
        if not cycle_targets:
            return None
        expanded = [route[0]]
        for index in range(segment_count):
            expanded.append(cycle_targets[index % len(cycle_targets)])
        return tuple(expanded)

    def _profile_snapshot(self, command: Dict[str, Any]) -> Dict[str, Any]:
        path = str(command.get("path", "")).strip()
        if not path:
            return {"ok": False, "error": "snapshot_path_required"}
        expanded = os.path.abspath(os.path.expanduser(path))
        profiling.profiler.write_json(expanded)
        return {
            "ok": True,
            "path": expanded,
            "sample_count": len(getattr(profiling.profiler, "frame_times_ns", ())),
        }

    def _stop_sustained(self) -> int:
        stopped = 0
        for entity in list(self._sustained_entities):
            anim = self.world.get_component(entity, MovementAnimation)
            if anim is not None and anim.is_moving:
                anim.is_moving = False
                anim.progress = 0.0
                anim.current_target_index = 0
                anim.path.clear()
                stopped += 1
        self._sustained_entities.clear()
        self._execution_density = 0.0
        self._phase = None
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
        living = len(self._living_units())
        active = self._active_moving_units()
        return {
            "socket": self.socket_path,
            "living_units": living,
            "active_moving_units": active,
            "actual_density": active / living if living else 0.0,
            "configured_moving_units": len(self._sustained_entities),
            "execution_density": self._execution_density,
            "motion_phase": self._phase,
            "prepared": self.prepared.summary() if self.prepared else None,
            "gc_policy": self._gc_policy.snapshot(),
        }

    @staticmethod
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
        return round(ordered[lo] * (1.0 - frac) + ordered[hi] * frac, 4)
