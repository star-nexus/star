"""Run deterministic visible-window STAR performance workloads.

The runner reuses the production engine and scene stack, blocks local gameplay
input, keeps SDL pumping/presentation active, and stops automatically. Two small
workloads are supported:

* ``static-window-v1`` keeps the world unchanged through the measured window.
* ``one-mover-v1`` issues one real MovementSystem order at the start of the
  measured window so animation, committed hex changes, Vision and Fog deltas are
  exercised without human timing noise.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pygame

from performance_profiler import profiler
from rotk_env.components import HexPosition, MovementPoints, Unit, UnitCount
from rotk_env.main import (
    GameConfig,
    GameEngine,
    GameOverScene,
    GameScene,
    StartScene,
    game_scene_kwargs_from_args,
)
from rotk_env.prefabs.config import Faction
from rotk_env.utils.hex_utils import HexMath
from rotk_env.utils.map_query import reachable_hexes


STATIC_WORKLOAD_ID = "static-window-v1"
ONE_MOVER_WORKLOAD_ID = "one-mover-v1"
WORKLOAD_IDS = (STATIC_WORKLOAD_ID, ONE_MOVER_WORKLOAD_ID)
DEFAULT_DURATION_S = 12.0
DEFAULT_MEASUREMENT_DURATION_S = 5.0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic STAR visible-window performance workload"
    )
    parser.add_argument(
        "--workload",
        choices=WORKLOAD_IDS,
        default=STATIC_WORKLOAD_ID,
        help="Workload to run. Default: static-window-v1.",
    )
    parser.add_argument(
        "--uncapped",
        action="store_true",
        help="Disable the production FPS limiter for throughput measurement.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help="Total wall-clock run duration including startup/warm-up. Default: 12s.",
    )
    parser.add_argument(
        "--measurement-duration",
        type=float,
        default=DEFAULT_MEASUREMENT_DURATION_S,
        help="Final measured interval. Default: 5s, matching the profiler horizon.",
    )
    parser.add_argument(
        "--profile-json",
        type=str,
        default=None,
        metavar="PATH",
        help="Enable silent profiling and write the final rolling profile JSON.",
    )
    parser.add_argument(
        "--summary-json",
        type=str,
        required=True,
        metavar="PATH",
        help="Write whole-run and measured-window throughput here.",
    )
    return parser


def _runtime_args(*, uncapped: bool) -> SimpleNamespace:
    return SimpleNamespace(
        players="human_vs_two_ai",
        mode="real_time",
        headless=False,
        scenario="default",
        seed=42,
        no_hub=True,
        hub_url=None,
        env_id=None,
        mock_ai=False,
        uncapped=uncapped,
    )


def _block_gameplay_input_events() -> None:
    """Block local gameplay input without disabling SDL's native event pump."""
    pygame.event.set_blocked(
        [
            pygame.KEYDOWN,
            pygame.KEYUP,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEWHEEL,
        ]
    )


def _movement_system(world):
    return next(
        (system for system in world.systems if system.__class__.__name__ == "MovementSystem"),
        None,
    )


def _select_one_mover_plan(scene: GameScene) -> tuple[int, tuple[int, int]]:
    """Pick one deterministic, long legal move from the production move rules.

    This is benchmark setup and therefore runs during warm-up, outside the
    measured interval. The candidate with the largest hex displacement wins.
    Remaining ties prefer larger spendable MP and then entity id.
    """
    world = scene.world
    plans: list[tuple[int, int, int, tuple[int, int]]] = []

    for entity in sorted(world.query().with_component(Unit).entities()):
        unit = world.get_component(entity, Unit)
        if unit is None or unit.faction != Faction.WEI:
            continue
        pos = world.get_component(entity, HexPosition)
        mp = world.get_component(entity, MovementPoints)
        count = world.get_component(entity, UnitCount)
        if pos is None or mp is None or count is None:
            continue

        spendable = mp.spendable(count)
        if spendable <= 0:
            continue
        start = (pos.col, pos.row)
        legal = reachable_hexes(world, start, spendable, mover=entity)
        if not legal:
            continue
        target = max(
            legal,
            key=lambda cell: (HexMath.hex_distance(start, cell), cell[0], cell[1]),
        )
        distance = HexMath.hex_distance(start, target)
        plans.append((distance, spendable, entity, target))

    if not plans:
        raise RuntimeError("one-mover-v1 found no legal Wei movement plan")

    _, _, entity, target = max(plans, key=lambda item: (item[0], item[1], item[2]))
    return entity, target


def _prepare_one_mover_plan(engine: GameEngine) -> tuple[int, tuple[int, int]] | None:
    scene = engine.current_scene
    if not isinstance(scene, GameScene) or not scene.initialized:
        return None
    return _select_one_mover_plan(scene)


def _issue_one_mover(
    engine: GameEngine,
    plan: tuple[int, tuple[int, int]],
) -> dict[str, object]:
    """Issue the precomputed canonical move through production MovementSystem."""
    scene = engine.current_scene
    if not isinstance(scene, GameScene) or not scene.initialized:
        raise RuntimeError("one-mover-v1 lost GameScene before move issue")

    movement = _movement_system(scene.world)
    if movement is None:
        raise RuntimeError("one-mover-v1 requires MovementSystem")

    entity, target = plan
    pos = scene.world.get_component(entity, HexPosition)
    if pos is None:
        raise RuntimeError(f"one-mover-v1 mover {entity} has no HexPosition")
    start = (pos.col, pos.row)

    # Only the production move order is measured. Benchmark candidate search was
    # completed during warm-up and cannot inflate STAR-controlled timings.
    with profiler.time_system("benchmark_move_order", category="work"):
        result = movement.move_unit(entity, target)
    if not result.get("success"):
        raise RuntimeError(f"one-mover-v1 move rejected: {result}")

    details: dict[str, object] = {
        "entity": entity,
        "from": [start[0], start[1]],
        "to": [target[0], target[1]],
        "path_length": len(result.get("path") or []),
        "cost": result.get("cost"),
    }
    profiler.set_metadata(
        benchmark_mover_entity=entity,
        benchmark_move_from=f"{start[0]},{start[1]}",
        benchmark_move_to=f"{target[0]},{target[1]}",
        benchmark_move_path_length=details["path_length"],
        benchmark_move_cost=details["cost"],
    )
    return details


