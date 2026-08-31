"""Unit action button rendering and click handling."""

from pathlib import Path

import pygame
from framework import System
from framework.ecs import profiling
from framework.engine import RMS

from ..components import UIState, Unit, Player
from ..components.unit_action_buttons import (
    UnitActionPanel,
    ActionConfirmDialog,
    ActionType,
)
from ..prefabs.config import GameConfig, PlayerType


class UnitActionButtonSystem(System):
    """Unit action system with cached text and explicit map-target actions."""

    FONT_PREWARM_TEXT = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "0123456789[]():+-/., %"
    )
    STATIC_MAIN_TEXTS = (
        "Move",
        "Attack",
        "Wait",
        "Garrison",
        "Capture",
        "Fortify",
        "Confirm",
        "Cancel",
    )
    STATIC_SMALL_TEXTS = (
        "[M]",
        "[A]",
        "[W]",
        "[G]",
        "[C]",
        "[F]",
        "End this unit's turn",
        "Gain a defense bonus",
        "Capture the current tile",
        "Build fortifications",
    )
    STATIC_TITLE_TEXTS = ("Unit Actions", "Confirm Action")

    def __init__(self):
        super().__init__(priority=4)

        self.panel_bg_color = (40, 40, 50, 180)
        self.button_bg_color = (60, 60, 70)
        self.button_hover_color = (80, 80, 90)
        self.button_disabled_color = (30, 30, 35)
        self.text_color = (255, 255, 255)
        self.text_disabled_color = (128, 128, 128)
        self.border_color = (100, 100, 110)

        pygame.font.init()
        font_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(font_path, 18)
        self.small_font = pygame.font.Font(font_path, 14)
        self.title_font = pygame.font.Font(font_path, 20)
        self._fonts = {
            "main": self.font,
            "small": self.small_font,
            "title": self.title_font,
        }
        self._text_surface_cache = {}
        self._frame_text_cache_misses = 0
        self._prewarm_action_text()

    def _render_text_cached(self, font_key: str, text: str, color: tuple):
        key = (font_key, text, color)
        surface = self._text_surface_cache.get(key)
        if surface is None:
            self._frame_text_cache_misses += 1
            surface = self._fonts[font_key].render(text, True, color)
            self._text_surface_cache[key] = surface
        return surface

    def _prewarm_action_text(self) -> None:
        for font in self._fonts.values():
            font.render(self.FONT_PREWARM_TEXT, True, self.text_color)

        for text in self.STATIC_MAIN_TEXTS:
            self._render_text_cached("main", text, self.text_color)
            self._render_text_cached("main", text, self.text_disabled_color)
        for text in self.STATIC_SMALL_TEXTS:
            self._render_text_cached("small", text, self.text_color)
            self._render_text_cached("small", text, self.text_disabled_color)
        for text in self.STATIC_TITLE_TEXTS:
            self._render_text_cached("title", text, self.text_color)

        self._frame_text_cache_misses = 0
        print(
            f"[UnitActionButtonSystem] Text surfaces prewarmed: "
            f"{len(self._text_surface_cache)} cached variants"
        )

    def initialize(self, world) -> None:
        self.world = world
        self.world.add_singleton_component(UnitActionPanel())
        self.world.add_singleton_component(ActionConfirmDialog())

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        self._frame_text_cache_misses = 0
        ui_state = self.world.get_singleton_component(UIState)
        action_panel = self.world.get_singleton_component(UnitActionPanel)
        if not ui_state or not action_panel:
            return

        # This panel used to be hard-coded at x=850, which was the right side
        # of the old 1200px window but sits over the playable map on a 2480px
        # desktop. Anchor it to the live right edge so it does not swallow map
        # clicks after the first unit selection.
        action_panel.x = max(20, GameConfig.WINDOW_WIDTH - action_panel.width - 20)
        action_panel.y = 100

        if ui_state.selected_unit != action_panel.selected_unit:
            with profiling.profiler.time_system(
                "unit_action_refresh", category="work"
            ):
                if ui_state.selected_unit and self._is_player_unit(
                    ui_state.selected_unit
                ):
                    action_panel.update_available_actions(
                        ui_state.selected_unit, self.world
                    )
                else:
                    action_panel.clear()

        if action_panel.visible:
            with profiling.profiler.time_system(
                "unit_action_render_panel", category="render"
            ):
                self._render_action_panel(action_panel)

        confirm_dialog = self.world.get_singleton_component(ActionConfirmDialog)
        if confirm_dialog and confirm_dialog.visible:
            with profiling.profiler.time_system(
                "unit_action_render_confirm", category="render"
            ):
                self._render_confirm_dialog(confirm_dialog)

        profiling.profiler.set_frame_metric(
            "unit_action_text_cache_misses", self._frame_text_cache_misses
        )
        profiling.profiler.set_frame_metric(
            "unit_action_text_cache_size", len(self._text_surface_cache)
        )

    def _is_player_unit(self, unit_entity: int) -> bool:
        unit = self.world.get_component(unit_entity, Unit)
        if not unit:
            return False
        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == unit.faction:
                return player.player_type == PlayerType.HUMAN
        return False

    def _render_action_panel(self, action_panel: UnitActionPanel):
        button_height = 35
        button_margin = 5
        panel_height = 60 + len(action_panel.available_actions) * (
            button_height + button_margin
        )

        panel_surface = pygame.Surface(
            (action_panel.width, panel_height), pygame.SRCALPHA
        )
        panel_surface.fill(self.panel_bg_color)
        pygame.draw.rect(
            panel_surface,
            self.border_color,
            (0, 0, action_panel.width, panel_height),
            2,
        )

        title_text = self._render_text_cached(
            "title", "Unit Actions", self.text_color
        )
        title_rect = title_text.get_rect(centerx=action_panel.width // 2, y=10)
        panel_surface.blit(title_text, title_rect)
        pygame.draw.line(
            panel_surface,
            self.border_color,
            (10, 35),
            (action_panel.width - 10, 35),
        )

        self._render_action_buttons(
            panel_surface, action_panel.available_actions, 45
        )
        RMS.draw(panel_surface, (action_panel.x, action_panel.y))

    def _render_action_buttons(self, surface, actions, y_offset):
        button_height = 35
        button_margin = 5

        for i, action in enumerate(actions):
            button_y = y_offset + i * (button_height + button_margin)
            button_rect = pygame.Rect(
                10, button_y, surface.get_width() - 20, button_height
            )
            bg_color = (
                self.button_bg_color
                if action.enabled
                else self.button_disabled_color
            )
            pygame.draw.rect(surface, bg_color, button_rect)
            pygame.draw.rect(surface, self.border_color, button_rect, 1)

            text_color = (
                self.text_color if action.enabled else self.text_disabled_color
            )
            label_text = self._render_text_cached(
                "main", action.label, text_color
            )
            surface.blit(label_text, (button_rect.x + 5, button_rect.y + 2))

            if action.hotkey:
                hotkey_text = self._render_text_cached(
                    "small", f"[{action.hotkey}]", text_color
                )
                surface.blit(
                    hotkey_text,
                    (
                        button_rect.right - hotkey_text.get_width() - 5,
                        button_rect.y + 2,
                    ),
                )

            if action.cost_description:
                cost_text = self._render_text_cached(
                    "small", action.cost_description, text_color
                )
                surface.blit(
                    cost_text, (button_rect.x + 5, button_rect.y + 18)
                )

    def _render_confirm_dialog(self, confirm_dialog: ActionConfirmDialog):
        dialog_width = 300
        dialog_height = 150
        dialog_x = (GameConfig.WINDOW_WIDTH - dialog_width) // 2
        dialog_y = (GameConfig.WINDOW_HEIGHT - dialog_height) // 2

        dialog_surface = pygame.Surface(
            (dialog_width, dialog_height), pygame.SRCALPHA
        )
        dialog_surface.fill((20, 20, 30, 220))
        pygame.draw.rect(
            dialog_surface,
            self.border_color,
            (0, 0, dialog_width, dialog_height),
            3,
        )

        title_text = self._render_text_cached(
            "title", "Confirm Action", self.text_color
        )
        dialog_surface.blit(
            title_text, title_text.get_rect(centerx=dialog_width // 2, y=10)
        )

        y_offset = 40
        for line in self._wrap_text(
            confirm_dialog.message, self.font, dialog_width - 20
        ):
            line_text = self._render_text_cached(
                "main", line, self.text_color
            )
            dialog_surface.blit(
                line_text,
                line_text.get_rect(centerx=dialog_width // 2, y=y_offset),
            )
            y_offset += 25

        button_width = 80
        button_height = 30
        button_y = dialog_height - 40
        confirm_rect = pygame.Rect(
            dialog_width // 2 - button_width - 10,
            button_y,
            button_width,
            button_height,
        )
        cancel_rect = pygame.Rect(
            dialog_width // 2 + 10,
            button_y,
            button_width,
            button_height,
        )
        pygame.draw.rect(dialog_surface, (100, 150, 100), confirm_rect)
        pygame.draw.rect(dialog_surface, self.border_color, confirm_rect, 1)
        pygame.draw.rect(dialog_surface, (150, 100, 100), cancel_rect)
        pygame.draw.rect(dialog_surface, self.border_color, cancel_rect, 1)

        confirm_text = self._render_text_cached(
            "main", "Confirm", self.text_color
        )
        cancel_text = self._render_text_cached(
            "main", "Cancel", self.text_color
        )
        dialog_surface.blit(
            confirm_text, confirm_text.get_rect(center=confirm_rect.center)
        )
        dialog_surface.blit(
            cancel_text, cancel_text.get_rect(center=cancel_rect.center)
        )
        RMS.draw(dialog_surface, (dialog_x, dialog_y))

    def _wrap_text(self, text, font, max_width):
        words = text.split(" ")
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    def handle_panel_click(self, mouse_pos):
        action_panel = self.world.get_singleton_component(UnitActionPanel)
        if not action_panel or not action_panel.visible:
            return False

        button_height = 35
        button_margin = 5
        panel_height = 60 + len(action_panel.available_actions) * (
            button_height + button_margin
        )
        panel_rect = pygame.Rect(
            action_panel.x, action_panel.y, action_panel.width, panel_height
        )
        if not panel_rect.collidepoint(mouse_pos):
            return False

        button_start_y = action_panel.y + 45
        relative_y = mouse_pos[1] - button_start_y
        if relative_y < 0:
            return True

        button_index = relative_y // (button_height + button_margin)
        if 0 <= button_index < len(action_panel.available_actions):
            action = action_panel.available_actions[button_index]
            if action.enabled:
                self._execute_action(
                    action.action_type, action_panel.selected_unit
                )
        return True

    def _execute_action(self, action_type, unit_entity):
        print(f"Executing action: {action_type.value} on unit {unit_entity}")
        action_panel = self.world.get_singleton_component(UnitActionPanel)

        if action_type in (ActionType.MOVE, ActionType.ATTACK):
            input_system = self._get_input_handling_system()
            if input_system and input_system.begin_targeting(
                action_type.value, unit_entity
            ):
                # Target is chosen on the map. Hide the menu so it cannot
                # intercept that click; InputHandlingSystem reopens/refreshed it
                # after a successful action.
                if action_panel is not None:
                    action_panel.visible = False
                return

        if action_type == ActionType.WAIT:
            self._execute_wait_action(unit_entity)
        elif action_type == ActionType.GARRISON:
            self._execute_garrison_action(unit_entity)
        elif action_type == ActionType.CAPTURE:
            self._execute_capture_action(unit_entity)
        elif action_type == ActionType.FORTIFY:
            self._execute_fortify_action(unit_entity)

        if action_panel is not None:
            action_panel.selected_unit = None

    def _execute_wait_action(self, unit_entity):
        from ..components import ActionPoints

        action_points = self.world.get_component(unit_entity, ActionPoints)
        if action_points and action_points.can_perform_action(ActionType.WAIT):
            action_points.consume_ap(ActionType.WAIT)
            print(f"Unit {unit_entity} ends turn")

    def _execute_garrison_action(self, unit_entity):
        from ..components import ActionPoints

        action_points = self.world.get_component(unit_entity, ActionPoints)
        if action_points and action_points.can_perform_action(ActionType.GARRISON):
            action_points.consume_ap(ActionType.GARRISON)
            print(f"Unit {unit_entity} begins garrisoning")

    def _execute_capture_action(self, unit_entity):
        from ..components import HexPosition

        position = self.world.get_component(unit_entity, HexPosition)
        if position:
            territory_system = self._get_territory_system()
            if territory_system:
                territory_system.start_capture(
                    unit_entity, (position.col, position.row)
                )

    def _execute_fortify_action(self, unit_entity):
        from ..components import HexPosition

        position = self.world.get_component(unit_entity, HexPosition)
        if position:
            territory_system = self._get_territory_system()
            if territory_system:
                territory_system.build_fortification(
                    unit_entity, (position.col, position.row)
                )

    def _get_input_handling_system(self):
        for system in self.world.systems:
            if system.__class__.__name__ == "InputHandlingSystem":
                return system
        return None

    def _get_territory_system(self):
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None
