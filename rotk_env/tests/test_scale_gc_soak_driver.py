"""Pure-logic tests for the repeated GC soak driver."""

import importlib.util
from pathlib import Path


_DRIVER_PATH = Path(__file__).resolve().parents[2] / "tools" / "scale_gc_soak.py"
_SPEC = importlib.util.spec_from_file_location("scale_gc_soak_driver", _DRIVER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_DRIVER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DRIVER)


def test_density_check_allows_small_absolute_unit_delta():
    snapshot = {
        "workload": {
            "living_units": 5000,
            "active_moving_units": 4997,
            "density": 4997 / 5000,
        }
    }

    ok, details = _DRIVER._density_check(snapshot, 1.0, 10)

    assert ok is True
    assert details["expected_active_units"] == 5000
    assert details["active_delta_units"] == -3


def test_density_check_rejects_material_workload_loss():
    snapshot = {
        "workload": {
            "living_units": 5000,
            "active_moving_units": 4950,
            "density": 0.99,
        }
    }

    ok, details = _DRIVER._density_check(snapshot, 1.0, 10)

    assert ok is False
    assert details["active_delta_units"] == -50


def test_summary_uses_post_priming_baseline_and_reports_vision_bound():
    baseline_after = {
        "memory": {"rss_mb": 350.0},
        "gc": {"tracked_objects": 200000},
        "world": {"entities": 100, "component_instances": 1000},
        "vision": {
            "geometry_cache_size": 3000,
            "geometry_cache_capacity": 4096,
            "geometry_cache_evictions": 0,
        },
    }
    final_after = {
        "memory": {"rss_mb": 352.0},
        "gc": {"tracked_objects": 201000},
        "world": {"entities": 100, "component_instances": 1000},
        "vision": {
            "geometry_cache_size": 4096,
            "geometry_cache_capacity": 4096,
            "geometry_cache_evictions": 500,
        },
    }
    result = {
        "baseline_collect": {"after": baseline_after},
        "cycles": [
            {
                "ok": True,
                "realtime_seconds": 15.0,
                "cumulative_realtime_seconds": 15.0,
                "deferred": {
                    "memory": {"rss_mb": 355.0},
                    "vision": {"geometry_cache_size": 4096},
                },
                "post_collect": {"collect_ms": 20.0, "collected": 0, "after": final_after},
            }
        ],
    }

    summary = _DRIVER._summary(result)

    assert summary["component_instance_growth"] == 0
    assert summary["entity_growth"] == 0
    assert summary["post_collect_rss_growth_mb"] == 2.0
    assert summary["vision_geometry_cache_capacity"] == 4096
    assert summary["final_vision_geometry_cache_size"] == 4096
    assert summary["final_vision_geometry_cache_evictions"] == 500
