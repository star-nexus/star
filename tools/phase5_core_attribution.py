#!/usr/bin/env python3
"""Phase-5.1 attribution launcher for STAR's 10K Core Runtime.

This tool intentionally does not optimize production code. It mounts temporary,
measurement-only probes around the current production Animation / Movement /
Vision paths, then delegates to ``rotk_env.main.main()``.

The probes are source-guarded against the exact production files used for the
Phase-5 baseline. If one of those files changes, the launcher refuses to run
unless ``STAR_PHASE5_ATTR_ALLOW_SOURCE_DRIFT=1`` is explicitly set.

Sampling is used for per-entity micro-timings so attribution does not introduce
10K nested profiler context managers into the hot loop. Exact per-frame sections
still use the Phase-3 hierarchical profiler.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.ecs import profiling as ecs_profiling


EXPECTED_BLOBS = {
    "rotk_env/systems/animation_system.py": "5eebde4603adcef119adb529cb69df679a364c3c",
    "rotk_env/systems/vision_system.py": "6e9190ceb209e257e8f3f10bebe6eb571b8415b4",
    "rotk_env/systems/window_movement_system.py": "9dce77603b42c588357fffa0438246f7f6e62117",
    "rotk_env/systems/movement_system.py": "c46820e8bcd35acb4245a7ac57d893093d4803d0",
}

_SAMPLE_EVERY_ENV = "STAR_PHASE5_ATTR_SAMPLE_EVERY"
_ALLOW_DRIFT_ENV = "STAR_PHASE5_ATTR_ALLOW_SOURCE_DRIFT"
_DEFAULT_SAMPLE_EVERY = 16


@dataclass
class _SampleAccumulator:
    """Low-overhead sampled wall-clock accumulator for one repeated operation."""

    every: int
    calls: int = 0
    sampled_calls: int = 0
    sampled_ns: int = 0

    def should_sample(self) -> bool:
        self.calls += 1
        return (self.calls - 1) % self.every == 0

    def add_sample(self, started_ns: int) -> None:
        self.sampled_calls += 1
        self.sampled_ns += max(0, time.perf_counter_ns() - started_ns)

    def call(self, fn: Callable, *args, **kwargs):
        if not self.should_sample():
            return fn(*args, **kwargs)
        started = time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            self.add_sample(started)

    @property
    def sample_avg_us(self) -> float:
        if not self.sampled_calls:
            return 0.0
        return self.sampled_ns / self.sampled_calls / 1_000.0

    @property
    def estimated_ms(self) -> float:
        if not self.sampled_calls:
            return 0.0
        mean_ns = self.sampled_ns / self.sampled_calls
        return mean_ns * self.calls / 1_000_000.0


_ACTIVE_ANIMATION_SAMPLES: Optional[Dict[str, _SampleAccumulator]] = None


def _sample_every() -> int:
    raw = os.environ.get(_SAMPLE_EVERY_ENV, str(_DEFAULT_SAMPLE_EVERY))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{_SAMPLE_EVERY_ENV} must be an integer >= 1") from exc
    if value < 1:
        raise ValueError(f"{_SAMPLE_EVERY_ENV} must be >= 1")
    return value


def _publish_sample(prefix: str, acc: _SampleAccumulator) -> None:
    metric = ecs_profiling.profiler.set_frame_metric
    metric(f"{prefix}_calls", acc.calls)
    metric(f"{prefix}_sampled_calls", acc.sampled_calls)
    metric(f"{prefix}_sample_avg_us", acc.sample_avg_us)
    metric(f"{prefix}_estimated_ms", acc.estimated_ms)


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=_REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _verify_source_contract() -> None:
    drift = []
    for path, expected in EXPECTED_BLOBS.items():
        if not (_REPO_ROOT / path).is_file():
            drift.append(f"{path}: missing")
            continue
        actual = _git_blob(path)
        if actual != expected:
            drift.append(f"{path}: expected {expected}, got {actual}")

    if not drift:
        return

    if os.environ.get(_ALLOW_DRIFT_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        print("[Phase5 attribution] WARNING: source drift override enabled")
        for item in drift:
            print(f"  - {item}")
        return

    details = "\n".join(f"  - {item}" for item in drift)
    raise RuntimeError(
        "Phase-5 attribution source guard failed. The probes were written for "
        "the exact Phase-5 baseline production files:\n"
        f"{details}\n"
        f"Set {_ALLOW_DRIFT_ENV}=1 only after manually reviewing probe parity."
    )


def _install_animation_probes(sample_every: int) -> None:
    from rotk_env.systems import animation_system as animation_mod
    from rotk_env.systems import movement_system as base_movement_mod
    from rotk_env.systems import window_movement_system as window_movement_mod

    original_base_commit = base_movement_mod.MovementSystem.commit_hex_position
    original_mark_vision_dirty = window_movement_mod.mark_vision_dirty
    original_update_spatial_index = window_movement_mod.update_unit_spatial_index

    def _sampled_hot_call(key: str, fn: Callable, *args, **kwargs):
        samples = _ACTIVE_ANIMATION_SAMPLES
        acc = samples.get(key) if samples is not None else None
        if acc is None:
            return fn(*args, **kwargs)
        return acc.call(fn, *args, **kwargs)

    def profiled_base_commit(self, entity, col, row, *, arrived=False):
        return _sampled_hot_call(
            "base_commit",
            original_base_commit,
            self,
            entity,
            col,
            row,
            arrived=arrived,
        )

    def profiled_mark_vision_dirty(world, entity):
        return _sampled_hot_call(
            "mark_vision_dirty",
            original_mark_vision_dirty,
            world,
            entity,
        )

    def profiled_update_spatial_index(world, entity):
        return _sampled_hot_call(
            "update_spatial_index",
            original_update_spatial_index,
            world,
            entity,
        )

    base_movement_mod.MovementSystem.commit_hex_position = profiled_base_commit
    window_movement_mod.mark_vision_dirty = profiled_mark_vision_dirty
    window_movement_mod.update_unit_spatial_index = profiled_update_spatial_index

    def attributed_movement_update(self, delta_time: float):
        global _ACTIVE_ANIMATION_SAMPLES

        profiler = ecs_profiling.profiler
        with profiler.time_system("animation_movement_update", category="update"):
            with profiler.time_system("animation_movement_query", category="update"):
                entities = (
                    self.world.query()
                    .with_all(animation_mod.HexPosition, animation_mod.MovementAnimation)
                    .entities()
                )

            samples = {
                "component_fetch": _SampleAccumulator(sample_every),
                "movement_system_lookup": _SampleAccumulator(sample_every),
                "segment_setup": _SampleAccumulator(sample_every),
                "base_commit": _SampleAccumulator(sample_every),
                "mark_vision_dirty": _SampleAccumulator(sample_every),
                "update_spatial_index": _SampleAccumulator(sample_every),
            }
            _ACTIVE_ANIMATION_SAMPLES = samples

            moving_entities = 0
            position_commits = 0
            completed_movements = 0

            try:
                with profiler.time_system("animation_movement_loop", category="update"):
                    for entity in entities:
                        fetch = samples["component_fetch"]
                        if fetch.should_sample():
                            started = time.perf_counter_ns()
                            pos = self.world.get_component(entity, animation_mod.HexPosition)
                            anim = self.world.get_component(
                                entity, animation_mod.MovementAnimation
                            )
                            fetch.add_sample(started)
                        else:
                            pos = self.world.get_component(entity, animation_mod.HexPosition)
                            anim = self.world.get_component(
                                entity, animation_mod.MovementAnimation
                            )

                        if not pos or not anim or not anim.is_moving:
                            continue

                        moving_entities += 1

                        if not anim.path or anim.current_target_index >= len(anim.path):
                            anim.is_moving = False
                            anim.progress = 0.0
                            anim.current_target_index = 0
                            anim.path.clear()
                            completed_movements += 1
                            continue

                        anim.progress += anim.speed * delta_time
                        lookup = samples["movement_system_lookup"]
                        movement_system = lookup.call(self._get_movement_system)

                        while (
                            anim.is_moving
                            and anim.current_target_index < len(anim.path)
                            and anim.progress
                            >= 1.0 - animation_mod._MOVEMENT_PROGRESS_EPSILON
                        ):
                            target_hex = anim.path[anim.current_target_index]
                            arrived = anim.current_target_index + 1 >= len(anim.path)
                            if movement_system:
                                movement_system.commit_hex_position(
                                    entity,
                                    target_hex[0],
                                    target_hex[1],
                                    arrived=arrived,
                                )
                            else:
                                pos.col, pos.row = target_hex

                            position_commits += 1
                            anim.current_target_index += 1
                            anim.progress = max(0.0, anim.progress - 1.0)

                            if anim.current_target_index >= len(anim.path):
                                anim.is_moving = False
                                anim.progress = 0.0
                                completed_movements += 1
                            else:
                                samples["segment_setup"].call(
                                    self._setup_movement_segment, anim, pos
                                )
            finally:
                _ACTIVE_ANIMATION_SAMPLES = None

            metric = profiler.set_frame_metric
            metric("phase5_attr_animation_entities_queried", len(entities))
            metric("phase5_attr_animation_moving_entities", moving_entities)
            metric("phase5_attr_animation_position_commits", position_commits)
            metric("phase5_attr_animation_completed_movements", completed_movements)

            _publish_sample(
                "phase5_attr_animation_component_fetch",
                samples["component_fetch"],
            )
            _publish_sample(
                "phase5_attr_animation_movement_system_lookup",
                samples["movement_system_lookup"],
            )
            _publish_sample(
                "phase5_attr_animation_segment_setup",
                samples["segment_setup"],
            )
            _publish_sample(
                "phase5_attr_movement_base_commit",
                samples["base_commit"],
            )
            _publish_sample(
                "phase5_attr_movement_mark_vision_dirty",
                samples["mark_vision_dirty"],
            )
            _publish_sample(
                "phase5_attr_movement_spatial_index_update",
                samples["update_spatial_index"],
            )

    animation_mod.AnimationSystem._update_movement_animations = attributed_movement_update

    def _wrap_once(method_name: str, section_name: str):
        original = getattr(animation_mod.AnimationSystem, method_name)

        def wrapped(self, *args, **kwargs):
            with ecs_profiling.profiler.time_system(section_name, category="update"):
                return original(self, *args, **kwargs)

        setattr(animation_mod.AnimationSystem, method_name, wrapped)

    _wrap_once("_update_attack_animations", "animation_attack_update")
    _wrap_once("_update_projectile_animations", "animation_projectile_update")
    _wrap_once("_update_effect_animations", "animation_effect_update")
    _wrap_once("_update_damage_numbers", "animation_damage_update")


def _install_vision_probe(sample_every: int) -> None:
    from rotk_env.systems import vision_system as vision_mod

    def attributed_vision_update(self, delta_time: float) -> None:
        del delta_time

        profiler = ecs_profiling.profiler
        self._frames += 1
        self._frame_fog_delta = {}

        with profiler.time_system("vision_prepare", category="vision"):
            fog = self._ensure_fog()
            fog_toggled = (
                self._last_fog_enabled is not None
                and self._last_fog_enabled != bool(fog.enabled)
            )
            self._last_fog_enabled = bool(fog.enabled)
            profiler.set_frame_metric("fog_enabled", int(bool(fog.enabled)))
            profiler.set_frame_metric("fog_toggle_this_frame", int(fog_toggled))

        audit_scanned = 0
        if not self._bootstrapped:
            with profiler.time_system("vision_audit_scan", category="vision"):
                audit_scanned = self._audit_all_units(force_all=True)
            self._bootstrapped = True
        else:
            audit_interval = (
                self._AUDIT_EVERY_FRAMES
                if vision_mod.get_unit_spatial_index(self.world) is not None
                else 1
            )
            if self._frames % audit_interval == 0:
                with profiler.time_system("vision_audit_scan", category="vision"):
                    audit_scanned = self._audit_all_units(force_all=False)

        with profiler.time_system("vision_dirty_snapshot", category="vision"):
            dirty = tuple(self._dirty)
            self._dirty.clear()

        changed = 0
        tile_updates = 0
        unit_tiles_added = 0
        unit_tiles_removed = 0
        faction_tiles_added = 0
        faction_tiles_removed = 0
        lifecycle_removals = 0

        geometry_hits_before = self._stat_geometry_hits
        geometry_misses_before = self._stat_geometry_misses
        geometry_evictions_before = self._stat_geometry_evictions

        samples = {
            "component_fetch": _SampleAccumulator(sample_every),
            "geometry": _SampleAccumulator(sample_every),
            "set_diff": _SampleAccumulator(sample_every),
            "union_maintenance": _SampleAccumulator(sample_every),
            "state_writeback": _SampleAccumulator(sample_every),
            "explored_update": _SampleAccumulator(sample_every),
        }

        with profiler.time_system("vision_dirty_batch", category="vision"):
            for entity in dirty:
                component_fetch = samples["component_fetch"]
                if component_fetch.should_sample():
                    started = time.perf_counter_ns()
                    position = self.world.get_component(entity, vision_mod.HexPosition)
                    vision = self.world.get_component(entity, vision_mod.Vision)
                    unit = self.world.get_component(entity, vision_mod.Unit)
                    component_fetch.add_sample(started)
                else:
                    position = self.world.get_component(entity, vision_mod.HexPosition)
                    vision = self.world.get_component(entity, vision_mod.Vision)
                    unit = self.world.get_component(entity, vision_mod.Unit)

                if position is None or vision is None or unit is None:
                    lifecycle_removals += 1
                    removed = self._remove_unit_contribution(entity, fog)
                    faction_tiles_removed += removed
                    continue

                current_pos = (position.col, position.row)
                current_range = int(vision.range)
                current_faction = unit.faction

                unchanged = (
                    not vision.dirty
                    and vision._last_observed_pos == current_pos
                    and vision._last_range == current_range
                    and entity in self._unit_visibility
                    and self._unit_faction.get(entity) == current_faction
                )
                if unchanged:
                    self._stat_cache_hits += 1
                    continue

                visible_tiles = samples["geometry"].call(
                    self._visibility_for, current_pos, current_range
                )
                tile_updates += len(visible_tiles)
                old_tiles = self._unit_visibility.get(entity, frozenset())
                old_faction = self._unit_faction.get(entity)

                set_diff = samples["set_diff"]
                if set_diff.should_sample():
                    started = time.perf_counter_ns()
                    removed_tiles = old_tiles.difference(visible_tiles)
                    added_tiles = visible_tiles.difference(old_tiles)
                    set_diff.add_sample(started)
                else:
                    removed_tiles = old_tiles.difference(visible_tiles)
                    added_tiles = visible_tiles.difference(old_tiles)

                union = samples["union_maintenance"]
                sample_union = union.should_sample()
                union_started = time.perf_counter_ns() if sample_union else 0

                if old_faction is not None and old_faction != current_faction:
                    removed, union_removed = self._remove_tiles(
                        fog, old_faction, old_tiles
                    )
                    unit_tiles_removed += removed
                    faction_tiles_removed += union_removed
                    old_tiles = frozenset()
                    removed_tiles = old_tiles.difference(visible_tiles)
                    added_tiles = visible_tiles.difference(old_tiles)

                if removed_tiles:
                    removed, union_removed = self._remove_tiles(
                        fog, current_faction, removed_tiles
                    )
                    unit_tiles_removed += removed
                    faction_tiles_removed += union_removed

                if added_tiles:
                    added, union_added = self._add_tiles(
                        fog, current_faction, added_tiles
                    )
                    unit_tiles_added += added
                    faction_tiles_added += union_added

                if sample_union:
                    union.add_sample(union_started)

                state_writeback = samples["state_writeback"]
                sample_state = state_writeback.should_sample()
                state_started = time.perf_counter_ns() if sample_state else 0

                self._unit_visibility[entity] = visible_tiles
                self._unit_faction[entity] = current_faction
                vision.visible_tiles = set(visible_tiles)
                vision._last_observed_pos = current_pos
                vision._last_range = current_range
                vision.dirty = False

                if sample_state:
                    state_writeback.add_sample(state_started)

                explored_update = samples["explored_update"]
                sample_explored = explored_update.should_sample()
                explored_started = time.perf_counter_ns() if sample_explored else 0

                explored = fog.explored_tiles.setdefault(current_faction, set())
                explored.update(visible_tiles)

                if sample_explored:
                    explored_update.add_sample(explored_started)

                self._stat_recomputes += 1
                changed += 1

        fog_delta_tiles = sum(len(tiles) for tiles in self._frame_fog_delta.values())
        with profiler.time_system("vision_fog_delta_publish", category="vision"):
            fog_journal_revision = vision_mod.publish_fog_visibility_delta(
                self.world, self._frame_fog_delta
            )

        with profiler.time_system("vision_metrics_publish", category="vision"):
            self._publish_metrics(
                dirty_seen=len(dirty),
                changed=changed,
                tile_updates=tile_updates,
                unit_tiles_added=unit_tiles_added,
                unit_tiles_removed=unit_tiles_removed,
                faction_tiles_added=faction_tiles_added,
                faction_tiles_removed=faction_tiles_removed,
                audit_scanned=audit_scanned,
                geometry_hits=self._stat_geometry_hits - geometry_hits_before,
                geometry_misses=self._stat_geometry_misses - geometry_misses_before,
                geometry_evictions=self._stat_geometry_evictions - geometry_evictions_before,
                fog_delta_tiles=fog_delta_tiles,
                fog_journal_revision=fog_journal_revision,
            )

            profiler.set_frame_metric(
                "phase5_attr_vision_lifecycle_removals", lifecycle_removals
            )
            _publish_sample(
                "phase5_attr_vision_component_fetch",
                samples["component_fetch"],
            )
            _publish_sample(
                "phase5_attr_vision_geometry",
                samples["geometry"],
            )
            _publish_sample(
                "phase5_attr_vision_set_diff",
                samples["set_diff"],
            )
            _publish_sample(
                "phase5_attr_vision_union_maintenance",
                samples["union_maintenance"],
            )
            _publish_sample(
                "phase5_attr_vision_state_writeback",
                samples["state_writeback"],
            )
            _publish_sample(
                "phase5_attr_vision_explored_update",
                samples["explored_update"],
            )

    vision_mod.VisionSystem.update = attributed_vision_update


def _install_probes() -> None:
    sample_every = _sample_every()
    _verify_source_contract()

    # Importing rotk_env.main installs STAR's concrete profiler into the ECS
    # profiling hook before these probes are mounted.
    import rotk_env.main as env_main

    _install_animation_probes(sample_every)
    _install_vision_probe(sample_every)

    ecs_profiling.profiler.set_metadata(
        phase5_core_attribution=True,
        phase5_core_attribution_sample_every=sample_every,
        phase5_core_attribution_source_guard=EXPECTED_BLOBS,
    )

    env_main.main()


def main() -> int:
    _install_probes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
