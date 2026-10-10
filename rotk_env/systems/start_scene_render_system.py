"""STARBench start menu: one measured layout for paint and picking."""
import pygame
from framework import System
from framework.engine import RMS
from ..components.start_menu import (StartMenuConfig, StartMenuButtons,
    START_PLAYER_OPTIONS, START_CONTROLLER_OPTIONS, start_panel_layout, scenario_option_rects)
from ..prefabs.config import GameMode
from ..ui.context import UiContext, ACCENT, BACKGROUND, BORDER, MUTED, TEXT, controller_available


class StartSceneRenderSystem(System):
    def __init__(self):
        super().__init__(priority=1)

    def initialize(self, world):
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, dt):
        config = self.world.get_singleton_component(StartMenuConfig)
        if config is None:
            return
        ctx = getattr(self.world, '_ui_context', None)
        if ctx is None:
            ctx = UiContext()
            self.world._ui_context = ctx
        ctx.sync()
        w, h = ctx._size
        geom = start_panel_layout(len(config.scenario_catalog or []), w, h)
        RMS.fill(BACKGROUND)
        ctx.text('STARBench', (w//2, 44), size=42, color=ACCENT, centered=True)
        ctx.text('Romance of the Three Kingdoms  /  LLM + Agent Benchmark',
                 (w//2, 94), size=20, color=MUTED, centered=True)
        panel = pygame.Rect(geom['panel_x'], geom['panel_y'], geom['panel_width'], geom['panel_height'])
        ctx.panel(panel)
        left = panel.x+28
        ctx.text('Game mode', (left, geom['mode_y']), color=ACCENT, size=20)
        ctx.text('Factions', (panel.x+panel.w//2+20, geom['player_y']), color=ACCENT, size=20)
        ctx.text('Controller', (left, geom['controller_y']), color=ACCENT, size=20)
        ctx.text('Scenario', (left, geom['scenario_y']), color=ACCENT, size=20)
        def option(rect, label, selected, enabled=True):
            if selected:
                RMS.rect((43, 57, 67), rect)
                RMS.rect(ACCENT, rect, 1)
            RMS.circle(ACCENT if selected else BORDER, (rect.x+10, rect.centery), 4)
            ctx.text(label, (rect.x+24, rect.y+7), size=18,
                     color=TEXT if enabled else MUTED, max_width=rect.w-30)
        for rect, mode, label in zip(geom['mode_rects'], [GameMode.TURN_BASED, GameMode.REAL_TIME], ['Turn based', 'Real time']):
            option(rect, label, config.selected_mode == mode)
        for rect, (players, label) in zip(geom['player_rects'], START_PLAYER_OPTIONS):
            option(rect, label, config.selected_players == players)
        for rect, (backend, label) in zip(geom['controller_rects'], START_CONTROLLER_OPTIONS):
            enabled = controller_available(ctx.backend, backend)
            if not enabled:
                label += '  — unavailable on Rust'
            option(rect, label, config.selected_controller_backend == backend, enabled)
        with RMS.clip(geom['scenario_clip']):
            for index, rect in scenario_option_rects(config, geom):
                item = config.scenario_catalog[index]
                label = item.get('name', item['scenario'])
                if 'width' in item:
                    label += f"  {item['width']}×{item['height']}"
                option(rect, label, config.selected_scenario == item['scenario'])
        explanation = 'Static slots: no automatic opponent actions.' if config.selected_controller_backend == 'none' else 'Controller explicitly selected.'
        ctx.text(f'{ctx.backend.upper()}  /  {explanation}', geom['summary_rect'].topleft, size=16, color=MUTED, max_width=panel.w-56)
        buttons = self.world.get_singleton_component(StartMenuButtons)
        if buttons:
            for name, button in buttons.buttons.items():
                rect = geom['start_rect' if name == 'start_game' else 'quit_rect']
                button['rect'] = rect.copy()
                RMS.rect((63, 77, 86) if button['hover'] else (40, 55, 67), rect)
                RMS.rect(ACCENT if name == 'start_game' else BORDER, rect, 1)
                text = ctx.text(button['text'], (rect.x+12, rect.y+10), size=18)
