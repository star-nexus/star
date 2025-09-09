"""
Romance of the Three Kingdoms Strategy Game

Usage:
    python main.py [Options]

Options:
    --mode [turn_based|real_time]  Game mode (default: turn_based)
    --scenario [default|chibi|three_kingdoms]  Game scenario (default: default)
    --players [human_vs_ai|ai_vs_ai|three_kingdoms]  Player configuration (default: human_vs_ai)
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

from framework.engine.game_engine import GameEngine

from rotk_env.scenes import GameScene, GameOverScene, StartScene
from rotk_env.prefabs.config import Faction, PlayerType


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Romance of the Three Kingdoms Strategy Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Game description:
  This is a turn-based strategy game set on a hexagonal map, supporting both human and AI opponents. The game features a variety of terrain types, each affecting units in unique ways to add strategic depth.

Controls:
  Left Mouse Button: Select unit / Move / Attack
  Right Mouse Button: Deselect
  WASD or Arrow Keys: Move camera
  V: Toggle coordinate display
  Spacebar: End turn
  Tab: Show/Hide statistics
  F1: Show/Hide help
  ESC: Cancel selection

Victory Conditions:
  Eliminate all enemy units, or achieve the highest score by the end of the game.
        """,
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Skip start scene, enter game directly, auto end, suitable for automation testing or server environment",
    )

    parser.add_argument(
        "--mode",
        choices=["turn_based", "real_time"],
        default="turn_based",
        help="Game mode (default: turn_based)",
    )

    parser.add_argument(
        "--scenario",
        choices=["default", "chibi", "three_kingdoms"],
        default="default",
        help="Game scenario (default: default)",
    )

    parser.add_argument(
        "--players",
        choices=["human_vs_ai", "ai_vs_ai", "three_kingdoms"],
        default="human_vs_ai",
        help="Player configuration (default: human_vs_ai)",
    )

    return parser.parse_args()


def create_game_from_args(args):
    """Create game from arguments"""
    players_config = {
        "human_vs_ai": {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
        "ai_vs_ai": {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        "three_kingdoms": {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
    }

    return players_config.get(
        args.players, {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
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
    try:
        # Parse command line arguments
        args = parse_arguments()

        # Display welcome message
        print_welcome()

        # Create game engine
        engine = GameEngine(
            title="Romance of the Three Kingdoms Strategy Game",
            width=1200,
            height=800,
            fps=60,
        )

        # Register game scenes
        engine.scene_manager.register_scene("start", StartScene)
        engine.scene_manager.register_scene("game", GameScene)
        engine.scene_manager.register_scene("game_over", GameOverScene)

        # Determine initial scene based on command line arguments
        if args.headless:
            # If start scene is skipped, enter game scene directly
            os.environ["SDL_VIDEODRIVER"] = "dummy"

            # Get player configuration
            players_config = create_game_from_args(args)

            # Set initial scene, pass parameters
            engine.scene_manager.switch_to(
                "game", players=players_config, game_mode=args.mode, headless=True
            )

            print(f"Game mode: {args.mode}")
            print(f"Player configuration: {args.players}")
            print(f"Game scenario: {args.scenario}")
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
        pygame.quit()
        print("Game Over")


if __name__ == "__main__":
    main()
