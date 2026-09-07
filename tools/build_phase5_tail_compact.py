#!/usr/bin/env python3
"""Build the standard two-tier Compact package for E7 repeat-* layout."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "star-compact-evidence-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(run_dir: Path, raw_zip: Path, output: Path) -> dict:
    run_dir = run_dir.resolve(); raw_zip = raw_zip.resolve(); output = output.resolve()
    point_files = sorted(run_dir.glob("repeat-*/point.json"))
    profile_files = sorted(run_dir.glob("repeat-*/profile.json"))
    if len(point_files) != 3 or len(profile_files) != 3:
        raise RuntimeError(f"E7 compact requires exactly 3 points/profiles, got {len(point_files)}/{len(profile_files)}")
    if not raw_zip.is_file():
        raise FileNotFoundError(raw_zip)

    points = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in point_files
    }
    raw_profiles = {
        path.relative_to(run_dir).as_posix(): {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in profile_files
    }
    summaries = sorted(run_dir.glob("*summary.json"))
    evidence = {
        "schema": SCHEMA,
        "role": "Compact Evidence Package",
        "purpose": "Default decision-grade review artifact; Raw remains authoritative for forensic re-audit.",
        "run_id": run_dir.name,
        "points": points,
        "raw_profiles": raw_profiles,
        "summary_files": [p.name for p in summaries],
    }
    raw_artifact = {
        "role": "Raw Forensic Package",
        "file": raw_zip.name,
        "sha256": sha256_file(raw_zip),
        "size_bytes": raw_zip.stat().st_size,
        "preservation_rule": "Preserve permanently; compact evidence does not replace raw.",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="star-e7-compact-") as tmp:
        root = Path(tmp)
        (root / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (root / "raw-artifact.json").write_text(json.dumps(raw_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for path in summaries:
            shutil.copy2(path, root / path.name)
        for name in ("manifest.txt", "source-guards.json", "tail-contract-test.log", "targeted-regressions.log"):
            path = run_dir / name
            if path.is_file(): shutil.copy2(path, root / name)
        lines = [
            f"{sha256_file(path)}  {path.name}"
            for path in sorted(root.iterdir()) if path.is_file() and path.name != "SHA256SUMS"
        ]
        (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(root.iterdir()):
                if path.is_file(): archive.write(path, path.name)

    return {
        "compact_zip": str(output),
        "compact_sha256": sha256_file(output),
        "compact_size_bytes": output.stat().st_size,
        "raw_zip": str(raw_zip),
        "raw_sha256": raw_artifact["sha256"],
        "raw_size_bytes": raw_artifact["size_bytes"],
        "point_count": len(point_files),
        "raw_profile_count": len(profile_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--raw-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.run_dir, args.raw_zip, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
