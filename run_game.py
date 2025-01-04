# game.py
import pygame
import argparse
from map_generator.map import MapGenerator
from game.game_system import TwoForcesEncounter
from ai_controller import AIController


class GameSettings:
    def __init__(self, args):
        # Map settings
        self.map_width = 25
        self.map_height = 25
        self.tile_size = 32

        # Window settings
        self.window_width = self.map_width * self.tile_size
        self.window_height = self.map_height * self.tile_size

        # Game state
        if args.ai:
            self.player_mode = "ai"
        else:
            self.player_mode = "human"
        self.vision_mode = 1
        self.winner = None
        self.show_mouse_pos = True

        # Frame settings
        self.save_interval = 300
        self.action_interval = 30


class Game:
    def __init__(self, settings: GameSettings):
        self.settings = settings
        self.init_pygame()

    def init_pygame(self):
        """Initialize Pygame and set up the display."""
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.settings.window_width, self.settings.window_height)
        )
        pygame.display.set_caption("Romance-of-the-Three-Kingdoms")
        self.font = pygame.font.SysFont(None, 24)
        self.win_font = pygame.font.SysFont(None, 72)

    def quit_pygame(self):
        """Quit pygame."""
        pygame.quit()


class GameController:
    def __init__(self, settings: GameSettings, environment_map, unit_map):
        self.settings = settings
        self.unit_controller = TwoForcesEncounter(
            environment_map, unit_map, tile_size=settings.tile_size
        )
        self.mouse_grid_x = 0
        self.mouse_grid_y = 0

    def handle_keydown_event(self, event):
        """Handle keyboard input events"""
        if event.key == pygame.K_UP:
            self.unit_controller.move("up")
        elif event.key == pygame.K_DOWN:
            self.unit_controller.move("down")
        elif event.key == pygame.K_LEFT:
            self.unit_controller.move("left")
        elif event.key == pygame.K_RIGHT:
            self.unit_controller.move("right")
        elif event.key == pygame.K_TAB:
            current_id = self.unit_controller.selected_unit_id
            if current_id is not None:
                new_index = (current_id + 1) % len(
                    self.unit_controller.unit_manager.unit_all_info
                )
                self.unit_controller.unit_manager.selected_unit_id = new_index
        elif event.key == pygame.K_1:
            self.settings.vision_mode = 1  # God view
        elif event.key == pygame.K_2:
            self.settings.vision_mode = 2  # R faction view
        elif event.key == pygame.K_3:
            self.settings.vision_mode = 3  # W faction view
        elif event.key == pygame.K_g:
            self.handle_g_key_action()
        elif event.key == pygame.K_h:
            self.unit_controller.step()

    def handle_g_key_action(self):
        """Plan path for target location"""
        pos_info = self.unit_controller.get_unit_info(
            pos=(self.mouse_grid_y, self.mouse_grid_x)
        )
        uid = self.unit_controller.selected_unit_id

        if uid is None:
            return

        if pos_info is None:
            self.unit_controller.plan(
                self.mouse_grid_y, self.mouse_grid_x, action="move"
            )
        else:
            pass

    def handle_events(self):
        """Handle all pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown_event(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    pos = pygame.mouse.get_pos()
                    self.unit_controller.select_unit_by_mouse(pos)

        # Update mouse position
        mouse_x, mouse_y = pygame.mouse.get_pos()
        self.mouse_grid_x = mouse_x // self.settings.tile_size
        self.mouse_grid_y = mouse_y // self.settings.tile_size
        return True


class GameLoop:
    def __init__(self, game, game_controller, generator, settings):
        self.game = game
        self.game_controller = game_controller
        self.generator = generator
        self.settings = settings
        self.clock = pygame.time.Clock()
        self.frame_count = 0
        self.running = True
        self.ai_controller = AIController() if settings.player_mode == "ai" else None

    def check_winner(self):
        """Check if there's a winner and update game settings"""
        # Get all units info from unit manager
        units_info = (
            self.game_controller.unit_controller.unit_manager.unit_all_info.values()
        )

        R_units = [u for u in units_info if u[2].startswith("R_")]
        W_units = [u for u in units_info if u[2].startswith("W_")]

        if not R_units and not W_units:
            self.settings.winner = "Peace"
        elif not R_units:
            self.settings.winner = "W win"
        elif not W_units:
            self.settings.winner = "R Win"

    def run(self):
        while self.running:
            # control frame rate
            self.clock.tick(30)
            self.frame_count += 1

            # Handle periodic saves
            if self.frame_count % self.settings.save_interval == 0:
                StateManager.save_game_state(self.settings, self.game_controller)

            # Handle AI mode actions
            if (
                self.ai_controller
                and self.frame_count % self.settings.action_interval == 0
            ):
                self.ai_controller.execute_actions(self.game_controller)

            self.running = self.game_controller.handle_events()

            # Check win condition
            self.check_winner()

            # Render frame
            RenderManager.render_frame(self.game, self.game_controller, self.generator)


