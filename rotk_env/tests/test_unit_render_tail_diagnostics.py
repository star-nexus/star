"""Regression tests for low-overhead UnitRender tail diagnostics."""

from types import SimpleNamespace

from rotk_env.systems.optimized_render_systems import MapRenderSystem
from rotk_env.testing import scale_experiment_measurement
from rotk_env.utils.gc_pause_tracker import GCPauseTracker


def test_gc_pause_tracker_attributes_generation_and_phase():
    ticks = iter((1_000_000, 3_500_000))
    tracker = GCPauseTracker(
        clock_ns=lambda: next(ticks),
        gc_count_fn=lambda: (11, 2, 0),
    )
    before = tracker.snapshot()

    tracker.set_phase("animated")
    tracker.callback("start", {"generation": 1})
    tracker.callback(
        "stop",
        {"generation": 1, "collected": 7, "uncollectable": 1},
    )
    delta = tracker.delta_since(before)

    assert delta.collections == 1
    assert delta.pause_ms == 2.5
    assert delta.generation_collections == (0, 1, 0)
    assert delta.generation_pause_ms == (0.0, 2.5, 0.0)
    assert delta.phase_collections["animated"] == 1
    assert delta.phase_pause_ms["animated"] == 2.5
    assert delta.collected_objects == 7
    assert delta.uncollectable_objects == 1
    assert delta.gc_counts_end == (11, 2, 0)


def test_map_fog_handoff_does_not_copy_visible_tile_set():
    calls = []

    class Presenter:
        def render(self, visible_tiles, camera_offset, zoom):
            calls.append((visible_tiles, camera_offset, zoom))

    fake_renderer = SimpleNamespace(_fog_presenter=Presenter())
    visible_tiles = {(0, 0), (1, 0)}

    MapRenderSystem._render_fog_of_war_optimized(
        fake_renderer, visible_tiles, [12.0, -3.0], 0.15
    )

    assert calls[0][0] is visible_tiles


def test_compact_slow_frame_keeps_unit_tail_metrics():
    snapshot = {
        "frame_index": 9,
        "frame_ms": 31.0,
        "active_ms": 30.0,
        "present_ms": 1.0,
        "fps_limiter_wait_ms": 0.0,
        "top_sections": [],
        "frame_metrics": {
            "unit_gc_collections": 1,
            "unit_gc_pause_ms": 17.25,
            "unit_gc_animated_draw_pause_ms": 17.25,
            "unit_animated_commands_added": 1600,
            "render_commands": 1700,
        },
    }

    result = scale_experiment_measurement._compact_slow_frame(snapshot)
    metrics = result["frame_metrics"]

    assert metrics["unit_gc_collections"] == 1
    assert metrics["unit_gc_pause_ms"] == 17.25
    assert metrics["unit_gc_animated_draw_pause_ms"] == 17.25
    assert metrics["unit_animated_commands_added"] == 1600
    assert metrics["render_commands"] == 1700
