"""Compatibility renderers plus low-overhead rare-tail diagnostics.

The production rendering semantics live in ``optimized_render_systems_base``.
This thin overlay keeps that verified implementation intact while adding:
- a compact opaque terrain presentation cache over the verified SRCALPHA overscan;
- a zero-copy fog presenter handoff for the already-set visible tile set;
- frame-level UnitRender diagnostics for command allocation and Python GC pauses.

The diagnostics deliberately avoid per-unit timers. They add only a few integer
counters, three render-queue size snapshots, and a GC callback whose work runs
only when Python actually performs a collection.
"""

from __future__ import annotations

import gc

from framework.ecs import profiling
from framework.engine import RMS

from ..components import HexPosition
from ..utils.gc_pause_tracker import GCPauseTracker
from .optimized_render_systems_base import (
    EffectRenderSystem,
    MapRenderSystem as _VerifiedMapRenderSystem,
    MiniMapSystem,
    UnitRenderSystem as _VerifiedUnitRenderSystem,
)
from .terrain_presentation_cache import OpaqueTerrainPresentationMixin


class MapRenderSystem(OpaqueTerrainPresentationMixin, _VerifiedMapRenderSystem):
    """Verified map renderer with opaque terrain present + zero-copy fog."""

    def _render_fog_of_war_optimized(
        self,
        visible_tiles,
        camera_offset,
        zoom: float = 1.0,
    ) -> None:
        # ``_get_visible_tiles_smart`` already returns a set. The previous scale
        # override copied thousands of entries every frame only to satisfy an
        # annotation in IncrementalFogSurfacePresenter.
        self._fog_presenter.render(visible_tiles, camera_offset, zoom)


class UnitRenderSystem(_VerifiedUnitRenderSystem):
    """Verified unit renderer plus low-overhead rare-tail attribution."""

    def __init__(self):
        super().__init__()
        self._gc_tail_tracker = GCPauseTracker()
        self._gc_tail_callback = self._gc_tail_tracker.callback
        self._gc_tail_registered = False

    def initialize(self, world) -> None:
        super().initialize(world)
        if self._gc_tail_callback not in gc.callbacks:
            gc.callbacks.append(self._gc_tail_callback)
            self._gc_tail_registered = True

    def cleanup(self) -> None:
        if self._gc_tail_registered:
            try:
                gc.callbacks.remove(self._gc_tail_callback)
            except ValueError:
                pass
            self._gc_tail_registered = False

    @staticmethod
    def _queued_render_commands() -> int:
        queue = getattr(RMS, "_render_queue", None)
        if not queue:
            return 0
        return sum(len(commands) for commands in queue.values())

    def update(self, delta_time: float) -> None:
        gc_before = self._gc_tail_tracker.snapshot()
        self._gc_tail_tracker.set_phase("other")
        try:
            super().update(delta_time)
        finally:
            self._gc_tail_tracker.set_phase("other")
            self._publish_gc_tail_metrics(gc_before)

    def _publish_gc_tail_metrics(self, before) -> None:
        delta = self._gc_tail_tracker.delta_since(before)
        metric = profiling.profiler.set_frame_metric
        metric("unit_gc_collections", delta.collections)
        metric("unit_gc_pause_ms", delta.pause_ms)
        metric("unit_gc_gen0_collections", delta.generation_collections[0])
        metric("unit_gc_gen1_collections", delta.generation_collections[1])
        metric("unit_gc_gen2_collections", delta.generation_collections[2])
        metric("unit_gc_gen0_pause_ms", delta.generation_pause_ms[0])
        metric("unit_gc_gen1_pause_ms", delta.generation_pause_ms[1])
        metric("unit_gc_gen2_pause_ms", delta.generation_pause_ms[2])
        metric("unit_gc_static_draw_pause_ms", delta.phase_pause_ms.get("static", 0.0))
        metric(
            "unit_gc_animated_draw_pause_ms",
            delta.phase_pause_ms.get("animated", 0.0),
        )
        metric("unit_gc_other_pause_ms", delta.phase_pause_ms.get("other", 0.0))
        metric("unit_gc_collected_objects", delta.collected_objects)
        metric("unit_gc_uncollectable_objects", delta.uncollectable_objects)
        for generation in range(3):
            metric(
                f"unit_gc_count{generation}_start",
                before.gc_counts[generation],
            )
            metric(
                f"unit_gc_count{generation}_end",
                delta.gc_counts_end[generation],
            )

    def _render_units_batch(self, visible_units, camera_offset, zoom):
        """Mirror the verified batch path while attributing allocation pressure."""
        metric = profiling.profiler.set_frame_metric
        if not visible_units:
            metric("animated_visible_units", 0)
            metric("unit_static_groups", 0)
            metric("unit_static_candidate_units", 0)
            metric("unit_static_submitted_units", 0)
            metric("unit_static_max_group_size", 0)
            metric("unit_static_multi_groups", 0)
            metric("unit_animated_draw_units", 0)
            metric("unit_static_commands_added", 0)
            metric("unit_animated_commands_added", 0)
            metric("unit_render_commands_added", 0)
            return

        with profiling.profiler.time_system("unit_batch_prepare", category="render"):
            animation_system = self._get_animation_system()
            units_by_position = {}
            animated_units = []

            for entity in visible_units:
                animated_screen_pos = self._get_fast_animation_screen_position(
                    entity, animation_system, camera_offset, zoom
                )
                if animated_screen_pos is not None:
                    animated_units.append((entity, animated_screen_pos))
                    continue

                position = self.world.get_component(entity, HexPosition)
                if position:
                    pos_key = (position.col, position.row)
                    units_by_position.setdefault(pos_key, []).append(entity)

        static_group_sizes = [len(units) for units in units_by_position.values()]
        static_candidate_units = sum(static_group_sizes)
        static_submitted_units = sum(
            1 if size == 1 else min(size, 6) for size in static_group_sizes
        )
        metric("animated_visible_units", len(animated_units))
        metric("unit_static_groups", len(static_group_sizes))
        metric("unit_static_candidate_units", static_candidate_units)
        metric("unit_static_submitted_units", static_submitted_units)
        metric(
            "unit_static_max_group_size",
            max(static_group_sizes, default=0),
        )
        metric(
            "unit_static_multi_groups",
            sum(1 for size in static_group_sizes if size > 1),
        )
        metric("unit_animated_draw_units", len(animated_units))

        queue_before = self._queued_render_commands()
        self._gc_tail_tracker.set_phase("static")
        try:
            with profiling.profiler.time_system("unit_static_draw", category="render"):
                for pos_key, units in units_by_position.items():
                    self._render_unit_group_optimized(
                        pos_key, units, camera_offset, zoom
                    )
        finally:
            self._gc_tail_tracker.set_phase("other")
        queue_after_static = self._queued_render_commands()

        self._gc_tail_tracker.set_phase("animated")
        try:
            with profiling.profiler.time_system(
                "unit_animated_draw", category="render"
            ):
                for entity, (screen_x, screen_y) in animated_units:
                    self._render_single_unit_fast(entity, screen_x, screen_y, zoom)
        finally:
            self._gc_tail_tracker.set_phase("other")
        queue_after_animated = self._queued_render_commands()

        static_commands = max(0, queue_after_static - queue_before)
        animated_commands = max(0, queue_after_animated - queue_after_static)
        metric("unit_static_commands_added", static_commands)
        metric("unit_animated_commands_added", animated_commands)
        metric(
            "unit_render_commands_added",
            max(0, queue_after_animated - queue_before),
        )
