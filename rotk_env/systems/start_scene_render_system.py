"""STARBench start menu: one measured layout for paint and picking."""
import math
import pygame
from framework import System
from framework.engine import RMS
from ..components.start_menu import (StartMenuConfig, StartMenuButtons,
    START_PLAYER_OPTIONS, START_CONTROLLER_OPTIONS)
from ..ui.start_layout import start_panel_layout, scenario_option_rects
from ..prefabs.config import GameMode
from ..ui.context import (UiContext, ACCENT, BACKGROUND, BORDER, MUTED, PANEL,
                          RAISED, TEXT, controller_available)


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
        def paint_motif(surface):
            surface.fill(BACKGROUND)
            for col in range(3):
                for row in range(5):
                    x, y = 12+col*42, 24+row*48+(col%2)*24
                    points = [(round(x+28*math.cos(n*math.pi/3)),
                               round(y+28*math.sin(n*math.pi/3))) for n in range(6)]
                    pygame.draw.polygon(surface, (31, 45, 56), points, 1)
        motif = ctx.widget_surface('menu-motif', (124, 280), paint_motif)
        RMS.draw(motif, (8, (h-280)//2))
        RMS.draw(motif, (w-132, (h-280)//2))
        ctx.text('STRATEGY  /  TACTICS  /  AGENTS', (w//2, 20), size=14, color=MUTED, centered=True)
        ctx.text('STARBench', (w//2, 43), size=46, color=ACCENT, centered=True)
        ctx.text('Romance of the Three Kingdoms  /  LLM + Agent Benchmark',
                 (w//2, 94), size=20, color=MUTED, centered=True)
        panel = pygame.Rect(geom['panel_x'], geom['panel_y'], geom['panel_width'], geom['panel_height'])
        def paint_frame(surface):
            surface.fill(PANEL)
            pygame.draw.rect(surface, BORDER, surface.get_rect(), 1)
            pygame.draw.rect(surface, ACCENT, (28, 0, 64, 3))
            pygame.draw.rect(surface, BACKGROUND, (1, panel.h-94, panel.w-2, 93))
            pygame.draw.line(surface, BORDER, (1, panel.h-94), (panel.w-2, panel.h-94))
        RMS.draw(ctx.widget_surface('menu-frame', panel.size, paint_frame), panel.topleft)
        left = panel.x+28
        ctx.text('01  GAME MODE', (left, geom['mode_y']), color=ACCENT, size=18)
        ctx.text('02  FACTIONS', (panel.x+panel.w//2+20, geom['player_y']), color=ACCENT, size=18)
        ctx.text('03  CONTROLLER', (left, geom['controller_y']), color=ACCENT, size=18)
        ctx.text('04  SCENARIO', (left, geom['scenario_y']), color=ACCENT, size=18)
        def option(rect, label, selected, enabled=True):
            key = ('menu-option', label, selected, enabled, id(ctx.font(18)))
            def paint(surface):
                surface.fill(PANEL)
                pygame.draw.rect(surface, RAISED if selected else BACKGROUND,
                                 surface.get_rect(), border_radius=4)
                if selected:
                    pygame.draw.rect(surface, ACCENT, surface.get_rect(), 1, border_radius=4)
                    pygame.draw.rect(surface, ACCENT, (0, 5, 3, rect.h-10))
                center = (13, rect.h//2)
                pygame.draw.circle(surface, ACCENT if selected else BORDER, center, 5, 1)
                if selected:
                    pygame.draw.circle(surface, ACCENT, center, 2)
                text = ctx.text_surface(label, size=18, color=TEXT if enabled else MUTED,
                                        max_width=rect.w-40)
                surface.blit(text, (28, (rect.h-text.get_height())//2))
            RMS.draw(ctx.widget_surface(key, rect.size, paint), rect.topleft)
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
        explanations = {
            'none': 'Offline preview. Agent slots have no automatic controller.',
            'hub': 'External Agents connect through the existing Hub after the game starts.',
            'mock_ai': 'Local rule BOT controls the Agent factions.',
        }
        explanation = explanations[config.selected_controller_backend]
        ctx.text(f'{ctx.backend.upper()}  /  {explanation}', geom['summary_rect'].topleft, size=16, color=MUTED, max_width=panel.w-56)
        buttons = self.world.get_singleton_component(StartMenuButtons)
        if buttons:
            for name, button in buttons.buttons.items():
                rect = geom['start_rect' if name == 'start_game' else 'quit_rect']
                button['rect'] = rect.copy()
                ctx.button(rect, button['text'], primary=name == 'start_game', hovered=button['hover'])
