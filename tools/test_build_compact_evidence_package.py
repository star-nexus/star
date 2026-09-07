from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from tools.build_compact_evidence_package import build_compact


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_compact_package_keeps_decision_evidence_but_not_full_profiles(tmp_path):
    run_dir = tmp_path / "run-001"
    for variant in ("control", "treatment"):
        point_dir = run_dir / variant / "100pct-moving"
        point_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            point_dir / "point.json",
            {
                "ok": True,
                "guards": {"fog_fixed_on": True, "density_matches": True},
                "profile": {
                    "controlled_work_frame_ms": {"avg": 30.0, "p99": 32.0},
                    "sections": {"unit_visible_cull": {"inclusive_ms": 2.0}},
                },
            },
        )
        _write_json(
            point_dir / "profile.json",
            {
                "large_raw_history": list(range(100)),
                "sections": {"unit_visible_cull": {"inclusive_ms": 2.0}},
            },
        )

    _write_json(run_dir / "unitrender-e6-summary.json", {"decision": "PASS"})
    (run_dir / "manifest.txt").write_text("run_id=run-001\n", encoding="utf-8")
    (run_dir / "treatment-contract-test.log").write_text("2 passed\n", encoding="utf-8")
    (run_dir / "control-targeted-regressions.log").write_text("25 passed\n", encoding="utf-8")
    (run_dir / "treatment-targeted-regressions.log").write_text("25 passed\n", encoding="utf-8")

    raw_zip = tmp_path / "run-001-raw.zip"
    with zipfile.ZipFile(raw_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(run_dir.parent))

    compact_zip = tmp_path / "run-001-compact.zip"
    result = build_compact(run_dir, raw_zip, compact_zip)

    assert result["point_count"] == 2
    assert result["raw_profile_count"] == 2
    assert result["raw_sha256"] == _sha256(raw_zip)
    assert result["compact_sha256"] == _sha256(compact_zip)

    with zipfile.ZipFile(compact_zip) as archive:
        names = set(archive.namelist())
        assert "evidence.json" in names
        assert "raw-artifact.json" in names
        assert "SHA256SUMS" in names
        assert "unitrender-e6-summary.json" in names
        assert not any(name.endswith("profile.json") for name in names)
        assert not any(name.endswith("point.json") for name in names)

        evidence = json.loads(archive.read("evidence.json"))
        raw_artifact = json.loads(archive.read("raw-artifact.json"))
        checksums = archive.read("SHA256SUMS").decode("utf-8")

    assert evidence["schema"] == "star-compact-evidence-v1"
    assert set(evidence["points"]) == {
        "control/100pct-moving",
        "treatment/100pct-moving",
    }
    assert set(evidence["raw_profiles"]) == {
        "control/100pct-moving/profile.json",
        "treatment/100pct-moving/profile.json",
    }
    assert raw_artifact["sha256"] == _sha256(raw_zip)
    assert raw_artifact["size_bytes"] == raw_zip.stat().st_size
    assert "evidence.json" in checksums
    assert "raw-artifact.json" in checksums
