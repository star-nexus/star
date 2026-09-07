#!/usr/bin/env python3
"""Phase-5 UnitRender E6: derived world-geometry reuse attribution.

Experimental treatment only, run against the exact retained production baseline.
The treatment changes one mechanism: UnitSpatialIndex._record_for_hex() reuses
long-lived per-hex derived geometry payload objects (world_x, world_y, bucket)
while continuing to allocate a fresh UnitSpatialRecord for every refresh.

This intentionally does NOT reuse UnitSpatialRecord identity (E5-2), change the
record dataclass layout (E5-1), alter Cull, or rewrite spatial containers.
"""

from __future__ import annotations

import subprocess
import sys
from math import floor
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

EXPECTED_RUNTIME_SHA = "17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a"
EXPECTED_BLOBS = {
    "rotk_env/utils/unit_spatial_index.py": "2c2fb26c6ae5f422516a6c3927049d8a78a72b32",
    "rotk_env/systems/window_unit_render_system.py": "b995df231c5e10d901b129f95716bfb0f30043eb",
}
_CACHE_ATTR = "_phase5_e6_geometry_cache"


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=_REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _verify_source_contract() -> None:
    runtime_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True
    ).strip()
    if runtime_sha != EXPECTED_RUNTIME_SHA:
        raise RuntimeError(
            "Phase-5 UnitRender E6 requires exact retained production baseline "
            f"{EXPECTED_RUNTIME_SHA}, got {runtime_sha}."
        )

    drift = []
    for path, expected in EXPECTED_BLOBS.items():
        full = _REPO_ROOT / path
        if not full.is_file():
            drift.append(f"{path}: missing")
            continue
        actual = _git_blob(path)
        if actual != expected:
            drift.append(f"{path}: expected {expected}, got {actual}")
    if drift:
        raise RuntimeError(
            "Phase-5 UnitRender E6 source guard failed; do not override it:\n  - "
            + "\n  - ".join(drift)
        )


def _install_geometry_reuse_patch() -> None:
    from rotk_env.utils.unit_spatial_index import UnitSpatialIndex, UnitSpatialRecord

    original = UnitSpatialIndex._record_for_hex
    if getattr(original, "_phase5_e6_geometry_reuse", False):
        return

    def geometry_reuse_record_for_hex(self, col: int, row: int, faction):
        cache = getattr(self, _CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(self, _CACHE_ATTR, cache)

        key = (col, row)
        geometry = cache.get(key)
        if geometry is None:
            world_x, world_y = self.hex_converter.hex_to_pixel(col, row)
            world_x = float(world_x)
            world_y = float(world_y)
            bucket = (
                floor(world_x / self.bucket_size),
                floor(world_y / self.bucket_size),
            )
            geometry = (world_x, world_y, bucket)
            cache[key] = geometry

        world_x, world_y, bucket = geometry
        return UnitSpatialRecord(
            col=col,
            row=row,
            faction=faction,
            world_x=world_x,
            world_y=world_y,
            bucket=bucket,
        )

    geometry_reuse_record_for_hex._phase5_e6_geometry_reuse = True
    geometry_reuse_record_for_hex._phase5_e6_original = original
    UnitSpatialIndex._record_for_hex = geometry_reuse_record_for_hex


def _install() -> None:
    _verify_source_contract()

    import rotk_env.main as env_main
    from framework.ecs import profiling as ecs_profiling

    _install_geometry_reuse_patch()
    ecs_profiling.profiler.set_metadata(
        phase5_unitrender_e6_attribution=True,
        phase5_unitrender_e6_runtime_sha=EXPECTED_RUNTIME_SHA,
        phase5_unitrender_e6_source_guard=EXPECTED_BLOBS,
        phase5_unitrender_e6_treatment="per_hex_derived_world_geometry_reuse",
        phase5_unitrender_e6_fresh_record_identity_preserved=True,
        phase5_unitrender_e6_record_layout_unchanged=True,
        phase5_unitrender_e6_cull_algorithm_unchanged=True,
        phase5_unitrender_e6_bucket_containers_unchanged=True,
        phase5_unitrender_e6_scope="derived_world_geometry_reuse_attribution",
        phase5_unitrender_e6_cache_boundedness="attribution_only_not_production_decision",
        phase5_unitrender_e6_aggregate_frame_latency="diagnostic_only",
    )
    env_main.main()


def main() -> int:
    _install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
