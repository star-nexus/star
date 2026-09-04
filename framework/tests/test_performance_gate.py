"""Tests for the portable STAR performance gate contract evaluator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools.performance_gate import (
    ContractError,
    evaluate_contract,
    load_mapping,
    main,
    resolve_path,
)


def _profile():
    return {
        "window_capacity_limited": False,
        "metadata": {"clock_mode": "uncapped_wall_clock"},
        "active_frame_ms": {"p99": 5.2},
        "frame_metrics": {
            "vision_units_scanned": {"kind": "numeric", "max": 1.0},
            "vision_mode": {"kind": "categorical", "values": ["dirty_refcount"]},
        },
    }


def test_resolve_path_handles_nested_dict_and_missing_value():
    found, value = resolve_path(_profile(), "frame_metrics.vision_units_scanned.max")
    assert found is True
    assert value == 1.0

    found, value = resolve_path(_profile(), "frame_metrics.not_here.max")
    assert found is False
    assert value is None


def test_contract_supports_causal_numeric_and_categorical_rules():
    contract = {
        "name": "causal",
        "rules": [
            {"path": "window_capacity_limited", "op": "eq", "value": False},
            {
                "path": "frame_metrics.vision_units_scanned.max",
                "op": "lte",
                "value": 1,
            },
            {
                "path": "frame_metrics.vision_mode.values",
                "op": "contains",
                "value": "dirty_refcount",
            },
            {"path": "metadata.clock_mode", "op": "exists", "value": True},
        ],
    }

    results = evaluate_contract(_profile(), contract)
    assert all(result.passed for result in results)


def test_missing_metric_fails_normal_comparison_but_can_be_checked_explicitly():
    contract = {
        "rules": [
            {"path": "frame_metrics.missing.max", "op": "lte", "value": 1},
            {"path": "frame_metrics.missing", "op": "exists", "value": False},
        ]
    }
    results = evaluate_contract(_profile(), contract)
    assert results[0].passed is False
    assert results[1].passed is True


def test_malformed_contract_is_rejected():
    with pytest.raises(ContractError):
        evaluate_contract(_profile(), {"rules": []})
    with pytest.raises(ContractError):
        evaluate_contract(
            _profile(),
            {"rules": [{"path": "active_frame_ms.p99", "op": "bogus", "value": 1}]},
        )


def test_static_reference_contract_rejects_material_controlled_regression():
    repo_root = Path(__file__).resolve().parents[2]
    contract = load_mapping(repo_root / "tools" / "performance_contract_static_window_reference.yaml")
    profile = {
        "metadata": {
            "benchmark_workload": "static-window-v1",
            "benchmark_uncapped": True,
        },
        "controlled_work_frame_ms": {"p99": 5.0},
        "sections": {
            "render_engine": {"inclusive_ms": 1.6},
            "render_scalar_execute": {"inclusive_ms": 1.3},
        },
        "uninstrumented_frame_ms": {"p99": 0.02},
    }

    results = evaluate_contract(profile, contract)
    failed_paths = {result.path for result in results if not result.passed}
    assert failed_paths == {"controlled_work_frame_ms.p99"}


def test_one_mover_reference_contract_uses_max_for_sparse_dynamic_regression():
    repo_root = Path(__file__).resolve().parents[2]
    contract = load_mapping(repo_root / "tools" / "performance_contract_one_mover.yaml")
    profile = {
        "metadata": {
            "benchmark_workload": "one-mover-v1",
            "benchmark_input_policy": "blocked_gameplay_events",
            "benchmark_measurement_duration_s": 5.0,
            "benchmark_summary_scope": "final_measurement_window",
            "benchmark_move_path_length": 7,
            "benchmark_move_cost": 6,
        },
        "window_capacity_limited": False,
        "window_coverage_s": 5.0,
        "frame_metrics": {
            "fog_enabled": {"min": 1.0, "max": 1.0},
            "effect_position_index_changes": {"max": 1.0},
            "vision_dirty_units": {"max": 1.0},
            "vision_units_scanned": {"max": 1.0},
            "vision_units_changed": {"max": 1.0},
            "vision_fog_delta_tiles": {"max": 7.0},
            "vision_geometry_cache_evictions": {"max": 0.0},
            "input_key_down": {"max": 0.0},
            "input_mouse_button": {"max": 0.0},
            "input_mouse_wheel": {"max": 0.0},
            "map_render_mode": {"values": ["overscan_cached"]},
        },
        # A sparse movement regression can leave p99 healthy when <1% of frames
        # are dynamic; max must still trip the reference gate.
        "controlled_work_frame_ms": {"p99": 2.8, "max": 5.0},
        "uninstrumented_frame_ms": {"p99": 0.02},
    }

    results = evaluate_contract(profile, contract)
    failed_paths = {result.path for result in results if not result.passed}
    assert failed_paths == {"controlled_work_frame_ms.max"}


def test_cli_exit_codes_distinguish_pass_fail_and_contract_error(tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")

    pass_contract = tmp_path / "pass.yaml"
    pass_contract.write_text(
        yaml.safe_dump(
            {
                "name": "pass",
                "rules": [
                    {"path": "frame_metrics.vision_units_scanned.max", "op": "lte", "value": 1}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert main(["--profile", str(profile_path), "--contract", str(pass_contract)]) == 0

    fail_contract = tmp_path / "fail.yaml"
    fail_contract.write_text(
        yaml.safe_dump(
            {
                "name": "fail",
                "rules": [
                    {"path": "frame_metrics.vision_units_scanned.max", "op": "lte", "value": 0}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert main(["--profile", str(profile_path), "--contract", str(fail_contract)]) == 1

    invalid_contract = tmp_path / "invalid.yaml"
    invalid_contract.write_text("rules: []\n", encoding="utf-8")
    assert main(["--profile", str(profile_path), "--contract", str(invalid_contract)]) == 2
