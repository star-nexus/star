"""
Input Handling System
Handles keyboard/mouse input, camera movement/zoom, UI toggles,
tile hover/selection, and dispatches domain events.
"""

import pygame
from typing import Tuple, Optional
from framework import System, World
from framework.engine import QuitEvent, KeyDownEvent, MouseButtonDownEvent, MouseMotionEvent
from framework.engine.events import EBS

from ..components import (
    InputState,
    UIState,
    HexPosition,
    Unit,
    GameState,
    Camera,
    BattleLog,
    Player,
    FogOfWar,
    MapData,
    set_fog_enabled,
)
from ..prefabs.config import GameConfig, HexOrientation, Faction, GameMode
from ..prefabs.controls import binding_for_key
from ..utils.hex_utils import HexConverter
from ..utils.env_events import TileClickedEvent, UnitSelectedEvent


class InputHandlingSystem(System):
    """Input handling system."""

    def __init__(self):
        super().__init__(priority=10)  # high priority
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.min_zoom = 0.5
        self.max_zoom = 3.0
        self._window_size: tuple[int, int] | None = None

    def initialize(self, world: World) -> None:
        """Initialize input system and default singletons."""
        self.world = world

        # Input state
        input_state = InputState()
        self.world.add_singleton_component(input_state)

        # UI state
        ui_state = UIState()
        self.world.add_singleton_component(ui_state)

        # Camera – center (0,0) of map at screen center. Zoom out on boards
        # larger than the window so a 33×33 map is visible, not just ~15 hexes.
        camera = Camera()
        camera.set_offset(GameConfig.WINDOW_WIDTH // 2, GameConfig.WINDOW_HEIGHT // 2)
        map_data = self.world.get_singleton_component(MapData)
        fit = self._zoom_to_fit_map(map_data)
        self.min_zoom = min(0.5, max(0.15, fit * 0.75))
        camera.zoom = min(1.0, fit)
        self.world.add_singleton_component(camera)
        self._window_size = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)

    def _zoom_to_fit_map(self, map_data: MapData | None) -> float:
        """Zoom that fits the loaded board in the window (capped at 1.0)."""
        if map_data is None or not map_data.tiles:
            return 1.0
        xs = []
        ys = []
        for col, row in map_data.tiles:
            x, y = self.hex_converter.hex_to_pixel(col, row)
            xs.append(x)
            ys.append(y)
        pad = GameConfig.HEX_SIZE * 2
        world_w = max(xs) - min(xs) + pad * 2
        world_h = max(ys) - min(ys) + pad * 2
        if world_w <= 0 or world_h <= 0:
            return 1.0
        zx = GameConfig.WINDOW_WIDTH / world_w
        zy = GameConfig.WINDOW_HEIGHT / world_h
        return max(0.15, min(1.0, min(zx, zy) * 0.92))

    def _follow_window_resize(self) -> None:
        size = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        if self._window_size is None:
            self._window_size = size
            return
        if size == self._window_size:
            return
        old_w, old_h = self._window_size
        camera = self.world.get_singleton_component(Camera)
        if camera is not None:
            camera.offset_x += (size[0] - old_w) / 2
            camera.offset_y += (size[1] - old_h) / 2
        fit = self._zoom_to_fit_map(self.world.get_singleton_component(MapData))
        self.min_zoom = min(0.5, max(0.15, fit * 0.75))
        if camera is not None:
            camera.zoom = min(self.max_zoom, max(self.min_zoom, camera.zoom))
        self._window_size = size

    def subscribe_events(self):
        """Subscribe input events to handlers."""
        EBS.subscribe(KeyDownEvent, self._handle_key_down)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def cleanup(self) -> None:
        EBS.unsubscribe(KeyDownEvent, self._handle_key_down)
        EBS.unsubscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def update(self, delta_time: float) -> None:
        """Process input per frame (mouse position, hover tile, held keys)."""
        input_state = self.world.get_singleton_component(InputState)
        ui_state = self.world.get_singleton_component(UIState)

        if not input_state or not ui_state:
            return

        self._follow_window_resize()

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
        if not ui_state:
            return

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

            if hex_pos and self._hex_on_board(hex_pos):
                self._handle_tile_click(hex_pos, ui_state)

        elif event.button == 3:  # right
            # Clear selection
            ui_state.selected_unit = None

    def _hex_on_board(self, hex_pos: Tuple[int, int]) -> bool:
        """True when the hex exists in MapData.tiles. No map → allow."""
        map_data = self.world.get_singleton_component(MapData)
        if map_data is None:
            return True
        return hex_pos in map_data.tiles

    def _handle_tile_click(self, hex_pos: Tuple[int, int], ui_state: UIState):
        """Handle tile click: select/move/attack depending on context."""
        clicked_unit = self._get_unit_at_position(hex_pos)

        if clicked_unit:
            if self._should_select_unit(clicked_unit, ui_state):
                ui_state.selected_unit = clicked_unit
                EBS.publish(UnitSelectedEvent(clicked_unit))
            elif ui_state.selected_unit:
                self._try_attack_target(ui_state.selected_unit, clicked_unit)
        elif ui_state.selected_unit:
            self._try_move_unit(ui_state.selected_unit, hex_pos)

        EBS.publish(TileClickedEvent(hex_pos, 1))

    def _should_select_unit(self, unit_entity: int, ui_state: UIState) -> bool:
        """Return whether a left click should select this unit.

        Turn-based interaction keeps the historical current-player restriction.
        Real-time has no meaningful single current turn, so using
        ``GameState.current_player`` there made only the first configured faction
        selectable forever. That is especially confusing in three-faction
        scale tests: zooming into a Wei/Wu cluster made mouse selection appear
        completely broken when the first configured faction was Shu.

        In real-time mode:
        * with no current selection, any clicked unit can become the manual
          focus;
        * with a unit selected, clicking the same faction changes selection;
        * clicking another faction remains an attack attempt, preserving the
          existing click-to-attack interaction;
        * right click still clears selection, so switching factions is explicit.
        """
        game_state = self.world.get_singleton_component(GameState)
        unit = self.world.get_component(unit_entity, Unit)
        if not game_state or not unit:
            return False

        if game_state.game_mode == GameMode.REAL_TIME:
            if not ui_state.selected_unit:
                return True
            selected = self.world.get_component(ui_state.selected_unit, Unit)
            if selected is None:
                return True
            return selected.faction == unit.faction

        return unit.faction == game_state.current_player

    def _handle_key_down(self, event: KeyDownEvent):
        """Handle key down (edge-triggered actions from the shared keymap)."""
        if self.world is None or self.world.get_singleton_component(UIState) is None:
            return
        binding = binding_for_key(event.key)
        if binding is None:
            return
        handler = getattr(self, f"_action_{binding.action}", None)
        if handler is not None:
            handler()

    def _action_end_turn(self):
        print("End current turn")
        self._end_current_turn()

    def _action_toggle_stats(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Toggle statistics panel")
        ui_state.show_stats = not ui_state.show_stats

    def _action_toggle_help(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Toggle help panel")
        ui_state.show_help = not ui_state.show_help

    def _action_clear_selection(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Clear selection")
        ui_state.selected_unit = None

    def _action_battle_log_up(self):
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            battle_log.scroll_up()

    def _action_battle_log_down(self):
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            battle_log.scroll_down()

    def _action_battle_log_bottom(self):
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            battle_log.scroll_to_bottom()

    def _action_toggle_hex_orientation(self):
        print("Toggle hex orientation")
        self._toggle_hex_orientation()

    def _action_toggle_fog(self):
        ui_state = self.world.get_singleton_component(UIState)
        fog = self._ensure_fog()
        enabled = not fog.enabled
        self._set_fog_enabled(ui_state, enabled=enabled)
        if enabled:
            print("Fog on - faction vision")
        else:
            print("Fog off - whole map visible to human, BOT, and agents")

    def _action_view_wei(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Switch to Wei view")
        self._set_faction_view(ui_state, Faction.WEI)

    def _action_view_shu(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Switch to Shu view")
        self._set_faction_view(ui_state, Faction.SHU)

    def _action_view_wu(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
        print("Switch to Wu view")
        self._set_faction_view(ui_state, Faction.WU)

    def _action_toggle_coordinates(self):
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return
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
            camera.zoom = min(camera.zoom + 2.0 * delta_time, self.max_zoom)
        if keys[pygame.K_MINUS]:  # minus: zoom out
            camera.zoom = max(camera.zoom - 2.0 * delta_time, self.min_zoom)

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
        # Get MapRenderSystem
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

    def _ensure_fog(self) -> FogOfWar:
        fog = self.world.get_singleton_component(FogOfWar)
        if fog is None:
            fog = FogOfWar()
            self.world.add_singleton_component(fog)
        return fog

    def _set_fog_enabled(self, ui_state: Optional[UIState], enabled: bool):
        """Write FogOfWar.enabled. Spectator camera is UI-only, not a fog flag."""
        set_fog_enabled(self._ensure_fog(), enabled)
        if ui_state is not None and not enabled:
            ui_state.view_faction = None

    def _set_faction_view(self, ui_state: UIState, faction: Faction):
        """Set spectator camera to a faction and restore fog."""
        if not self._faction_exists(faction):
            print(f"Faction {faction.value} does not exist in current game")
            return

        self._set_fog_enabled(ui_state, enabled=True)
        ui_state.view_faction = faction
        print(f"Switch to {faction.value} view - only that faction's vision is visible")

    def _faction_exists(self, faction: Faction) -> bool:
        """Check whether a faction exists in the current game."""
        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == faction:
                return True
        return False
