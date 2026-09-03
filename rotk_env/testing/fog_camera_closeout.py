"""Pure analysis helpers for the Camera-to-Fog closeout reassessment."""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Mapping

EXPERIMENT_ID = "2026-09-camera-fog-full-rebuild"
PHASE = "closeout_reassessment_v1"
HISTORICAL_TILE_LOOP_MS = 27.918

EXPECTED_PATHS = {
    "geometry_path": "fused",
    "corner_path": "precomputed",
    "world_corner_path": "cached",
    "presentation_bounds_path": "fog_content",
}

FINE_TIMER_FIELDS = (
    "polygon_timing_enabled",
    "hex_corners_timing_enabled",
    "geometry_prepare_timing_enabled",
    "screen_transform_timing_enabled",
    "bounds_rect_timing_enabled",
)

_PARENT_SECTIONS = {
    "world_update",
    "MapRenderSystem",
    "render_engine",
    "fog_surface_full_build",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _per_rebuild(total: int, rebuilds: int) -> float | None:
    return total / rebuilds if rebuilds else None


def extract_workload(stop: Mapping[str, Any]) -> Dict[str, object]:
    """Extract exact Fog workload counters and normalize them per rebuild."""
    attribution = _mapping(stop.get("full_build_attribution"))
    rebuilds = int(stop.get("fog_full_build_delta", 0) or 0)
    input_tiles = int(attribution.get("full_build_input_tiles", 0) or 0)
    visible = int(attribution.get("full_build_visible_no_fog_tiles", 0) or 0)
    skipped = int(
        attribution.get("full_build_visible_no_fog_skipped_tiles", 0) or 0
    )
    polygons = int(attribution.get("full_build_polygon_draw_tiles", 0) or 0)
    return {
        "camera_changed_frames": int(stop.get("camera_changed_frames", 0) or 0),
        "fog_full_rebuilds": rebuilds,
        "input_tiles_total": input_tiles,
        "input_tiles_per_rebuild": _per_rebuild(input_tiles, rebuilds),
        "visible_no_fog_tiles_total": visible,
        "visible_no_fog_tiles_per_rebuild": _per_rebuild(visible, rebuilds),
        "visible_no_fog_skipped_total": skipped,
        "visible_no_fog_skipped_per_rebuild": _per_rebuild(skipped, rebuilds),
        "polygon_tiles_total": polygons,
        "polygon_tiles_per_rebuild": _per_rebuild(polygons, rebuilds),
    }


def extract_costs(stop: Mapping[str, Any]) -> Dict[str, object]:
    """Extract coarse production profiler costs without low-level timers."""
    profile = _mapping(stop.get("profile_snapshot"))
    sections = _mapping(profile.get("sections"))

    def section(name: str, key: str = "inclusive_ms") -> float | None:
        return _number(_mapping(sections.get(name)).get(key))

    return {
        "fog_tile_loop_mean_ms": section("fog_full_build_tile_loop"),
        "fog_full_build_mean_ms": section("fog_surface_full_build"),
        "fog_surface_allocate_mean_ms": section(
            "fog_full_build_surface_allocate"
        ),
        "map_render_inclusive_mean_ms": section("MapRenderSystem"),
        "map_render_self_mean_ms": section("MapRenderSystem", "self_ms"),
        "render_engine_mean_ms": section("render_engine"),
        "render_queue_submit_mean_ms": section("render_queue_submit"),
        "render_scalar_execute_mean_ms": section("render_scalar_execute"),
        "frame_mean_ms": _number(profile.get("avg_frame_ms")),
        "fps": _number(profile.get("avg_fps")),
        "p50_frame_ms": _number(profile.get("p50_frame_ms")),
        "p95_frame_ms": _number(profile.get("p95_frame_ms")),
        "p99_frame_ms": _number(profile.get("p99_frame_ms")),
        "max_frame_ms": _number(profile.get("max_frame_ms")),
        "epoch_worst_frame_ms": _number(profile.get("epoch_worst_slow_frame_ms")),
    }


def extract_tail_diagnostics(stop: Mapping[str, Any]) -> Dict[str, object]:
    """Identify local max-self sections without treating tails as verdicts."""
    profile = _mapping(stop.get("profile_snapshot"))
    sections = _mapping(profile.get("sections"))
    ranked = []
    for name, raw in sections.items():
        if name in _PARENT_SECTIONS:
            continue
        item = _mapping(raw)
        max_self = _number(item.get("max_self_ms"))
        if max_self is None:
            continue
        ranked.append(
            {
                "name": str(name),
                "max_self_ms": max_self,
                "max_inclusive_ms": _number(item.get("max_inclusive_ms")),
                "mean_self_ms": _number(item.get("self_ms")),
            }
        )
    ranked.sort(key=lambda item: (-float(item["max_self_ms"]), item["name"]))
    top = ranked[:5]
    fog_max = _number(
        _mapping(sections.get("fog_full_build_tile_loop")).get("max_self_ms")
    )
    local_peak = top[0] if top else None
    outside_fog = bool(
        local_peak
        and not str(local_peak["name"]).startswith("fog_")
        and (
            fog_max is None or float(local_peak["max_self_ms"]) > fog_max
        )
    )
    return {
        "epoch_worst_frame_ms": _number(profile.get("epoch_worst_slow_frame_ms")),
        "p99_frame_ms": _number(profile.get("p99_frame_ms")),
        "max_frame_ms": _number(profile.get("max_frame_ms")),
        "top_5_sections_by_max_self_ms": top,
        "worst_slow_frame": profile.get("worst_slow_frame"),
        "classification": (
            "TAIL-CONTAMINATION-OUTSIDE-FOG"
            if outside_fog
            else "NO-OUTSIDE-FOG-TAIL-PROVEN"
        ),
    }


def validate_configuration(stop: Mapping[str, Any]) -> Dict[str, object]:
    """Validate requested, effective, and pre-run production defaults."""
    checks: Dict[str, bool] = {}
    for stem, expected in EXPECTED_PATHS.items():
        checks[f"{stem}_before_is_production_default"] = (
            stop.get(f"{stem}_before") == expected
        )
        checks[f"{stem}_requested"] = stop.get(f"{stem}_requested") == expected
        checks[f"{stem}_effective"] = stop.get(f"{stem}_effective") == expected
    checks.update(
        {
            f"{field}_off": stop.get(field) is False for field in FINE_TIMER_FIELDS
        }
    )
    checks.update(
        {
            "translation_feasibility_off": stop.get(
                "translation_feasibility_enabled"
            )
            is False,
            "phase_feasibility_off": stop.get("phase_raster_feasibility_enabled")
            is False,
            "full_rebuild_observer_none_before": stop.get(
                "full_rebuild_observer_active_before"
            )
            is False,
            "full_rebuild_observer_none_effective": stop.get(
                "full_rebuild_observer_active_effective"
            )
            is False,
        }
    )
    return {"valid": all(checks.values()), "checks": checks}


def validate_epoch(
    name: str,
    stop: Mapping[str, Any],
    *,
    require_warm_cache: bool = True,
) -> Dict[str, object]:
    """Validate one closeout epoch and its mode-specific invariants."""
    workload = extract_workload(stop)
    cache = _mapping(stop.get("tile_world_corner_cache"))
    rebuilds = int(workload["fog_full_rebuilds"])
    changed = int(workload["camera_changed_frames"])
    input_tiles = int(workload["input_tiles_total"])
    skipped = int(workload["visible_no_fog_skipped_total"])
    visible = int(workload["visible_no_fog_tiles_total"])
    polygons = int(workload["polygon_tiles_total"])
    config = validate_configuration(stop)

    checks = {
        "stop_ok": stop.get("ok") is True,
        "completed": stop.get("completed") is True,
        "not_aborted": stop.get("aborted_reason") is None,
        "camera_restored": stop.get("camera_restored") is True,
        "paths_restored": all(
            stop.get(field) is True
            for field in (
                "geometry_path_restored",
                "corner_path_restored",
                "world_corner_path_restored",
                "presentation_bounds_path_restored",
            )
        ),
        "timers_restored": stop.get("attribution_timers_restored") is True,
        "observer_restored": stop.get("full_rebuild_observer_restored") is True,
        "fog_remained_enabled": stop.get("fog_enabled_start") is True
        and stop.get("fog_enabled_end") is True
        and int(stop.get("fog_disabled_frames", 0) or 0) == 0,
        "units_stationary": int(stop.get("active_moving_units_start", 0) or 0)
        == 0
        and int(stop.get("active_moving_units_end", 0) or 0) == 0
        and int(stop.get("unit_movement_frames", 0) or 0) == 0,
        "production_configuration": bool(config["valid"]),
        "skipped_equals_visible_no_fog": skipped == visible,
        "skipped_plus_polygon_equals_input": skipped + polygons == input_tiles,
        "warm_cache_no_misses": (
            not require_warm_cache or int(cache.get("misses_delta", 0) or 0) == 0
        ),
    }
    if name == "stationary_z015":
        checks["stationary_camera_unchanged"] = changed == 0
        checks["stationary_no_fog_rebuild"] = rebuilds == 0
    elif name in {"short_pan_z015_a", "short_pan_z015_b", "short_pan_z050"}:
        checks["short_pan_camera_frames"] = changed == 39
        checks["short_pan_fog_rebuilds"] = rebuilds == 39
    elif name in {"long_pan_z015", "zoom_z015"}:
        checks["geometry_key_rebuild_tolerance"] = (
            rebuilds <= changed and changed - rebuilds <= 1
        )
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "configuration": config,
    }


