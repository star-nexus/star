"""
Input Handling System
Handles keyboard/mouse input, camera movement/zoom, UI toggles,
tile hover/selection, and dispatches domain events.
"""

import pygame
from typing import Tuple, Optional
from framework import (
    System,
    World,
    QuitEvent,
    KeyDownEvent,
    MouseButtonDownEvent,
    MouseMotionEvent,
)
from framework.engine.events import EBS

# from framework.ui.ui_layer_manager import ui_layer_manager
from ..components import (
    InputState,
    UIState,
    HexPosition,
    Unit,
    GameState,
    Camera,
    BattleLog,
    Player,
)
from ..prefabs.config import GameConfig, HexOrientation, Faction
from ..utils.hex_utils import HexConverter
from ..utils.env_events import TileClickedEvent, UnitSelectedEvent


class InputHandlingSystem(System):
    """Input handling system."""

    def __init__(self):
        super().__init__(priority=10)  # high priority
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

    def initialize(self, world: World) -> None:
        """Initialize input system and default singletons."""
        self.world = world

        # Input state
        input_state = InputState()
        self.world.add_singleton_component(input_state)

        # UI state
        ui_state = UIState()
        self.world.add_singleton_component(ui_state)

        # Camera – center (0,0) of map at screen center
        camera = Camera()
        camera.set_offset(GameConfig.WINDOW_WIDTH // 2, GameConfig.WINDOW_HEIGHT // 2)
        self.world.add_singleton_component(camera)

    def subscribe_events(self):
        """Subscribe input events to handlers."""
        EBS.subscribe(KeyDownEvent, self._handle_key_down)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def update(self, delta_time: float) -> None:
        """Process input per frame (mouse position, hover tile, held keys)."""
        input_state = self.world.get_singleton_component(InputState)
        ui_state = self.world.get_singleton_component(UIState)

        if not input_state or not ui_state:
            return

        # Update mouse position
        mouse_pos = pygame.mouse.get_pos()
        input_state.mouse_pos = mouse_pos

        # Optionally check if mouse is over UI and adjust hover state
        # mouse_over_ui = ui_layer_manager.is_mouse_over_ui(mouse_pos)

        # If not over UI, update map hover
        # if not mouse_over_ui:
        hex_pos = self._screen_to_hex(mouse_pos)
        ui_state.hovered_tile = hex_pos
        # else:
        #     # Over UI: clear map hover
        #     ui_state.hovered_tile = None

        # Handle continuous keyboard input
        keys = pygame.key.get_pressed()
        self._handle_keyboard(keys, input_state, delta_time)

    def _handle_mouse_click(self, event: MouseButtonDownEvent):
        """Handle mouse click."""
        ui_state = self.world.get_singleton_component(UIState)

        # First, check if clicking on UI
        # if ui_layer_manager.should_block_map_interaction(event.pos):
        #     # Do not process map interaction when over UI
        #     return

        # Action button panel first
        action_button_system = self._get_action_button_system()
        if action_button_system and action_button_system.handle_panel_click(event.pos):
            return

        # Minimap click handling
        minimap_system = self._get_minimap_system()
        if minimap_system and minimap_system.handle_click(event.pos):
            return

        if event.button == 1:  # left
            hex_pos = self._screen_to_hex(event.pos)

            if hex_pos:
                # Ensure inside map bounds (center-offset coordinate system)
                q, r = hex_pos
                half_width = GameConfig.MAP_WIDTH // 2
                half_height = GameConfig.MAP_HEIGHT // 2

                if -half_width <= q < half_width and -half_height <= r < half_height:
                    self._handle_tile_click(hex_pos, ui_state)

        elif event.button == 3:  # right
            # Clear selection
            ui_state.selected_unit = None

    def _handle_tile_click(self, hex_pos: Tuple[int, int], ui_state: UIState):
        """Handle tile click: select/move/attack depending on context."""
        # Unit on tile?
        clicked_unit = self._get_unit_at_position(hex_pos)

        if clicked_unit:
            # If current player's unit → select
            if self._is_current_player_unit(clicked_unit):
                # Select
                ui_state.selected_unit = clicked_unit
                EBS.publish(UnitSelectedEvent(clicked_unit))
            else:
                # If a unit is selected, try attack
                if ui_state.selected_unit:
                    self._try_attack_target(ui_state.selected_unit, clicked_unit)
        else:
            # Empty tile
            if ui_state.selected_unit:
                # Try move selected unit
                self._try_move_unit(ui_state.selected_unit, hex_pos)

        # Publish tile click event
        EBS.publish(TileClickedEvent(hex_pos, 1))

    def _handle_key_down(self, event: KeyDownEvent):
        """Handle key down (edge-triggered actions)."""
        ui_state = self.world.get_singleton_component(UIState)
        battle_log = self.world.get_singleton_component(BattleLog)

        if event.key == pygame.K_SPACE:
            # Space: end turn
            print("End current turn")
            self._end_current_turn()

        elif event.key == pygame.K_TAB:
            # Tab: toggle statistics panel
            print("Toggle statistics panel")
            ui_state.show_stats = not ui_state.show_stats

        elif event.key == pygame.K_F1:
            # F1: toggle help
            print("Toggle help panel")
            ui_state.show_help = not ui_state.show_help

        elif event.key == pygame.K_ESCAPE:
            # ESC: clear selection
            print("Clear selection")
            ui_state.selected_unit = None

        elif event.key == pygame.K_PAGEUP:
            # Page Up: scroll battle log up
            if battle_log:
                battle_log.scroll_up()

        elif event.key == pygame.K_PAGEDOWN:
            # Page Down: scroll battle log down
            if battle_log:
                battle_log.scroll_down()

        elif event.key == pygame.K_END:
            # End: scroll battle log to bottom
            if battle_log:
                battle_log.scroll_to_bottom()

        elif event.key == pygame.K_h:
            # H: toggle hex orientation
            print("Toggle hex orientation")
            self._toggle_hex_orientation()

        # View mode hotkeys
        elif event.key == pygame.K_1:
            # 1: God view
            print("Switch to God view")
            self._set_god_mode(ui_state, True)

        elif event.key == pygame.K_2:
            # 2: Wei view
            print("Switch to Wei view")
            self._set_faction_view(ui_state, Faction.WEI)

        elif event.key == pygame.K_3:
            # 3: Shu view
            print("Switch to Shu view")
            self._set_faction_view(ui_state, Faction.SHU)

        elif event.key == pygame.K_4:
            # 4: Wu view
            print("Switch to Wu view")
            self._set_faction_view(ui_state, Faction.WU)

        elif event.key == pygame.K_v:
            # V: toggle coordinate overlay
            ui_state.show_coordinates = not ui_state.show_coordinates
            print(f"Coordinates: {'ON' if ui_state.show_coordinates else 'OFF'}")

    def _handle_keyboard(
        self,
        keys: pygame.key.ScancodeWrapper,
        input_state: InputState,
        delta_time: float,
    ):
        """Handle held keys for camera movement and zoom."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # Camera movement
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            camera.move(0, camera.speed * delta_time)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            camera.move(0, -camera.speed * delta_time)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            camera.move(camera.speed * delta_time, 0)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            camera.move(-camera.speed * delta_time, 0)

        # Camera zoom
        if keys[pygame.K_PLUS] or keys[pygame.K_EQUALS]:  # plus: zoom in
            camera.zoom = min(camera.zoom + 2.0 * delta_time, 3.0)  # max 3x
        if keys[pygame.K_MINUS]:  # minus: zoom out
            camera.zoom = max(camera.zoom - 2.0 * delta_time, 0.5)  # min 0.5x

    def _screen_to_hex(self, screen_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Convert screen coordinates to hex (high-precision)."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return None

        x, y = screen_pos
        camera_offset = camera.get_offset()

        # Apply camera offset (use floats for precision)
        world_x = (float(x) - float(camera_offset[0])) / camera.zoom
        world_y = (float(y) - float(camera_offset[1])) / camera.zoom

        # High-precision conversion
        hex_pos = self.hex_converter.pixel_to_hex(world_x, world_y)

        return hex_pos

    def _hex_to_screen(self, hex_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert hex coordinates to screen coordinates."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return (0.0, 0.0)

        camera_offset = camera.get_offset()
        world_x, world_y = self.hex_converter.hex_to_pixel(*hex_pos)
        screen_x = world_x + camera_offset[0]
        screen_y = world_y + camera_offset[1]
        return screen_x, screen_y

    def _get_unit_at_position(self, hex_pos: Tuple[int, int]) -> Optional[int]:
        """Get unit entity at given hex, if any."""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            if position and (position.col, position.row) == hex_pos:
                return entity
        return None

    def _is_current_player_unit(self, unit_entity: int) -> bool:
        """Check if unit belongs to current player."""
        game_state = self.world.get_singleton_component(GameState)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not unit:
            return False

        return unit.faction == game_state.current_player

    def _try_attack_target(self, attacker_entity: int, target_entity: int):
        """Attempt to issue an attack order."""
        combat_system = self._get_combat_system()
        if combat_system:
            combat_system.attack(attacker_entity, target_entity)

    def _try_move_unit(self, unit_entity: int, target_pos: Tuple[int, int]):
        """Attempt to move a unit to target hex."""
        movement_system = self._get_movement_system()
        if movement_system:
            movement_system.move_unit(unit_entity, target_pos)

    def _end_current_turn(self):
        """End current turn via TurnSystem."""
        turn_system = self._get_turn_system()
        if turn_system:
            turn_system.end_turn()

    def _get_minimap_system(self):
        """Get MiniMapSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MiniMapSystem":
                return system
        return None

    def _get_action_button_system(self):
        """Get UnitActionButtonSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "UnitActionButtonSystem":
                return system
        return None

    def _get_combat_system(self):
        """Get CombatSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_movement_system(self):
        """Get MovementSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_turn_system(self):
        """Get TurnSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _toggle_hex_orientation(self):
        """Toggle hex orientation in MapRenderSystem and mirror locally."""
        # 获取地图渲染系统
        map_render_system = self._get_map_render_system()
        if map_render_system:
            map_render_system.toggle_hex_orientation()
            # Mirror local converter
            self.hex_converter = HexConverter(
                GameConfig.HEX_SIZE, map_render_system.hex_converter.orientation
            )
        else:
            print("MapRenderSystem not found")

    def _get_map_render_system(self):
        """Get MapRenderSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MapRenderSystem":
                return system
        return None

    def _set_god_mode(self, ui_state: UIState, enable: bool):
        """Enable/disable God view mode."""
        ui_state.god_mode = enable
        ui_state.view_faction = None
        if enable:
            print("🔥 GOD VIEW enabled - all units visible")
        else:
            print("👁️ GOD VIEW disabled")

    def _set_faction_view(self, ui_state: UIState, faction: Faction):
        """Set view to a specific faction."""
        # Ensure faction exists in current game
        if not self._faction_exists(faction):
            print(f"❌ Faction {faction.value} does not exist in current game")
            return

        ui_state.god_mode = False
        ui_state.view_faction = faction
        print(f"👁️ Switch to {faction.value} view - only that faction's vision is visible")

    def _faction_exists(self, faction: Faction) -> bool:
        """Check whether a faction exists in the current game."""
        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == faction:
                return True
        return False
