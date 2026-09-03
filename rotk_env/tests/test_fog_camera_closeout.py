from copy import deepcopy

import pytest

from rotk_env.testing.fog_camera_closeout import (
    build_closeout_summary,
    extract_tail_diagnostics,
    extract_workload,
    historical_comparison,
    primary_aggregate,
    summarize_epoch,
    validate_configuration,
    validate_epoch,
    workload_scaling,
)


def _profile(tile_ms=15.0, frame_ms=28.0, fps=35.0):
    return {
        "ok": True,
        "avg_fps": fps,
        "avg_frame_ms": frame_ms,
        "p50_frame_ms": frame_ms - 1.0,
        "p95_frame_ms": frame_ms + 2.0,
        "p99_frame_ms": frame_ms + 5.0,
        "max_frame_ms": frame_ms + 9.0,
        "epoch_worst_slow_frame_ms": frame_ms + 10.0,
        "sections": {
            "fog_full_build_tile_loop": {
                "inclusive_ms": tile_ms,
                "self_ms": tile_ms,
                "max_self_ms": tile_ms + 1.0,
                "max_inclusive_ms": tile_ms + 1.0,
            },
            "fog_surface_full_build": {
                "inclusive_ms": tile_ms + 0.2,
                "self_ms": 0.02,
                "max_self_ms": 0.03,
                "max_inclusive_ms": tile_ms + 1.2,
            },
            "fog_full_build_surface_allocate": {
                "inclusive_ms": 0.1,
                "self_ms": 0.1,
                "max_self_ms": 0.2,
                "max_inclusive_ms": 0.2,
            },
            "MapRenderSystem": {
                "inclusive_ms": tile_ms + 2.0,
                "self_ms": 2.0,
                "max_self_ms": 2.5,
                "max_inclusive_ms": tile_ms + 3.0,
            },
            "render_engine": {
                "inclusive_ms": 2.2,
                "self_ms": 0.1,
                "max_self_ms": 0.2,
                "max_inclusive_ms": 2.5,
            },
            "render_queue_submit": {
                "inclusive_ms": 2.0,
                "self_ms": 0.02,
                "max_self_ms": 0.03,
                "max_inclusive_ms": 2.2,
            },
            "render_scalar_execute": {
                "inclusive_ms": 1.4,
                "self_ms": 1.4,
                "max_self_ms": 1.6,
                "max_inclusive_ms": 1.6,
            },
            "unit_static_draw": {
                "inclusive_ms": 2.5,
                "self_ms": 2.5,
                "max_self_ms": 20.0,
                "max_inclusive_ms": 20.0,
            },
            "world_update": {
                "inclusive_ms": 24.0,
                "self_ms": 0.03,
                "max_self_ms": 0.04,
                "max_inclusive_ms": 40.0,
            },
        },
        "worst_slow_frame": {
            "frame_index": 12,
            "frame_ms": frame_ms + 10.0,
            "top_sections": [
                {"name": "unit_static_draw", "self_ms": 20.0}
            ],
        },
    }