def summarize_epoch(
    name: str,
    raw: Mapping[str, Any],
    *,
    included_in_closeout_metrics: bool,
    require_warm_cache: bool,
) -> Dict[str, object]:
    stop = _mapping(raw.get("stop"))
    return {
        "name": name,
        "included_in_closeout_metrics": included_in_closeout_metrics,
        "mode": stop.get("mode"),
        "workload": extract_workload(stop),
        "cache": dict(_mapping(stop.get("tile_world_corner_cache"))),
        "costs": extract_costs(stop),
        "tail_diagnostics": extract_tail_diagnostics(stop),
        "validation": validate_epoch(
            name, stop, require_warm_cache=require_warm_cache
        ),
        "raw": dict(raw),
    }


def primary_aggregate(runs: Mapping[str, Mapping[str, Any]]) -> Dict[str, object]:
    a = _mapping(_mapping(runs["short_pan_z015_a"]).get("costs"))
    b = _mapping(_mapping(runs["short_pan_z015_b"]).get("costs"))

    def average(key: str) -> float | None:
        values = [_number(a.get(key)), _number(b.get(key))]
        return mean(value for value in values if value is not None) if all(
            value is not None for value in values
        ) else None

    tile_a = _number(a.get("fog_tile_loop_mean_ms"))
    tile_b = _number(b.get("fog_tile_loop_mean_ms"))
    drift = (
        abs(tile_a - tile_b)
        if tile_a is not None and tile_b is not None
        else None
    )
    tile_mean = average("fog_tile_loop_mean_ms")
    drift_pct = drift / tile_mean * 100.0 if drift is not None and tile_mean else None
    return {
        "tile_loop_ms": average("fog_tile_loop_mean_ms"),
        "full_build_ms": average("fog_full_build_mean_ms"),
        "frame_ms": average("frame_mean_ms"),
        "fps": average("fps"),
        "tile_loop_replicate_drift_ms": drift,
        "tile_loop_replicate_drift_pct": drift_pct,
        "drift_acceptable": drift_pct is not None and drift_pct <= 10.0,
    }


