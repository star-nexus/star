"""One scene's layout, input ownership and bounded pygame resources."""
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps

import pygame

from framework.ecs import profiling
from framework.engine import RMS

VISUAL_VERSION = "starbench-ui-v2"
BACKGROUND = (16, 24, 32)
PANEL = (27, 39, 51)
BORDER = (59, 75, 88)
ACCENT = (200, 166, 106)
TEXT = (230, 232, 228)
MUTED = (169, 180, 188)


@dataclass(frozen=True)
class Layout:
    top: pygame.Rect
    viewport: pygame.Rect
    sidebar: pygame.Rect
    content: pygame.Rect
    minimap: pygame.Rect
    selection: pygame.Rect
    actions: pygame.Rect
    log: pygame.Rect
    footer: pygame.Rect
    scale: float
    max_scroll: int


def viewport_for(world):
    from ..prefabs.config import GameConfig
    ctx = getattr(world, "_ui_context", None)
    return ctx.layout.viewport if ctx else pygame.Rect(0, 0, GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)


def controller_available(runtime_backend, controller):
    return runtime_backend != "rust" or controller == "none"


class UiContext:
    """Owned by the scene/session, referenced by its display systems only."""
    visual_version = VISUAL_VERSION

    def __init__(self, *, backend="python", controller="none"):
        self.backend = backend
        self.controller = controller
        self.scroll = 0
        self.log_collapsed = False
        self.modal_scroll = 0
        self._size = None
        self._layout_key = None
        self._camera_center = None
        self._bound = []
        self._fonts = {}
        self._text = OrderedDict()
        self._surfaces = OrderedDict()
        self._widgets = OrderedDict()
        self._widget_bytes = 0
        self._surface_bytes = 0
        self._text_bytes = 0
        self.closed = False
        self.sync()
        profiling.profiler.set_metadata(visual_version=self.visual_version)

    def sync(self, world=None):
        from ..prefabs.config import GameConfig
        surface = pygame.display.get_surface()
        size = surface.get_size() if surface and surface.get_width() > 1 else (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        key = (size, self.scroll, self.log_collapsed)
        if key == self._layout_key and (world is None or self._camera_center is not None):
            return
        w, h = size
        scale = min(1.25, max(1., min(w/1200, h/800)))
        gap, top_h, side_w = round(12*scale), round(64*scale), round(304*scale)
        top = pygame.Rect(0, 0, w, top_h)
        side = pygame.Rect(w-side_w-gap, top_h+gap, side_w, h-top_h-2*gap)
        footer = pygame.Rect(side.x+gap, side.bottom-round(48*scale), side.w-2*gap, round(36*scale))
        content = pygame.Rect(side.x+gap, side.y+gap, side.w-2*gap, footer.y-side.y-2*gap)
        heights = [round(v*scale) for v in (152, 182, 268, 28 if self.log_collapsed else 158)]
        content_h = sum(heights)+3*gap
        max_scroll = max(0, content_h-content.h)
        self.scroll = min(max_scroll, max(0, self.scroll))
        y = content.y-self.scroll
        rects = []
        for height in heights:
            rects.append(pygame.Rect(content.x, y, content.w, height))
            y += height+gap
        viewport = pygame.Rect(0, top_h, side.x-gap, h-top_h)
        old = getattr(self, "layout", None)
        if world is not None:
            from ..components import Camera
            camera = world.get_singleton_component(Camera)
            if camera is not None:
                # First attachment also moves the old full-window centre into
                # the viewport. Offsets remain absolute screen coordinates.
                previous = self._camera_center or (GameConfig.WINDOW_WIDTH/2, GameConfig.WINDOW_HEIGHT/2)
                if previous != viewport.center:
                    camera.offset_x += viewport.centerx-previous[0]
                    camera.offset_y += viewport.centery-previous[1]
                self._camera_center = viewport.center
        self.layout = Layout(top, viewport, side, content, *rects, footer, scale, max_scroll)
        self._size = size
        self._layout_key = (size, self.scroll, self.log_collapsed)

    def attach(self, world):
        world._ui_context = self
        self.sync(world)
        for system in world.systems:
            self.bind(system)

    def bind(self, system):
        name = type(system).__name__
        layers = {"MapRenderSystem": 10, "EffectRenderSystem": 20, "UnitRenderSystem": 30,
                  "UIRenderSystem": 90, "PanelRenderSystem": 100, "MiniMapSystem": 110,
                  "UnitActionButtonSystem": 120, "UIButtonSystem": 130}
        if name not in layers or getattr(system, "_ui_bound", False):
            return
        original = system.update
        @wraps(original)
        def update(dt):
            self.sync(system.world)
            with RMS.layer(layers[name]):
                if layers[name] < 90:
                    with RMS.clip(self.layout.viewport):
                        return original(dt)
                if name == "MiniMapSystem":
                    with RMS.clip(self.layout.content):
                        return original(dt)
                return original(dt)
        system.update = update
        system._ui_bound = True
        self._bound.append((system, original))

    def font(self, size=18):
        px = max(14, round(size*self.layout.scale))
        if px not in self._fonts:
            self._fonts[px] = pygame.font.Font(None, px)
        return self._fonts[px]

    def text_surface(self, text, *, size=18, color=TEXT, max_width=None):
        text = str(text)
        font = self.font(size)
        if max_width is not None and font.size(text)[0] > max_width:
            while text and font.size(text+"...")[0] > max_width:
                text = text[:-1]
            text += "..."
        key = (id(font), text, color)
        surface = self._text.get(key)
        if surface is None:
            surface = font.render(text, True, color)
            cost = surface.get_pitch()*surface.get_height()
            self._text[key] = surface
            self._text_bytes += cost
            while len(self._text) > 1024 or self._text_bytes > 8*1024*1024:
                _, discarded = self._text.popitem(last=False)
                self._text_bytes -= discarded.get_pitch()*discarded.get_height()
        else:
            self._text.move_to_end(key)
        return surface

    def text(self, text, pos, *, size=18, color=TEXT, max_width=None, centered=False):
        surface = self.text_surface(text, size=size, color=color, max_width=max_width)
        if centered:
            pos = (pos[0]-surface.get_width()//2, pos[1])
        RMS.draw(surface, pos)
        return surface

    def tactical_surface(self, kind, size, points=None):
        key = (kind, tuple(size), tuple(points or ()))
        surface = self._surfaces.get(key)
        if surface is not None:
            self._surfaces.move_to_end(key)
            return surface
        surface = pygame.Surface(size, pygame.SRCALPHA)
        if kind.startswith('badge:'):
            name = kind.split(':', 1)[1]
            x, y = size[0]//2, size[1]//2
            r = min(size)//2-1
            colors = {'wei': (110,168,255), 'shu': (240,120,120), 'wu': (128,200,155)}
            color = colors.get(name, TEXT)
            if name == 'shu':
                pygame.draw.polygon(surface, color, [(x,y-r),(x+r,y),(x,y+r),(x-r,y)])
            elif name == 'wu':
                pygame.draw.polygon(surface, color, [(x,y-r),(x+r,y+r),(x-r,y+r)])
            else:
                pygame.draw.circle(surface, color, (x,y), r)
        elif points:
            if kind == "move":
                pygame.draw.polygon(surface, (100, 160, 225, 38), points)
                pygame.draw.polygon(surface, (125, 185, 240, 125), points, 1)
            else:
                pygame.draw.polygon(surface, (*ACCENT, 150), points, 2)
        else:
            center = (size[0]//2, size[1]//2)
            pygame.draw.circle(surface, (235, 114, 105, 180), center, min(size)//2-2, 2)
        cost = surface.get_pitch()*surface.get_height()
        if cost <= 32*1024*1024:
            self._surfaces[key] = surface
            self._surface_bytes += cost
            while len(self._surfaces) > 128 or self._surface_bytes > 32*1024*1024:
                _, discarded = self._surfaces.popitem(last=False)
                self._surface_bytes -= discarded.get_pitch()*discarded.get_height()
        return surface

    def widget_surface(self, key, size, paint):
        """Immutable paint fragments; keys contain only visual facts, not ECS refs."""
        key = (key, tuple(size))
        surface = self._widgets.get(key)
        if surface is not None:
            self._widgets.move_to_end(key)
            return surface
        surface = pygame.Surface(size)
        paint(surface)
        cost = surface.get_pitch()*surface.get_height()
        if cost <= 8*1024*1024:
            self._widgets[key] = surface
            self._widget_bytes += cost
            while len(self._widgets) > 128 or self._widget_bytes > 8*1024*1024:
                _, discarded = self._widgets.popitem(last=False)
                self._widget_bytes -= discarded.get_pitch()*discarded.get_height()
        return surface

    def panel(self, rect, title=None):
        if rect.w <= 0 or rect.h <= 0:
            return
        def paint(surface):
            surface.fill(PANEL)
            pygame.draw.rect(surface, BORDER, surface.get_rect(), 1)
        RMS.draw(self.widget_surface('panel', rect.size, paint), rect.topleft)
        if title:
            self.text(title, (rect.x+10, rect.y+8), color=ACCENT, size=20)

    def modal_visible(self, world):
        from ..components import UIState
        from ..components.unit_action_buttons import ActionConfirmDialog
        ui = world.get_singleton_component(UIState)
        confirm = world.get_singleton_component(ActionConfirmDialog)
        return bool((ui and (ui.show_help or ui.show_stats)) or (confirm and confirm.visible))

    def owns(self, pos, world):
        view = self.layout.viewport
        overlays = (pygame.Rect(8, view.y+8, 310, 26),
                    pygame.Rect(0, view.bottom-34, min(350, view.w), 34))
        return (self.modal_visible(world) or not view.collidepoint(pos)
                or any(rect.collidepoint(pos) for rect in overlays))

    def handle_click(self, pos, world):
        if self.layout.content.collidepoint(pos) and pygame.Rect(self.layout.log.x, self.layout.log.y, self.layout.log.w, 28).collidepoint(pos):
            self.log_collapsed = not self.log_collapsed
            self.sync(world)
        return self.owns(pos, world)

    def scroll_at(self, pos, amount, world):
        if self.modal_visible(world):
            self.modal_scroll = max(0, self.modal_scroll-int(amount)*24)
            return True
        if self.layout.sidebar.collidepoint(pos):
            self.scroll = min(self.layout.max_scroll, max(0, self.scroll-int(amount)*36))
            self.sync(world)
            return True
        return self.owns(pos, world)

    def cache_stats(self):
        return dict(tactical_entries=len(self._surfaces), tactical_bytes=self._surface_bytes,
                    text_entries=len(self._text), text_bytes=self._text_bytes,
                    widget_entries=len(self._widgets), widget_bytes=self._widget_bytes)

    def unbind(self):
        for system, original in self._bound:
            system.update = original
            system._ui_bound = False
        self._bound.clear()

    def close(self):
        self.unbind()
        self._surfaces.clear()
        self._widgets.clear()
        self._widget_bytes = 0
        self._text.clear()
        self._fonts.clear()
        self._surface_bytes = self._text_bytes = 0
        self.closed = True
