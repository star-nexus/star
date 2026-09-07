#!/usr/bin/env python3
"""Phase-5 UnitRender E6-2: slotted-record composition attribution.

Treatment runs against the exact retained E6-1 production state and changes one
mechanism only: ``UnitSpatialRecord`` is redefined with ``slots=True`` while
keeping the E6-1 board-bounded geometry ownership unchanged.

This is a composition experiment, not a production KEEP by itself.  A positive
result justifies the trivial one-line production candidate for a later source
A/B validation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

EXPECTED_RUNTIME_SHA = "e7ba18b31870577110b591104ef8fa7b4713e43c"
EXPECTED_BLOBS = {
    "rotk_env/utils/unit_spatial_index.py": "24236fb1db40ddb79744e499d16b279745e8ddb4",
    "rotk_env/systems/window_unit_render_system.py": "b995df231c5e10d901b129f95716bfb0f30043eb",
}


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
            "Phase-5 UnitRender E6-2 requires exact retained E6-1 production "
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
            "Phase-5 UnitRender E6-2 source guard failed; do not override it:\n  - "
            + "\n  - ".join(drift)
        )


def _install_slotted_record_patch() -> None:
    import rotk_env.utils.unit_spatial_index as spatial

    current = spatial.UnitSpatialRecord
    if getattr(current, "_phase5_e6_2_slotted", False):
        return

    # Execute the exact source-level representation change in the owning module
    # namespace.  Existing functions resolve UnitSpatialRecord through that
    # module global at runtime, so all records created after this point use the
    # slotted frozen dataclass.  The patch is installed before world creation.
    exec(
        """@dataclass(frozen=True, slots=True)\n"
        "class UnitSpatialRecord:\n"
        "    col: int\n"
        "    row: int\n"
        "    faction: Faction\n"
        "    world_x: float\n"
        "    world_y: float\n"
        "    bucket: Bucket\n",
        spatial.__dict__,
    )
    patched = spatial.UnitSpatialRecord
    patched._phase5_e6_2_slotted = True
    patched._phase5_e6_2_original = current


def _install() -> None:
    _verify_source_contract()

    import rotk_env.main as env_main
    from framework.ecs import profiling as ecs_profiling

    _install_slotted_record_patch()
    ecs_profiling.profiler.set_metadata(
        phase5_unitrender_e6_2_attribution=True,
        phase5_unitrender_e6_2_runtime_sha=EXPECTED_RUNTIME_SHA,
        phase5_unitrender_e6_2_source_guard=EXPECTED_BLOBS,
        phase5_unitrender_e6_2_treatment="slotted_unit_spatial_record_on_e6_1",
        phase5_unitrender_e6_2_e6_1_geometry_ownership_preserved=True,
        phase5_unitrender_e6_2_fresh_record_identity_preserved=True,
        phase5_unitrender_e6_2_record_fields_unchanged=True,
        phase5_unitrender_e6_2_cull_algorithm_unchanged=True,
        phase5_unitrender_e6_2_spatial_containers_unchanged=True,
        phase5_unitrender_e6_2_scope="composition_attribution",
        phase5_unitrender_e6_2_positive_is_not_production_keep=True,
    )
    env_main.main()


def main() -> int:
    _install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