def workload_scaling(runs: Mapping[str, Mapping[str, Any]]) -> Dict[str, object]:
    primary_workloads = [
        _mapping(_mapping(runs[name]).get("workload"))
        for name in ("short_pan_z015_a", "short_pan_z015_b")
    ]
    primary_costs = [
        _mapping(_mapping(runs[name]).get("costs"))
        for name in ("short_pan_z015_a", "short_pan_z015_b")
    ]
    culling_workload = _mapping(_mapping(runs["short_pan_z050"]).get("workload"))
    culling_cost = _mapping(_mapping(runs["short_pan_z050"]).get("costs"))
    primary_polygons = mean(
        float(item.get("polygon_tiles_per_rebuild", 0.0) or 0.0)
        for item in primary_workloads
    )
    primary_tile_ms = mean(
        float(item.get("fog_tile_loop_mean_ms", 0.0) or 0.0)
        for item in primary_costs
    )
    culling_polygons = float(
        culling_workload.get("polygon_tiles_per_rebuild", 0.0) or 0.0
    )
    culling_tile_ms = float(culling_cost.get("fog_tile_loop_mean_ms", 0.0) or 0.0)

    def normalized(tile_ms: float, polygons: float) -> float | None:
        return tile_ms * 1000.0 / polygons if polygons else None

    fewer = culling_polygons < primary_polygons * 0.75
    lower = culling_tile_ms < primary_tile_ms
    return {
        "primary_polygon_tiles_per_rebuild": primary_polygons,
        "culling_polygon_tiles_per_rebuild": culling_polygons,
        "primary_tile_loop_ms": primary_tile_ms,
        "culling_tile_loop_ms": culling_tile_ms,
        "primary_tile_loop_us_per_polygon_tile": normalized(
            primary_tile_ms, primary_polygons
        ),
        "culling_tile_loop_us_per_polygon_tile": normalized(
            culling_tile_ms, culling_polygons
        ),
        "culling_processes_substantially_fewer_tiles": fewer,
        "culling_absolute_cost_is_lower": lower,
        "classification": (
            "WORKLOAD-PROPORTIONAL" if fewer and lower else "RESIDUAL-SCALING-ANOMALY"
        ),
    }


