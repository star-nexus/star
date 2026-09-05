"""Structural checks for the explicit Phase-4 production-path scale harness."""

from __future__ import annotations

import importlib.util
import os
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from rotk_env.main import game_scene_kwargs_from_args
from rotk_env.testing.scale_harness import ScaleHarnessSystem
from rotk_env.utils.hex_utils import HexMath


def test_static_route_is_deterministic_passable_adjacent_walk():
    board = set(HexMath.hex_in_range(0, 0, 4))
    route_a = ScaleHarnessSystem._static_route(
        (0, 0),
        route_steps=12,
        rng=random.Random(42),
        board=board,
        impassable=set(),
    )
    route_b = ScaleHarnessSystem._static_route(
        (0, 0),
        route_steps=12,
        rng=random.Random(42),
        board=board,
        impassable=set(),
    )

    assert route_a == route_b
    assert len(route_a) == 13
    assert all(cell in board for cell in route_a)
    assert all(HexMath.hex_distance(a, b) == 1 for a, b in zip(route_a, route_a[1:]))


def test_static_route_never_enters_impassable_cell():
    board = set(HexMath.hex_in_range(0, 0, 3))
    blocked = {(1, 0), (0, 1)}
    route = ScaleHarnessSystem._static_route(
        (0, 0),
        route_steps=20,
        rng=random.Random(7),
        board=board,
        impassable=blocked,
    )
    assert not (set(route) & blocked)


def test_sustained_path_expands_without_per_frame_harness_work():
    class _World:
        @staticmethod
        def get_component(entity, component_type):
            return None

    harness = ScaleHarnessSystem("/tmp/not-opened.sock")
    harness.world = _World()
    path = harness._build_sustained_path(
        1,
        ((0, 0), (1, 0), (1, 1)),
        duration_seconds=2.5,
    )
    # Default animation speed is 2 tiles/s: ceil(2.5 * 2) = 5 targets.
    assert path is not None
    assert len(path) == 6
    assert path[0] == (0, 0)


def test_existing_runtime_args_do_not_need_scale_field():
    args = SimpleNamespace(
        players="human_vs_two_ai",
        mode="real_time",
        headless=False,
        scenario="default",
        seed=42,
        no_hub=True,
        hub_url=None,
        env_id=None,
        mock_ai=False,
    )
    kwargs = game_scene_kwargs_from_args(args)
    assert kwargs["scale_harness_socket"] is None


def test_scale_driver_entrypoint_works_outside_repo_cwd(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "scale_driver.py"
    env = os.environ.copy()
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "production-path system-scale harness" in result.stdout


def test_formal_density_point_defaults_to_accepted_realtime_gc_policy():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "scale_driver.py"
    spec = importlib.util.spec_from_file_location("star_scale_driver_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    density_args = module.parse_args(
        ["density-point", "--density", "0.25", "--profile", "/tmp/profile.json"]
    )
    manual_args = module.parse_args(["start"])

    assert density_args.gc_policy == "realtime_defer"
    assert manual_args.gc_policy == "auto"