def _stop(
    *,
    mode="short_pan",
    changed=39,
    rebuilds=39,
    input_per=8281,
    visible_per=1888,
    polygon_per=6393,
    tile_ms=15.0,
    cache_misses=0,
):
    return {
        "ok": True,
        "completed": True,
        "mode": mode,
        "aborted_reason": None,
        "camera_restored": True,
        "geometry_path_before": "fused",
        "geometry_path_requested": "fused",
        "geometry_path_effective": "fused",
        "geometry_path_restored": True,
        "corner_path_before": "precomputed",
        "corner_path_requested": "precomputed",
        "corner_path_effective": "precomputed",
        "corner_path_restored": True,
        "world_corner_path_before": "cached",
        "world_corner_path_requested": "cached",
        "world_corner_path_effective": "cached",
        "world_corner_path_restored": True,
        "presentation_bounds_path_before": "fog_content",
        "presentation_bounds_path_requested": "fog_content",
        "presentation_bounds_path_effective": "fog_content",
        "presentation_bounds_path_restored": True,
        "polygon_timing_enabled": False,
        "hex_corners_timing_enabled": False,
        "geometry_prepare_timing_enabled": False,
        "screen_transform_timing_enabled": False,
        "bounds_rect_timing_enabled": False,
        "translation_feasibility_enabled": False,
        "phase_raster_feasibility_enabled": False,
        "full_rebuild_observer_active_before": False,
        "full_rebuild_observer_active_effective": False,
        "attribution_timers_restored": True,
        "full_rebuild_observer_restored": True,
        "fog_enabled_start": True,
        "fog_enabled_end": True,
        "fog_disabled_frames": 0,
        "active_moving_units_start": 0,
        "active_moving_units_end": 0,
        "unit_movement_frames": 0,
        "camera_changed_frames": changed,
        "fog_full_build_delta": rebuilds,
        "full_build_attribution": {
            "full_build_input_tiles": input_per * rebuilds,
            "full_build_visible_no_fog_tiles": visible_per * rebuilds,
            "full_build_visible_no_fog_skipped_tiles": visible_per * rebuilds,
            "full_build_polygon_draw_tiles": polygon_per * rebuilds,
        },
        "tile_world_corner_cache": {
            "hits_delta": polygon_per * rebuilds,
            "misses_delta": cache_misses,
            "entries_end": 8281,
        },
        "profile_snapshot": _profile(tile_ms=tile_ms),
    }


def _raw(**kwargs):
    return {
        "start": {"ok": True},
        "status": {"completed": True},
        "stop": _stop(**kwargs),
    }


def _matrix():
    return {
        "stationary_z015": _raw(
            mode="stationary",
            changed=0,
            rebuilds=0,
            input_per=0,
            visible_per=0,
            polygon_per=0,
        ),
        "short_pan_z015_a": _raw(tile_ms=15.0),
        "short_pan_z050": _raw(
            input_per=2392, visible_per=180, polygon_per=2212, tile_ms=8.5
        ),
        "short_pan_z015_b": _raw(tile_ms=15.6),
        "long_pan_z015": _raw(mode="long_pan", changed=97, rebuilds=96),
        "zoom_z015": _raw(mode="zoom", changed=16, rebuilds=15),
    }


def test_extracts_workload_and_per_rebuild_normalization():
    workload = extract_workload(_stop())
    assert workload["input_tiles_per_rebuild"] == 8281
    assert workload["visible_no_fog_skipped_per_rebuild"] == 1888
    assert workload["polygon_tiles_per_rebuild"] == 6393


def test_detects_workload_accounting_anomaly():
    stop = _stop()
    stop["full_build_attribution"]["full_build_polygon_draw_tiles"] -= 1
    result = validate_epoch("short_pan_z015_a", stop)
    assert result["valid"] is False
    assert result["checks"]["skipped_plus_polygon_equals_input"] is False


def test_validates_production_paths_requested_effective_and_before():
    assert validate_configuration(_stop())["valid"] is True
    wrong = _stop()
    wrong["presentation_bounds_path_before"] = "map_content_legacy"
    assert validate_configuration(wrong)["valid"] is False


def test_requires_all_fine_timers_off_and_no_observer():
    timed = _stop()
    timed["polygon_timing_enabled"] = True
    assert validate_configuration(timed)["valid"] is False
    observed = _stop()
    observed["full_rebuild_observer_active_effective"] = True
    assert validate_configuration(observed)["valid"] is False


def test_warm_cache_validation_rejects_misses():
    result = validate_epoch("short_pan_z015_a", _stop(cache_misses=1))
    assert result["valid"] is False
    assert result["checks"]["warm_cache_no_misses"] is False


def test_short_pan_requires_exact_camera_and_rebuild_counts():
    assert validate_epoch("short_pan_z015_a", _stop())["valid"] is True
    assert validate_epoch(
        "short_pan_z015_a", _stop(rebuilds=38)
    )["valid"] is False