def historical_comparison(current_tile_loop_ms: float | None) -> Dict[str, object]:
    reduction = (
        HISTORICAL_TILE_LOOP_MS - current_tile_loop_ms
        if current_tile_loop_ms is not None
        else None
    )
    return {
        "label": "cross-commit supportive trajectory; not a same-commit causal A/B",
        "original_tile_loop_ms": HISTORICAL_TILE_LOOP_MS,
        "current_tile_loop_ms": current_tile_loop_ms,
        "absolute_reduction_ms": reduction,
        "percentage_reduction": (
            reduction / HISTORICAL_TILE_LOOP_MS * 100.0
            if reduction is not None
            else None
        ),
    }


def build_closeout_summary(
    *,
    base_commit: str,
    prime_raw: Mapping[str, Any],
    run_raw: Mapping[str, Mapping[str, Any]],
) -> Dict[str, object]:
    """Build the auditable closeout document and hard recommendation."""
    prime = summarize_epoch(
        "prime",
        prime_raw,
        included_in_closeout_metrics=False,
        require_warm_cache=False,
    )
    runs = {
        name: summarize_epoch(
            name,
            raw,
            included_in_closeout_metrics=True,
            require_warm_cache=True,
        )
        for name, raw in run_raw.items()
    }
    primary = primary_aggregate(runs)
    scaling = workload_scaling(runs)
    prime_cache = _mapping(prime.get("cache"))
    prime_workload = _mapping(prime.get("workload"))
    required_prime_entries = int(
        prime_workload.get("polygon_tiles_per_rebuild", 0) or 0
    )
    measured_cache_misses = {
        name: int(_mapping(run.get("cache")).get("misses_delta", 0) or 0)
        for name, run in runs.items()
    }
    cache_warm_state = {
        "prime_cache_entries_end": int(prime_cache.get("entries_end", 0) or 0),
        "prime_polygon_working_set_per_rebuild": required_prime_entries,
        "prime_visible_no_fog_tiles_not_cached": int(
            prime_workload.get("visible_no_fog_skipped_per_rebuild", 0) or 0
        ),
        "measured_epoch_misses": measured_cache_misses,
        "all_measured_epochs_zero_miss": all(
            misses == 0 for misses in measured_cache_misses.values()
        ),
    }
    checks = {
        "prime_valid": bool(_mapping(prime.get("validation")).get("valid")),
        "prime_excluded_from_closeout_metrics": prime.get(
            "included_in_closeout_metrics"
        )
        is False,
        "prime_populated_production_fog_working_set": int(
            prime_cache.get("entries_end", 0) or 0
        )
        >= required_prime_entries
        > 0,
        "all_measured_epochs_zero_cache_miss": cache_warm_state[
            "all_measured_epochs_zero_miss"
        ],
        "all_measured_epochs_valid": all(
            bool(_mapping(run.get("validation")).get("valid"))
            for run in runs.values()
        ),
        "primary_replicate_drift_acceptable": primary["drift_acceptable"] is True,
        "residual_scales_with_workload": scaling["classification"]
        == "WORKLOAD-PROPORTIONAL",
    }
    explained = all(checks.values())
    classification = (
        "EXPLAINED-WORKLOAD-BOUND" if explained else "UNEXPLAINED-RESIDUAL"
    )
    recommendation = (
        "CASE-CLOSEOUT-READY / RECOMMEND-CLOSED"
        if explained
        else "CASE-CLOSEOUT-NOT-READY / KEEP-OPEN"
    )
    return {
        "experiment": EXPERIMENT_ID,
        "phase": PHASE,
        "base_commit": base_commit,
        "configuration": {
            **EXPECTED_PATHS,
            "fine_timers_enabled": False,
            "translation_feasibility_enabled": False,
            "phase_feasibility_enabled": False,
            "full_rebuild_observer": None,
            "fog_enabled": True,
            "units_stationary": True,
        },
        "prime": prime,
        "cache_warm_state": cache_warm_state,
        "runs": runs,
        "primary": primary,
        "workload_scaling": scaling,
        "tail_diagnostics": {
            name: run["tail_diagnostics"] for name, run in runs.items()
        },
        "integrity_checks": {"valid": explained, "checks": checks},
        "historical_supportive_comparison": historical_comparison(
            _number(primary.get("tile_loop_ms"))
        ),
        "residual_classification": classification,
        "closeout_recommendation": recommendation,
    }


__all__ = [
    "EXPECTED_PATHS",
    "EXPERIMENT_ID",
    "PHASE",
    "build_closeout_summary",
    "extract_costs",
    "extract_tail_diagnostics",
    "extract_workload",
    "historical_comparison",
    "primary_aggregate",
    "summarize_epoch",
    "validate_configuration",
    "validate_epoch",
    "workload_scaling",
]
