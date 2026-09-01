"""Compatibility wrapper adding UnitRender tail diagnostics to scale snapshots."""

from __future__ import annotations

from . import scale_experiment_measurement_base as _base

_original_compact_slow_frame = _base._compact_slow_frame

_TAIL_METRICS = (
    "render_commands",
    "render_simple_blits",
    "render_blit_batches",
    "unit_static_groups",
    "unit_static_candidate_units",
    "unit_static_submitted_units",
    "unit_static_max_group_size",
    "unit_static_multi_groups",
    "unit_animated_draw_units",
    "unit_static_commands_added",
    "unit_animated_commands_added",
    "unit_render_commands_added",
    "unit_gc_collections",
    "unit_gc_pause_ms",
    "unit_gc_gen0_collections",
    "unit_gc_gen1_collections",
    "unit_gc_gen2_collections",
    "unit_gc_gen0_pause_ms",
    "unit_gc_gen1_pause_ms",
    "unit_gc_gen2_pause_ms",
    "unit_gc_static_draw_pause_ms",
    "unit_gc_animated_draw_pause_ms",
    "unit_gc_other_pause_ms",
    "unit_gc_collected_objects",
    "unit_gc_uncollectable_objects",
    "unit_gc_count0_start",
    "unit_gc_count0_end",
    "unit_gc_count1_start",
    "unit_gc_count1_end",
    "unit_gc_count2_start",
    "unit_gc_count2_end",
)


def _compact_slow_frame(snapshot):
    result = _original_compact_slow_frame(snapshot)
    if result is None or not isinstance(snapshot, dict):
        return result

    source_metrics = snapshot.get("frame_metrics", {})
    target_metrics = result.setdefault("frame_metrics", {})
    if isinstance(source_metrics, dict):
        for key in _TAIL_METRICS:
            if key in source_metrics:
                target_metrics[key] = source_metrics[key]
    return result


_base._compact_slow_frame = _compact_slow_frame

install_scale_experiment_measurement = _base.install_scale_experiment_measurement

__all__ = ["install_scale_experiment_measurement"]
