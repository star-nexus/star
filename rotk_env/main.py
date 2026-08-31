"""
Romance of the Three Kingdoms Strategy Game

Usage:
    python main.py [Options]

Options:
    --mode [turn_based|real_time]  Game mode (default: turn_based)
    --scenario [default|chibi|three_kingdoms]  Game scenario (default: default)
    --players [human_vs_ai|ai_vs_ai|three_kingdoms|human_vs_two_ai]  Player configuration (default: human_vs_ai)
    --skip-start  Skip the start UI and apply --players/--mode/--scenario
    --headless  Skip start UI, dummy display, auto end (eval / CI)
    --hub-url URL  Hub websocket (default: ws://localhost:8000/ws/metaverse)
    --no-hub  Do not connect to a Hub (offline BOT / rules tests)
    --profile  Print Performance Profiler v2 stats every ~5 seconds
    --profile-json PATH  Write the final rolling profiler snapshot as JSON
    --help  Show help information
"""

import sys
import os
import argparse
import pygame
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Add framework to path
sys.path.append(str(Path(__file__).parent.parent / "framework"))

from framework import set_profiler
from framework.engine.game_engine import GameEngine
from performance_profiler import profiler

# The ECS core ships a no-op profiler so it stays free of repo-root imports.
# The ENV entry point is the layer that knows about `performance_profiler`.
set_profiler(profiler)

from rotk_env.scenes import GameScene, GameOverScene, StartScene
from rotk_env.prefabs.config import PLAYER_PRESETS, GameConfig
from rotk_env.prefabs.controls import format_cli_controls
from rotk_env.prefabs.world_builder import DEFAULT_HUB_URL


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Romance of the Three Kingdoms Strategy Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Game description:
  This is a turn-based strategy game set on a hexagonal map, supporting both human and AI opponents. The game features a variety of terrain types, each affecting units in unique ways to add strategic depth.

{format_cli_controls()}