class RenderManager:
    @staticmethod
    def _get_highlight_pos(game_controller):
        """Get position of selected unit for highlighting"""
        selected = game_controller.unit_controller.selected_unit_info
        return (selected[0], selected[1]) if selected else None

    @staticmethod
    def _calculate_visible_map(game, game_controller):
        """Calculate visible areas based on vision mode"""
        if game.settings.vision_mode == 1:
            return None  # God view - everything visible
        faction = "R" if game.settings.vision_mode == 2 else "W"
        return game_controller.unit_controller.compute_visibility(
            faction, vision_range=2
        )

    @staticmethod
    def _render_ui_elements(game, game_controller):
        # Render selected unit info
        selected = game_controller.unit_controller.selected_unit_info
        if selected:
            text = game.font.render(
                f"selected: {selected[2]} at ({selected[1]}, {selected[0]})",
                True,
                (255, 255, 255),
            )
        else:
            text = game.font.render("Cannot select", True, (255, 255, 255))
        game.screen.blit(text, (10, 10))

        # Render play mode
        mode_text = game.font.render(
            f"Play Mode: {game.settings.player_mode}", True, (255, 255, 255)
        )
        game.screen.blit(mode_text, (10, 30))

        # Render vision mode
        vision_text = (
            "God"
            if game.settings.vision_mode == 1
            else ("R" if game.settings.vision_mode == 2 else "W")
        )
        v_text = game.font.render(f"View Mode: {vision_text}", True, (255, 255, 255))
        game.screen.blit(v_text, (10, 50))

        # Render mouse position
        mouse_text = game.font.render(
            f"Mouse: ({game_controller.mouse_grid_x}, {game_controller.mouse_grid_y})",
            True,
            (255, 255, 255),
        )
        game.screen.blit(mouse_text, (10, 70))

        # Render target position if exists
        selected_id = game_controller.unit_controller.selected_unit_id
        if (
            selected_id is not None
            and selected_id in game_controller.unit_controller.path_planner.destinations
        ):
            ty, tx = game_controller.unit_controller.path_planner.destinations[
                selected_id
            ]["pos"]
            target_text = game.font.render(f"Aim: ({tx}, {ty})", True, (255, 255, 255))
            game.screen.blit(target_text, (10, 90))

        # Render winner if exists
        if game.settings.winner is not None:
            win_color = (255, 0, 0) if game.settings.winner == "Peace" else (0, 255, 0)
            win_text = game.win_font.render(game.settings.winner, True, win_color)
            win_rect = win_text.get_rect(
                center=(
                    game.settings.window_width // 2,
                    game.settings.window_height // 2,
                )
            )
            game.screen.blit(win_text, win_rect)

    @staticmethod
    def render_frame(game, game_controller, generator):
        game.screen.fill((0, 0, 0))

        # Calculate rendering parameters
        highlight_pos = RenderManager._get_highlight_pos(game_controller)
        visible_map = RenderManager._calculate_visible_map(game, game_controller)
        path_to_show = game_controller.unit_controller.path_planner.get_path(
            game_controller.unit_controller.selected_unit_id
        )

        # Render map and UI elements
        generator.render_map(
            game.screen,
            game_controller.unit_controller.environment_map,
            game_controller.unit_controller.unit_manager.unit_map,
            highlight_pos=highlight_pos,
            visible_map=visible_map,
            path_to_show=path_to_show,
        )

        RenderManager._render_ui_elements(game, game_controller)
        pygame.display.flip()


class StateManager:
    @staticmethod
    def save_game_state(settings, game_controller):
        """Handle saving environment and unit status"""
        StateManager.save_env_status(settings, game_controller)
        StateManager.save_unit_status(game_controller)

    @staticmethod
    def save_env_status(settings, game_controller):
        with open("run_log/env_status.txt", "w") as f:
            f.write(f"MapSize: {settings.map_width}x{settings.map_height}\n")
            # Update to use unit manager's method
            faction_counts = game_controller.unit_controller.get_faction_unit_counts()
            f.write(
                "R Force: ping={ping} shui={shui} shan={shan}\n".format(
                    **faction_counts["R"]
                )
            )
            f.write(
                "W Force: ping={ping} shui={shui} shan={shan}\n".format(
                    **faction_counts["W"]
                )
            )

    @staticmethod
    def save_unit_status(game_controller):
        with open("run_log/unit_status.txt", "w") as f:
            # Update method name
            units_info = (
                game_controller.unit_controller.get_all_units_info_with_path_state()
            )
            for uid, uy, ux, ut, state in units_info:
                f.write(f"unit_id:{uid} type:{ut} x:{ux} y:{uy} state:{state}\n")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ai", action="store_true", help="Run the game in AI mode (default: human)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    # Initialize game components
    settings = GameSettings(args)
    game = Game(settings)

    # Create map and controller
    generator = MapGenerator(
        settings.map_width, settings.map_height, "map_generator/map_tiles"
    )
    environment_map, unit_map = generator.generate_maps(
        r_unit_count=10, w_unit_count=10
    )
    game_controller = GameController(settings, environment_map, unit_map)

    # Create and run game loop
    game_loop = GameLoop(game, game_controller, generator, settings)
    game_loop.run()

    game.quit_pygame()


if __name__ == "__main__":
    main()
