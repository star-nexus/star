#!/usr/bin/env python3
"""Build a compact, decision-grade evidence package beside a raw forensic ZIP.

The compact package is the default artifact for normal review / Agent / LLM use.
It never replaces the raw forensic package.  Instead it contains:

- complete point.json decision-grade payloads;
- experiment summary JSON(s);
- manifest and concise validation logs;
- SHA256 references for raw profile.json files;
- SHA256 + size reference for the immutable raw forensic ZIP;
- package-local SHA256SUMS.

The raw forensic ZIP remains the final audit substrate when a profiler, analyzer,
tail event, or alternative attribution must be re-examined.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

SCHEMA = "star-compact-evidence-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def build_compact(run_dir: Path, raw_zip: Path, output: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    raw_zip = raw_zip.resolve()
    output = output.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")
    if not raw_zip.is_file():
        raise FileNotFoundError(f"raw forensic ZIP not found: {raw_zip}")

    point_files = sorted(run_dir.glob("control/*/point.json")) + sorted(
        run_dir.glob("treatment/*/point.json")
    )
    if not point_files:
        raise RuntimeError("no control/treatment point.json evidence found")

    points: dict[str, Any] = {}
    for path in point_files:
        points[_relative(path.parent, run_dir)] = _load_json(path)

    raw_profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.glob("control/*/profile.json")) + sorted(
        run_dir.glob("treatment/*/profile.json")
    ):
        raw_profiles[_relative(path, run_dir)] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    summaries = sorted(run_dir.glob("*summary.json"))
    evidence = {
        "schema": SCHEMA,
        "role": "Compact Evidence Package",
        "purpose": (
            "Default decision-grade review artifact. The raw forensic package "
            "remains authoritative for low-level re-audit."
        ),
        "run_id": run_dir.name,
        "points": points,
        "raw_profiles": raw_profiles,
        "summary_files": [path.name for path in summaries],
    }

    raw_artifact = {
        "role": "Raw Forensic Package",
        "file": raw_zip.name,
        "sha256": sha256_file(raw_zip),
        "size_bytes": raw_zip.stat().st_size,
        "preservation_rule": (
            "Preserve permanently for forensic re-audit; compact evidence does not replace raw."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="star-compact-evidence-") as tmp:
        root = Path(tmp)
        (root / "evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (root / "raw-artifact.json").write_text(
            json.dumps(raw_artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        for path in summaries:
            shutil.copy2(path, root / path.name)

        preferred = (
            "manifest.txt",
            "treatment-contract-test.log",
            "control-targeted-regressions.log",
            "treatment-targeted-regressions.log",
        )
        for name in preferred:
            source = run_dir / name
            if source.is_file():
                shutil.copy2(source, root / name)

        checksum_lines = []
        for path in sorted(root.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                checksum_lines.append(f"{sha256_file(path)}  {path.name}")
        (root / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )

        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(root.iterdir()):
                if path.is_file():
                    archive.write(path, path.name)

    return {
        "compact_zip": str(output),
        "compact_sha256": sha256_file(output),
        "compact_size_bytes": output.stat().st_size,
        "raw_zip": str(raw_zip),
        "raw_sha256": raw_artifact["sha256"],
        "raw_size_bytes": raw_artifact["size_bytes"],
        "point_count": len(points),
        "raw_profile_count": len(raw_profiles),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--raw-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output = args.output
    if output is None:
        output = args.run_dir.with_name(args.run_dir.name + "-compact.zip")
    result = build_compact(args.run_dir, args.raw_zip, output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