Victory Conditions:
  Annihilate every opposing unit to win. Being wiped is a loss.
  A draw is called if every living unit on the field dies at once, or when
  the clock expires (turn-based: after 100 turns; real-time: 3600 seconds).
        """,
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Skip start scene, dummy display, auto end (eval / CI). Still connects to Hub unless --no-hub.",
    )
    parser.add_argument(
        "--hub-url",
        type=str,
        default=None,
        help=(
            "Hub websocket URL. Default is "
            f"{DEFAULT_HUB_URL}. Overridden by --no-hub. "
            "Also reads $STAR_HUB_URL when this flag is omitted."
        ),
    )
    parser.add_argument(
        "--no-hub",
        action="store_true",
        default=False,
        help="Do not open a Hub websocket. Rule BOT still plays; LLM agents cannot join.",
    )
    parser.add_argument(
        "--skip-start",
        action="store_true",
        default=False,
        help="Skip start UI and apply --players/--mode/--scenario with a visible window",
    )

    parser.add_argument(
        "--mode",
        choices=["turn_based", "real_time"],
        default="turn_based",
        help="Game mode (default: turn_based)",
    )
    parser.add_argument(
        "--scenario",
        default="default",
        help=(
            "Map to load from rotk_env/maps/. "
            "default/three_kingdoms → river_split.json; "
            "any other name loads <name>.json in that folder."
        ),
    )

    parser.add_argument(
        "--players",
        choices=["human_vs_ai", "ai_vs_ai", "three_kingdoms", "human_vs_two_ai"],
        default="human_vs_ai",
        help="Player configuration (default: human_vs_ai). three_kingdoms is AI/AI/AI for eval.",
    )

    parser.add_argument(
        "--env-id",
        type=str,
        default=None,
        help="Environment ID for Hub/WebSocket (default: env_1, or ENV_ID env var if set)",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Root RNG seed for reproducibility. Wires through map generation, "
            "combat rolls, terrain/skill events, and visual particles. "
            "Resolution priority: --seed > $STAR_SEED > .configs.toml[default].seed > wall-clock."
        ),
    )

    parser.add_argument(
        "--profile",
        action="store_true",
        default=False,
        help=(
            "Enable STAR Performance Profiler v2 console output. Reports "
            "exclusive/inclusive timings, frame percentiles, present time, "
            "and FPS-cap waiting separately."
        ),
    )
    parser.add_argument(
        "--profile-json",
        type=str,
        default=None,
        metavar="PATH",
        help="Write the final rolling Performance Profiler v2 snapshot to PATH as JSON.",
    )

    return parser.parse_args()


def resolve_hub_url(args) -> str | None:
    """Pick the Hub URL. --no-hub wins; otherwise --hub-url, $STAR_HUB_URL, default."""
    if args.no_hub:
        return None
    if args.hub_url:
        return args.hub_url
    env_url = os.environ.get("STAR_HUB_URL")
    if env_url:
        return env_url
    return DEFAULT_HUB_URL


def create_game_from_args(args):
    """Create game from arguments"""
    return PLAYER_PRESETS.get(
        args.players, PLAYER_PRESETS["human_vs_ai"]
    )


def print_welcome():
    """Display welcome message"""
    print("\n" + "=" * 60)
    print("  Romance of the Three Kingdoms Strategy Game")
    print("=" * 60)
    print("\nA hex-based turn-based strategy game powered by a modern framework.")
    print("\nGame Features:")
    print("  ✓ Hexagonal map system for deep tactical play")
    print("  ✓ Diverse terrain effects influencing strategy")
    print("  ✓ Fog of war for realistic battlefield uncertainty")
    print("  ✓ Play as AI or human, or both")
    print("  ✓ Detailed game statistics and analytics")
    print("  ✓ Classic turn-based strategy mechanics")
    print("\nLaunching the game, please wait...")


def main():
    """Main game function"""
    args = None
    try:
        args = parse_arguments()

        # Collection is opt-in so normal runs do not pay profiler timing/deque
        # overhead. JSON-only runs collect silently; --profile additionally
        # enables periodic console output.
        profiler.enabled = args.profile or bool(args.profile_json)
        profiler.enable_profiler = args.profile
        profiler.set_metadata(
            mode=args.mode,
            scenario=args.scenario,
            players=args.players,
        )

        # --env-id 优先于环境变量 ENV_ID，便于 auto_test 等通过 CLI 显式传入
        if args.env_id is not None:
            os.environ["ENV_ID"] = args.env_id

        # Display welcome message
        print_welcome()

        if args.headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["HEADLESS"] = "1"

        # Create game engine
        engine = GameEngine(
            title="Romance of the Three Kingdoms Strategy Game",
            fps=GameConfig.FPS,
        )
        if not args.headless:
            GameConfig.WINDOW_WIDTH = engine.width
            GameConfig.WINDOW_HEIGHT = engine.height

        # Register game scenes
        engine.scene_manager.register_scene("start", StartScene)
        engine.scene_manager.register_scene("game", GameScene)
        engine.scene_manager.register_scene("game_over", GameOverScene)

        # Determine initial scene based on command line arguments
        if args.headless or args.skip_start:
            players_config = create_game_from_args(args)
            hub_url = resolve_hub_url(args)
            engine.scene_manager.switch_to(
                "game",
                players=players_config,
                mode=args.mode,
                headless=args.headless,
                scenario=args.scenario,
                seed=args.seed,
                seed_source="cli" if args.seed is not None else "default",
                hub_url=hub_url,
                env_id=args.env_id,
            )

            print(f"Game mode: {args.mode}")
            print(f"Player configuration: {args.players}")
            print(f"Game scenario: {args.scenario}")
            if hub_url is None:
                print("Hub: offline (--no-hub)")
            else:
                print(f"Hub URL: {hub_url}")
            if args.env_id is not None:
                print(f"Environment ID: {args.env_id}")
            if args.seed is not None:
                print(f"Root seed: {args.seed}")
            if args.profile:
                print("Performance Profiler v2: enabled")

        else:
            # Default to start scene
            engine.scene_manager.switch_to("start")
            print("Enter game configuration interface...")

        print("Game started! Configure the game in the start interface, then click start game.")

        # Start game
        engine.start()

    except KeyboardInterrupt:
        print("\nGame interrupted by user")
    except Exception as e:
        print(f"\nGame running error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if args is not None and args.profile_json:
            try:
                profiler.write_json(args.profile_json)
                print(f"Performance profile written to: {args.profile_json}")
            except Exception as e:
                print(f"Warning: Failed to write performance profile: {e}")
        pygame.quit()
        print("Game Over")


if __name__ == "__main__":
    main()
