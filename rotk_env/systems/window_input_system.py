"""Window input with render-consistent picking and explicit action targeting.

The window path provides two guarantees beyond coordinate-only input:
* visible unit sprites are picked in screen space using the same camera transform
  as the renderer, then the clicked entity is carried into tile dispatch;
* Move/Attack action-panel buttons enter an explicit target-selection mode
  instead of being no-op buttons.
"""

from __future__ import annotations

from typing import Optional, Tuple

from framework.ecs import profiling
from framework.engine.events import EBS

from ..components import (
    Camera,
    FogOfWar,
    GameState,
    HexPosition,
    UIState,
    Unit,
    UnitCount,
)
from ..prefabs.config import GameConfig
from ..utils.env_events import TileClickedEvent, UnitSelectedEvent
from .input_system import InputHandlingSystem as BaseInputHandlingSystem


class InputHandlingSystem(BaseInputHandlingSystem):
    """Interactive input with render-consistent unit hit testing."""

    def __init__(self):
        super().__init__()
        self._targeting_action: Optional[str] = None
        self._targeting_unit: Optional[int] = None

    def begin_targeting(self, action: str, unit_entity: int) -> bool:
        """Enter map-target selection for a HUMAN-controlled unit."""
        if action not in ("move", "attack") or not self._should_select_unit(unit_entity):
            return False
        self._targeting_action = action
        self._targeting_unit = unit_entity
        return True

    def cancel_targeting(self, *, refresh_panel: bool = False) -> None:
        self._targeting_action = None
        self._targeting_unit = None
        if refresh_panel:
            try:
                from ..components.unit_action_buttons import UnitActionPanel

                panel = self.world.get_singleton_component(UnitActionPanel)
                if panel is not None:
                    # Force UnitActionButtonSystem to rebuild costs/availability
                    # on its next update while keeping the UI selection intact.
                    panel.selected_unit = None
            except Exception:
                pass

    def _handle_mouse_click(self, event):
        """Pick visible sprites first, then fall back to ordinary hex clicks."""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return

        profiler = profiling.profiler

        with profiler.time_system("input_click_ui", category="input"):
            action_button_system = self._get_action_button_system()
            consumed_by_ui = bool(
                action_button_system
                and action_button_system.handle_panel_click(event.pos)
            )
        if consumed_by_ui:
            return

        with profiler.time_system("input_click_minimap", category="input"):
            minimap_system = self._get_minimap_system()
            consumed_by_minimap = bool(
                minimap_system and minimap_system.handle_click(event.pos)
            )
        if consumed_by_minimap:
            return

        if event.button == 1:
            with profiler.time_system("input_click_unit_hit_test", category="input"):
                clicked_unit = self._get_visible_unit_at_screen_position(event.pos)

            with profiler.time_system("input_click_screen_to_hex", category="input"):
                hex_pos = self._screen_to_hex(event.pos)

            # If the pointer actually hit a rendered token, use that entity's
            # authoritative hex. This makes picking independent from any tiny
            # pixel->hex rounding difference after zoom/fog/cache transitions.
            if clicked_unit is not None:
                position = self.world.get_component(clicked_unit, HexPosition)
                if position is not None:
                    hex_pos = (position.col, position.row)

            if hex_pos and self._hex_on_board(hex_pos):
                self._handle_tile_click(
                    hex_pos,
                    ui_state,
                    clicked_unit=clicked_unit,
                )

        elif event.button == 3:
            ui_state.selected_unit = None
            self.cancel_targeting(refresh_panel=False)

    def _handle_tile_click(
        self,
        hex_pos: Tuple[int, int],
        ui_state: UIState,
        *,
        clicked_unit: Optional[int] = None,
    ) -> None:
        profiler = profiling.profiler
        if clicked_unit is None:
            with profiler.time_system("input_click_unit_lookup", category="input"):
                clicked_unit = self._get_unit_at_position(hex_pos)

        targeting = getattr(self, "_targeting_action", None)
        targeting_unit = getattr(self, "_targeting_unit", None)
        if (
            targeting
            and targeting_unit is not None
            and ui_state.selected_unit == targeting_unit
            and self._should_select_unit(targeting_unit)
        ):
            if targeting == "move" and clicked_unit is None:
                with profiler.time_system("input_click_move", category="input"):
                    result = self._try_move_unit(targeting_unit, hex_pos)
                if self._action_succeeded(result):
                    self.cancel_targeting(refresh_panel=True)
            elif (
                targeting == "attack"
                and clicked_unit is not None
                and clicked_unit != targeting_unit
            ):
                with profiler.time_system("input_click_attack", category="input"):
                    self._try_attack_target(targeting_unit, clicked_unit)
                # CombatSystem.attack returns False for both an invalid order and
                # a legitimate miss after consuming AP. Either way, one target
                # click completes this interaction; refresh the menu from the
                # resulting world state instead of trapping the user in target mode.
                self.cancel_targeting(refresh_panel=True)
            elif clicked_unit is not None and self._should_select_unit(clicked_unit):
                # Selecting another local unit cancels the active target mode.
                self.cancel_targeting(refresh_panel=False)
                ui_state.selected_unit = clicked_unit
                EBS.publish(UnitSelectedEvent(clicked_unit))

            EBS.publish(TileClickedEvent(hex_pos, 1))
            return

        if clicked_unit:
            if self._should_select_unit(clicked_unit):
                self.cancel_targeting(refresh_panel=False)
                ui_state.selected_unit = clicked_unit
                EBS.publish(UnitSelectedEvent(clicked_unit))
            elif ui_state.selected_unit and self._should_select_unit(ui_state.selected_unit):
                with profiler.time_system("input_click_attack", category="input"):
                    self._try_attack_target(ui_state.selected_unit, clicked_unit)
        elif ui_state.selected_unit and self._should_select_unit(ui_state.selected_unit):
            with profiler.time_system("input_click_move", category="input"):
                self._try_move_unit(ui_state.selected_unit, hex_pos)

        EBS.publish(TileClickedEvent(hex_pos, 1))

    def _get_unit_at_position(self, hex_pos: Tuple[int, int]) -> Optional[int]:
        """Prefer a visible HUMAN token when several entities share one hex."""
        candidates = []
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            if position is None or (position.col, position.row) != hex_pos:
                continue
            if not self._unit_is_visible_for_pick(entity):
                continue
            candidates.append(entity)
        if not candidates:
            return None
        return min(candidates, key=lambda entity: (not self._should_select_unit(entity), entity))

    def _get_visible_unit_at_screen_position(
        self, screen_pos: Tuple[int, int]
    ) -> Optional[int]:
        """Return the visible token under the pointer using renderer coordinates.

        This runs only on mouse-down, not every frame, which avoids maintaining
        another hot-path index. A HUMAN token wins an exact-position tie, which
        also makes overlapped real-time units manually recoverable.
        """
        camera = self.world.get_singleton_component(Camera)
        if camera is None or camera.zoom <= 0:
            return None

        mouse_x, mouse_y = float(screen_pos[0]), float(screen_pos[1])
        hit_radius = max(8.0, GameConfig.HEX_SIZE * float(camera.zoom) * 0.65)
        hit_radius_sq = hit_radius * hit_radius

        animation_system = self._get_animation_system_for_pick()
        best = None
        best_key = None
        entities = self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        for entity in entities:
            count = self.world.get_component(entity, UnitCount)
            if count is not None and count.current_count <= 0:
                continue
            if not self._unit_is_visible_for_pick(entity):
                continue

            position = self.world.get_component(entity, HexPosition)
            if position is None:
                continue
            world_x, world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            if animation_system is not None:
                try:
                    render_pos = animation_system.get_unit_render_position(entity)
                except Exception:
                    render_pos = None
                if render_pos is not None:
                    world_x, world_y = render_pos

            screen_x = world_x * camera.zoom + camera.offset_x
            screen_y = world_y * camera.zoom + camera.offset_y
            dx = mouse_x - screen_x
            dy = mouse_y - screen_y
            dist_sq = dx * dx + dy * dy
            if dist_sq > hit_radius_sq:
                continue

            key = (dist_sq, not self._should_select_unit(entity), entity)
            if best_key is None or key < best_key:
                best = entity
                best_key = key

        return best

    def _unit_is_visible_for_pick(self, entity: int) -> bool:
        unit = self.world.get_component(entity, Unit)
        position = self.world.get_component(entity, HexPosition)
        if unit is None or position is None:
            return False

        fog = self.world.get_singleton_component(FogOfWar)
        if fog is None or not fog.enabled:
            return True

        game_state = self.world.get_singleton_component(GameState)
        ui_state = self.world.get_singleton_component(UIState)
        if game_state is None or ui_state is None:
            return True
        view_faction = ui_state.view_faction or game_state.current_player
        if unit.faction == view_faction:
            return True
        return (position.col, position.row) in fog.faction_vision.get(
            view_faction, set()
        )

    def _get_animation_system_for_pick(self):
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def _hex_to_screen(self, hex_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Exact inverse partner of _screen_to_hex, including camera zoom."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return (0.0, 0.0)
        world_x, world_y = self.hex_converter.hex_to_pixel(*hex_pos)
        return (
            world_x * camera.zoom + camera.offset_x,
            world_y * camera.zoom + camera.offset_y,
        )

    def _try_move_unit(self, unit_entity: int, target_pos: Tuple[int, int]):
        movement_system = self._get_movement_system()
        if movement_system:
            return movement_system.move_unit(unit_entity, target_pos)
        return None

    def _try_attack_target(self, attacker_entity: int, target_entity: int):
        combat_system = self._get_combat_system()
        if combat_system:
            return combat_system.attack(attacker_entity, target_entity)
        return None

    @staticmethod
    def _action_succeeded(result) -> bool:
        if isinstance(result, dict):
            return bool(result.get("success", result.get("result", False)))
        if isinstance(result, bool):
            return result
        return result is not None
