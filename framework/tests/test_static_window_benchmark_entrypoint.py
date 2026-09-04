"""Entrypoint regression for the standalone visible-window benchmark runner."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_window_benchmark_direct_script_help_from_outside_repo(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "run_static_window_benchmark.py"
    env = os.environ.copy()
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "deterministic STAR visible-window performance workload" in result.stdout
    assert "static-window-v1" in result.stdout
    assert "one-mover-v1" in result.stdout