@pytest.mark.parametrize(
    "name,mode", [("long_pan_z015", "long_pan"), ("zoom_z015", "zoom")]
)
def test_long_pan_and_zoom_allow_one_geometry_key_frame(name, mode):
    assert validate_epoch(name, _stop(mode=mode, changed=20, rebuilds=19))["valid"]
    assert not validate_epoch(name, _stop(mode=mode, changed=20, rebuilds=18))["valid"]


def test_stationary_requires_zero_changes_and_rebuilds():
    stop = _stop(
        mode="stationary",
        changed=0,
        rebuilds=0,
        input_per=0,
        visible_per=0,
        polygon_per=0,
    )
    assert validate_epoch("stationary_z015", stop)["valid"] is True
    stop["fog_full_build_delta"] = 1
    assert validate_epoch("stationary_z015", stop)["valid"] is False


def test_primary_replicate_drift_calculation():
    runs = {
        name: summarize_epoch(
            name, raw, included_in_closeout_metrics=True, require_warm_cache=True
        )
        for name, raw in _matrix().items()
    }
    primary = primary_aggregate(runs)
    assert primary["tile_loop_ms"] == pytest.approx(15.3)
    assert primary["tile_loop_replicate_drift_ms"] == pytest.approx(0.6)
    assert primary["drift_acceptable"] is True


def test_residual_scaling_classification():
    runs = {
        name: summarize_epoch(
            name, raw, included_in_closeout_metrics=True, require_warm_cache=True
        )
        for name, raw in _matrix().items()
    }
    scaling = workload_scaling(runs)
    assert scaling["classification"] == "WORKLOAD-PROPORTIONAL"
    assert scaling["culling_tile_loop_us_per_polygon_tile"] is not None


def test_tail_top_section_extraction_excludes_parent_sections():
    tail = extract_tail_diagnostics(_stop())
    assert tail["top_5_sections_by_max_self_ms"][0]["name"] == "unit_static_draw"
    assert tail["classification"] == "TAIL-CONTAMINATION-OUTSIDE-FOG"
    assert "world_update" not in {
        item["name"] for item in tail["top_5_sections_by_max_self_ms"]
    }


def test_historical_comparison_is_explicitly_cross_commit():
    result = historical_comparison(15.0)
    assert "not a same-commit causal A/B" in result["label"]
    assert result["absolute_reduction_ms"] == pytest.approx(12.918)


def test_closeout_recommends_closed_when_all_invariants_hold():
    result = build_closeout_summary(
        base_commit="base", prime_raw=_raw(), run_raw=_matrix()
    )
    assert result["prime"]["included_in_closeout_metrics"] is False
    assert result["cache_warm_state"] == {
        "prime_cache_entries_end": 8281,
        "prime_polygon_working_set_per_rebuild": 6393,
        "prime_visible_no_fog_tiles_not_cached": 1888,
        "measured_epoch_misses": {
            "stationary_z015": 0,
            "short_pan_z015_a": 0,
            "short_pan_z050": 0,
            "short_pan_z015_b": 0,
            "long_pan_z015": 0,
            "zoom_z015": 0,
        },
        "all_measured_epochs_zero_miss": True,
    }
    assert result["residual_classification"] == "EXPLAINED-WORKLOAD-BOUND"
    assert result["closeout_recommendation"] == (
        "CASE-CLOSEOUT-READY / RECOMMEND-CLOSED"
    )


def test_closeout_keeps_open_on_structural_failure():
    matrix = _matrix()
    matrix["short_pan_z050"] = deepcopy(matrix["short_pan_z015_a"])
    result = build_closeout_summary(
        base_commit="base", prime_raw=_raw(), run_raw=matrix
    )
    assert result["residual_classification"] == "UNEXPLAINED-RESIDUAL"
    assert result["closeout_recommendation"] == (
        "CASE-CLOSEOUT-NOT-READY / KEEP-OPEN"
    )
