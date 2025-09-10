"""
Panel Render System - Responsible for rendering unit info panel (top-left), 
battle log panel (bottom-right), and minimap (top-right)
"""

import pygame
import time
from pathlib import Path
from framework import System, RMS
from ..components import (
    UIState,
    Unit,
    UnitCount,
    MovementPoints,
    Combat,
    HexPosition,
    UnitStatus,
    BattleLog,
    MapData,
    Terrain,
    Camera,
    FogOfWar,
    GameState,
    GameModeComponent,
)
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter


class PanelRenderSystem(System):
    """Panel rendering system for UI elements"""

    def __init__(self):
        super().__init__(priority=2)  # Lower priority
        self.font = None
        self.small_font = None

        # Initialize fonts
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """Initialize the panel rendering system"""
        self.world = world

    def subscribe_events(self):
        """Subscribe to events (panel render system doesn't need to subscribe to events)"""
        pass

    def update(self, delta_time: float) -> None:
        """Update panel rendering"""
        self._render_selected_unit_info()
        self._render_battle_log()
        self._render_view_mode_info()  # New: render view mode info
        # self._render_minimap()

    def _render_selected_unit_info(self):
        """Render selected unit information (top-left corner)"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.selected_unit:
            return

        unit_entity = ui_state.selected_unit
        unit = self.world.get_component(unit_entity, Unit)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        movement = self.world.get_component(unit_entity, MovementPoints)
        combat = self.world.get_component(unit_entity, Combat)
        position = self.world.get_component(unit_entity, HexPosition)
        status = self.world.get_component(unit_entity, UnitStatus)

        if not unit:
            return

        # Create info panel background
        panel_width = 250
        panel_height = 180
        panel_x = 10
        panel_y = 80

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(220)
        panel_surface.fill((0, 0, 30))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Draw border
        RMS.rect((100, 150, 200), (panel_x, panel_y, panel_width, panel_height), 2)

        # Render unit information
        y_offset = panel_y + 10
        line_height = 20

        # Unit type and faction
        unit_type_text = f"Type: {unit.unit_type.value}"
        faction_text = f"Faction: {unit.faction.value}"
        faction_color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))

        type_surface = self.small_font.render(unit_type_text, True, (255, 255, 255))
        faction_surface = self.small_font.render(faction_text, True, faction_color)

        RMS.draw(type_surface, (panel_x + 10, y_offset))
        y_offset += line_height
        RMS.draw(faction_surface, (panel_x + 10, y_offset))
        y_offset += line_height

        # Unit count with health indicator
        if unit_count:
            count_text = f"Strength: {unit_count.current_count}/{unit_count.max_count}"
            count_percentage = unit_count.percentage / 100
            count_color = (
                (255, 0, 0)
                if count_percentage < 0.3
                else (255, 255, 0) if count_percentage < 0.7 else (0, 255, 0)
            )
            count_surface = self.small_font.render(count_text, True, count_color)
            RMS.draw(count_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # Movement points
        if movement and unit_count:
            effective_max = movement.get_effective_movement(unit_count)
            movement_text = f"Movement: {movement.current_mp:.1f}/{effective_max:.1f}"
            movement_surface = self.small_font.render(
                movement_text, True, (0, 255, 255)
            )
            RMS.draw(movement_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # Attack power
        if combat:
            attack_text = f"Attack: {combat.base_attack}"
            attack_surface = self.small_font.render(attack_text, True, (255, 200, 0))
            RMS.draw(attack_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # Position
        if position:
            pos_text = f"Location: ({position.col}, {position.row})"
            pos_surface = self.small_font.render(pos_text, True, (200, 200, 200))
            RMS.draw(pos_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # Status
        if status:
            status_text = f"Status: {status.current_status}"
            status_colors = {
                "idle": (128, 128, 128),
                "moving": (0, 255, 255),
                "combat": (255, 0, 0),
                "hidden": (128, 0, 128),
                "resting": (0, 255, 0),
            }
            status_color = status_colors.get(status.current_status, (255, 255, 255))
            status_surface = self.small_font.render(status_text, True, status_color)
            RMS.draw(status_surface, (panel_x + 10, y_offset))

    def _render_battle_log(self):
        """Render battle log (bottom-right corner)"""
        battle_log = self.world.get_singleton_component(BattleLog)
        if not battle_log or not battle_log.show_log:
            return

        # Create log panel background
        panel_width = 400
        panel_height = 200
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = GameConfig.WINDOW_HEIGHT - panel_height - 10

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(200)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Draw border
        RMS.rect((150, 150, 150), (panel_x, panel_y, panel_width, panel_height), 2)

        # Render title with better styling
        title_surface = self.small_font.render("BATTLE LOG", True, (255, 255, 255))
        RMS.draw(title_surface, (panel_x + 10, panel_y + 5))

        # Render scroll indicator
        if len(battle_log.entries) > battle_log.visible_lines:
            scroll_info = f"({battle_log.scroll_offset + 1}-{min(battle_log.scroll_offset + battle_log.visible_lines, len(battle_log.entries))}/{len(battle_log.entries)})"
            scroll_surface = self.small_font.render(scroll_info, True, (180, 180, 180))
            RMS.draw(scroll_surface, (panel_x + panel_width - 100, panel_y + 5))

        # Render log entries (using visible entries)
        visible_entries = battle_log.get_visible_entries()
        y_offset = panel_y + 25
        line_height = 20

        for entry in visible_entries:
            if y_offset + line_height > panel_y + panel_height - 5:
                break

            # Use game time display
            if entry.game_time_display:
                time_str = entry.game_time_display
            else:
                # Compatibility: if no game time display, use default format
                time_str = "00:00"

            # Render message
            message_text = f"[{time_str}] {entry.message}"
            # Limit text length
            if len(message_text) > 45:
                message_text = message_text[:42] + "..."

            message_surface = self.small_font.render(message_text, True, entry.color)
            RMS.draw(message_surface, (panel_x + 10, y_offset))
            y_offset += line_height

    def _render_minimap(self):
        """Render minimap (top-right corner)"""
        # Minimap dimensions
        minimap_size = 120
        minimap_x = GameConfig.WINDOW_WIDTH - minimap_size - 10
        minimap_y = 10

        # Create minimap background
        minimap_surface = pygame.Surface((minimap_size, minimap_size))
        minimap_surface.set_alpha(200)
        minimap_surface.fill((20, 20, 40))
        RMS.draw(minimap_surface, (minimap_x, minimap_y))

        # Draw border
        RMS.rect((100, 100, 100), (minimap_x, minimap_y, minimap_size, minimap_size), 2)

        # Get map data
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Calculate scale ratio
        scale_x = minimap_size / GameConfig.MAP_WIDTH
        scale_y = minimap_size / GameConfig.MAP_HEIGHT
        scale = min(scale_x, scale_y)

        # Render terrain (simplified)
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # Convert coordinates
            pixel_x = (q + GameConfig.MAP_WIDTH // 2) * scale
            pixel_y = (r + GameConfig.MAP_HEIGHT // 2) * scale

            mini_x = minimap_x + pixel_x
            mini_y = minimap_y + pixel_y

            # Simplified terrain color
            color = GameConfig.TERRAIN_COLORS.get(terrain.terrain_type, (128, 128, 128))
            # Draw small dot
            RMS.circle(color, (int(mini_x), int(mini_y)), 1)

        # Render units
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if not position or not unit:
                continue

            # Check if unit is visible
            if not self._is_unit_visible(entity):
                continue

            # Convert coordinates
            pixel_x = (position.col + GameConfig.MAP_WIDTH // 2) * scale
            pixel_y = (position.row + GameConfig.MAP_HEIGHT // 2) * scale

            mini_x = minimap_x + pixel_x
            mini_y = minimap_y + pixel_y

            # Unit color
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(mini_x), int(mini_y)), 2)
            RMS.circle((0, 0, 0), (int(mini_x), int(mini_y)), 2, 1)

        # Render camera view range
        camera = self.world.get_singleton_component(Camera)
        if camera:
            # Simplified view indicator
            view_size = 20
            camera_x = minimap_x + minimap_size // 2
            camera_y = minimap_y + minimap_size // 2
            RMS.rect(
                (255, 255, 0),
                (
                    camera_x - view_size // 2,
                    camera_y - view_size // 2,
                    view_size,
                    view_size,
                ),
                1,
            )

    def _is_unit_visible(self, unit_entity: int) -> bool:
        """Check if unit is visible (considering fog of war)"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not fog_of_war or not position or not unit:
            return True

        # Own faction units are always visible
        if unit.faction == game_state.current_player:
            return True

        # Check if in current player's vision range
        current_vision = fog_of_war.faction_vision.get(game_state.current_player, set())
        return (position.col, position.row) in current_vision

    def _render_view_mode_info(self):
        """Render current view mode information (top-right corner)"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return

        # Determine current view mode
        if ui_state.god_mode:
            mode_text = "🔥 God View"
            mode_color = (255, 215, 0)  # Gold
        elif ui_state.view_faction:
            faction_name = ui_state.view_faction.value
            mode_text = f"👁️ {faction_name} View"
            # Use faction colors
            faction_colors = {
                "Wei": (100, 149, 237),  # Blue
                "Shu": (255, 69, 0),  # Red
                "Wu": (34, 139, 34),  # Green
            }
            mode_color = faction_colors.get(faction_name, (255, 255, 255))
        else:
            # Default view (current player)
            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.current_player:
                faction_name = game_state.current_player.value
                mode_text = f"👁️ {faction_name} View"
                faction_colors = {
                    "Wei": (100, 149, 237),
                    "Shu": (255, 69, 0),
                    "Wu": (34, 139, 34),
                }
                mode_color = faction_colors.get(faction_name, (255, 255, 255))
            else:
                mode_text = "👁️ Normal View"
                mode_color = (255, 255, 255)

        # Render background
        panel_width = 150
        panel_height = 30
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = 10

        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill((0, 0, 0, 180))  # Semi-transparent black background
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Render text
        text_surface = self.small_font.render(mode_text, True, mode_color)
        text_rect = text_surface.get_rect()
        text_rect.center = (panel_x + panel_width // 2, panel_y + panel_height // 2)
        RMS.draw(text_surface, text_rect)

        # Render key hints (below)
        hint_text = "Keys: 1-God 2-Wei 3-Shu 4-Wu"
        hint_surface = self.small_font.render(hint_text, True, (200, 200, 200))
        hint_rect = hint_surface.get_rect()
        hint_rect.centerx = panel_x + panel_width // 2
        hint_rect.top = panel_y + panel_height + 5
        RMS.draw(hint_surface, hint_rect)
