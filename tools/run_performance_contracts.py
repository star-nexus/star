"""Run the portable structural performance-regression contract suite.

These checks protect algorithmic/fast-path invariants rather than host-specific
wall-clock numbers. They are suitable for ordinary developer machines and CI.
Timing contracts belong in ``tools/performance_gate.py`` with a pinned workload
and, when necessary, a pinned benchmark host.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


STRUCTURAL_CONTRACTS = [
    # Measurement semantics themselves.
    "framework/tests/test_performance_profiler.py",
    "framework/tests/test_performance_measurement_contract.py",
    "framework/tests/test_performance_gate.py",
    "framework/tests/test_static_window_benchmark_entrypoint.py",
    # Accepted bounded realtime-GC semantics for latency-critical scale windows.
    "framework/tests/test_realtime_gc_policy.py",
    # Phase-4 scale control must remain deterministic and outside per-frame work.
    "framework/tests/test_scale_harness_contract.py",
    # Render queue should preserve blit batching.
    "framework/tests/test_render_blit_batching.py",
    # One dirty Vision observer must not become an all-observer recompute.
    "rotk_env/tests/test_vision_incremental_index.py::test_mark_dirty_updates_only_changed_unit_and_keeps_explored_history",
    # The validated large-window Vision working-set headroom must not regress to 4096.
    "rotk_env/tests/test_window_vision_cache_config.py::test_window_vision_cache_keeps_validated_headroom_default",
    # Fog visibility changes must stay incremental and pixel-equivalent.
    "rotk_env/tests/test_fog_surface_presenter.py::test_incremental_reveal_and_hide_match_fresh_canonical_surface",
    # Unit rendering must filter spatial candidates rather than resident units.
    "rotk_env/tests/test_window_unit_render_spatial_cull.py::test_spatial_cull_filters_bounds_before_fog",
    # Camera pan inside the overscan margin must reuse the terrain raster.
    "rotk_env/tests/test_window_map_overscan.py::test_pan_reuses_overscan_and_zoom_keeps_direct_fallback",
    # Terrain presentation must retain the opaque compact fast path.
    "rotk_env/tests/test_terrain_presentation_cache.py::test_compact_cache_is_non_srcalpha_and_pixel_equivalent",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run STAR structural performance contracts")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the protected pytest node IDs without running them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        for contract in STRUCTURAL_CONTRACTS:
            print(contract)
        return 0

    command = [sys.executable, "-m", "pytest", "-q", *STRUCTURAL_CONTRACTS]
    print("STAR structural performance contracts")
    print(" ".join(command))
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