def run(args: argparse.Namespace) -> dict[str, object]:
    duration_s = max(6.0, float(args.duration))
    measurement_duration_s = float(args.measurement_duration)
    if measurement_duration_s <= 0.0:
        raise ValueError("--measurement-duration must be > 0")
    if measurement_duration_s >= duration_s:
        raise ValueError("--measurement-duration must be shorter than --duration")

    workload = str(args.workload)
    warmup_duration_s = duration_s - measurement_duration_s
    profile_enabled = bool(args.profile_json)
    measurement_scope = (
        "final_steady_state_window"
        if workload == STATIC_WORKLOAD_ID
        else "final_measurement_window"
    )

    profiler.enabled = profile_enabled
    profiler.enable_profiler = False
    profiler.reset()
    profiler.set_metadata(
        benchmark_workload=workload,
        benchmark_input_policy="blocked_gameplay_events",
        benchmark_duration_s=duration_s,
        benchmark_measurement_duration_s=measurement_duration_s,
        benchmark_summary_scope=measurement_scope,
        benchmark_uncapped=bool(args.uncapped),
    )

    runtime_args = _runtime_args(uncapped=bool(args.uncapped))
    engine = GameEngine(
        title=f"STAR Performance Benchmark — {workload}",
        fps=GameConfig.FPS,
        uncapped=bool(args.uncapped),
    )
    GameConfig.WINDOW_WIDTH = engine.width
    GameConfig.WINDOW_HEIGHT = engine.height

    engine.scene_manager.register_scene("start", StartScene)
    engine.scene_manager.register_scene("game", GameScene)
    engine.scene_manager.register_scene("game_over", GameOverScene)
    engine.scene_manager.switch_to(
        "start",
        auto_start_config=game_scene_kwargs_from_args(runtime_args),
    )
    _block_gameplay_input_events()

    frame_count = 0
    measurement_frame_count = 0
    measurement_start_at = 0.0
    measurement_end_at = 0.0
    one_mover_plan: tuple[int, tuple[int, int]] | None = None
    one_mover_details: dict[str, object] | None = None
    original_update = engine._update

    def counted_update() -> None:
        nonlocal frame_count, measurement_frame_count, one_mover_plan, one_mover_details
        now = time.perf_counter()
        frame_count += 1

        if workload == ONE_MOVER_WORKLOAD_ID and now < measurement_start_at:
            if one_mover_plan is None:
                one_mover_plan = _prepare_one_mover_plan(engine)

        if measurement_start_at <= now < measurement_end_at:
            measurement_frame_count += 1
            if workload == ONE_MOVER_WORKLOAD_ID and one_mover_details is None:
                if one_mover_plan is None:
                    raise RuntimeError(
                        "one-mover-v1 plan was not prepared during warm-up"
                    )
                one_mover_details = _issue_one_mover(engine, one_mover_plan)

        original_update()

    # Present in every workload/profiler mode so harness overhead stays symmetric.
    engine._update = counted_update  # type: ignore[method-assign]

    stop_timer = threading.Timer(duration_s, lambda: engine.stop(None))
    stop_timer.daemon = True

    started_at = time.perf_counter()
    measurement_start_at = started_at + warmup_duration_s
    measurement_end_at = started_at + duration_s
    stop_timer.start()
    try:
        engine.start()
    finally:
        ended_at = time.perf_counter()
        elapsed_s = max(0.0, ended_at - started_at)
        stop_timer.cancel()

    if workload == ONE_MOVER_WORKLOAD_ID and one_mover_details is None:
        raise RuntimeError("one-mover-v1 never issued its movement order")

    measurement_elapsed_s = max(
        0.0,
        min(ended_at, measurement_end_at) - measurement_start_at,
    )

    summary: dict[str, object] = {
        "workload": workload,
        "duration_target_s": duration_s,
        "elapsed_s": elapsed_s,
        "frame_count": frame_count,
        "throughput_fps": (frame_count / elapsed_s) if elapsed_s > 0.0 else 0.0,
        "throughput_scope": "whole_benchmark_including_startup",
        "warmup_duration_target_s": warmup_duration_s,
        "measurement_duration_target_s": measurement_duration_s,
        "measurement_elapsed_s": measurement_elapsed_s,
        "measurement_frame_count": measurement_frame_count,
        "measurement_throughput_fps": (
            measurement_frame_count / measurement_elapsed_s
            if measurement_elapsed_s > 0.0
            else 0.0
        ),
        "measurement_scope": measurement_scope,
        "profiler_enabled": profile_enabled,
        "uncapped": bool(args.uncapped),
        "scenario": "default",
        "seed": 42,
        "players": "human_vs_two_ai",
        "hub": "offline",
        "mock_ai": False,
        "input_policy": "blocked_gameplay_events",
    }
    if one_mover_details is not None:
        summary["one_mover"] = one_mover_details

    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    if args.profile_json:
        profile_path = Path(args.profile_json)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profiler.write_json(profile_path)

    print(json.dumps(summary, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        run(args)
        return 0
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
