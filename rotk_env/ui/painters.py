"""Shared paint functions over the current presentation; no game writes."""
import pygame

from framework.engine import RMS
from .. import components as c
from ..prefabs.config import GameMode
from ..prefabs.controls import help_panel_lines, action_hotkey
from .context import ACCENT, BACKGROUND, BORDER, MUTED, PANEL, TEXT


def faction_badge(faction, center, radius=5):
    name = getattr(faction, 'value', faction)
    colors = {'wei': (110, 168, 255), 'shu': (240, 120, 120), 'wu': (128, 200, 155)}
    color = colors.get(name, TEXT)
    x, y = center
    if name == 'shu':
        RMS.polygon(color, [(x, y-radius), (x+radius, y), (x, y+radius), (x-radius, y)])
    elif name == 'wu':
        RMS.polygon(color, [(x, y-radius), (x+radius, y+radius), (x-radius, y+radius)])
    else:
        RMS.circle(color, center, radius)


def render_shell(system, ctx):
    world = system.world
    layout = ctx.layout
    ctx.panel(layout.top)
    ctx.panel(layout.sidebar)
    ctx.text('STARBench', (16, 16), size=26, color=ACCENT)
    state = world.get_singleton_component(c.GameState)
    clock = world.get_singleton_component(c.GameTime)
    mode = 'Real time' if state and state.game_mode == GameMode.REAL_TIME else 'Turn based'
    timing = clock.get_current_time_display() if clock and state and state.game_mode == GameMode.REAL_TIME else f'Turn {getattr(state, "turn_number", 0)}'
    phase = 'Simultaneous turns' if state and state.game_mode == GameMode.REAL_TIME else f'Active: {getattr(getattr(state, "current_player", None), "value", "—")}'
    ui = world.get_singleton_component(c.UIState)
    fog = world.get_singleton_component(c.FogOfWar)
    view = getattr(ui, 'view_faction', None) or getattr(state, 'current_player', None)
    view_label = getattr(view, 'value', '—').upper() if fog and fog.enabled else 'ALL'
    if state and state.game_over:
        phase = 'Game over'
    ctx.text(f'{mode}  /  {timing}  /  {phase}  /  View: {view_label}', (170, 12), size=20, max_width=layout.top.w-400)
    llm = next((s for s in world.systems if type(s).__name__ == 'LLMSystem'), None)
    client = getattr(llm, 'client', None)
    stats = world.get_singleton_component(c.GameStats)
    registered = len(getattr(stats, 'agent_id_to_faction', {})) if stats else 0
    native_facts = getattr(world, '_native_hub_facts', None)
    connected = getattr(client, 'connected', False)
    if native_facts is not None:
        registered = native_facts['registered_agents']
        connected = native_facts['connected']
    if ctx.controller == 'hub':
        controller = f'Hub {"connected" if connected else "disconnected"}'
    elif ctx.controller == 'mock_ai':
        controller = 'Local rule BOT'
    else:
        controller = 'Offline  /  Static AI slots — no controller'
    ctx.text(f'{ctx.backend.upper()}  /  {controller}  /  Registered: {registered}', (170, 37), size=16, color=MUTED, max_width=layout.top.w-400)
    counts = system._current_faction_counts()
    RMS.rect(PANEL, (0, layout.viewport.bottom-34, min(350, layout.viewport.w), 34))
    x = 16
    for faction, count in counts.items():
        faction_badge(faction, (x+4, layout.viewport.bottom-17))
        label = f'{getattr(faction, "value", faction).upper()}: {count}'
        ctx.text(label, (x+16, layout.viewport.bottom-24), size=16)
        x += 110
    # Legend is limited to geometric meanings; it never advertises permission.
    RMS.rect(PANEL, (8, layout.viewport.y+8, 310, 26))
    ctx.text('Blue: reachable  /  Gold: attack range', (16, layout.viewport.y+12), size=16, color=TEXT)
    with RMS.clip(layout.content):
        ctx.text('Mini-map', (layout.minimap.x, layout.minimap.y-2), size=16, color=ACCENT)
    if layout.max_scroll:
        thumb_h = max(24, int(layout.content.h**2/(layout.content.h+layout.max_scroll)))
        thumb_y = layout.content.y+int(ctx.scroll/layout.max_scroll*(layout.content.h-thumb_h))
        RMS.rect(BORDER, (layout.sidebar.right-6, thumb_y, 3, thumb_h))
    render_modal(system, ctx)


def render_selection_and_log(world, ctx):
    ui = world.get_singleton_component(c.UIState)
    rect = ctx.layout.selection
    entity = ui.selected_unit if ui else None
    unit = world.get_component(entity, c.Unit) if entity is not None else None
    heading = None
    lines = []
    if unit:
        count = world.get_component(entity, c.UnitCount)
        mp = world.get_component(entity, c.MovementPoints)
        combat = world.get_component(entity, c.Combat)
        pos = world.get_component(entity, c.HexPosition)
        status = world.get_component(entity, c.UnitStatus)
        heading = f'{unit.faction.value.upper()}  ·  {unit.unit_type.value.title()}'
        if count:
            lines.append(f'Strength: {count.current_count}/{count.max_count}')
        if mp and count:
            lines.append(f'Movement: {mp.current_mp:.1f}/{mp.get_effective_movement(count):.1f}')
        if combat:
            lines.append(f'Attack: {combat.base_attack}')
        if pos:
            lines.append(f'Location: ({pos.col}, {pos.row})')
        if status:
            lines.append(f'Status: {getattr(status.current_status, "value", status.current_status)}')
    # Read current facts every frame. Cached pixels hold no World/component refs.
    faction = unit.faction.value if unit else None
    key = ('selection', heading, tuple(lines), faction, ctx.layout.scale,
           tuple(id(ctx.font(size)) for size in (14,16,18,20)))
    def paint_selection(surface):
        surface.fill(PANEL)
        pygame.draw.rect(surface, BORDER, surface.get_rect(), 1)
        surface.blit(ctx.text_surface('Selected unit', size=20, color=ACCENT), (10,8))
        if heading is None:
            surface.blit(ctx.text_surface('Select a human unit on the map.', color=MUTED, max_width=rect.w-20), (10,44))
            surface.blit(ctx.text_surface('1 infantry  /  2 cavalry  /  3–5 archers', size=14, color=MUTED, max_width=rect.w-20), (10,70))
        else:
            badge = ctx.tactical_surface('badge:'+faction, (12,12))
            surface.blit(badge, (9,38))
            surface.blit(ctx.text_surface(heading,size=20,max_width=rect.w-40), (30,36))
            for index, line in enumerate(lines):
                surface.blit(ctx.text_surface(line,size=16,max_width=rect.w-24), (12,64+index*21*ctx.layout.scale))
    with RMS.clip(ctx.layout.content):
        RMS.draw(ctx.widget_surface(key, rect.size, paint_selection), rect.topleft)
        rect = ctx.layout.log
        log = world.get_singleton_component(c.BattleLog)
        entries = tuple(f'[{entry.game_time_display or "00:00"}] {entry.message}'
                        for entry in log.get_visible_entries()) if log and log.show_log and not ctx.log_collapsed else ()
        key = ('log', ctx.log_collapsed, entries, ctx.layout.scale,
               id(ctx.font(18)), id(ctx.font(14)))
        def paint_log(surface):
            surface.fill(PANEL)
            pygame.draw.rect(surface, BORDER, surface.get_rect(), 1)
            surface.blit(ctx.text_surface(f'Battle log  {"+" if ctx.log_collapsed else "−"}',color=ACCENT), (10,8))
            surface.set_clip((8,32,rect.w-16,rect.h-38))
            for index, text in enumerate(entries):
                surface.blit(ctx.text_surface(text,size=14,color=MUTED,max_width=rect.w-20), (10,34+index*19*ctx.layout.scale))
            surface.set_clip(None)
        RMS.draw(ctx.widget_surface(key, rect.size, paint_log), rect.topleft)


def action_rects(panel, ctx):
    rect = ctx.layout.actions
    row_h = round(38*ctx.layout.scale)
    return [pygame.Rect(rect.x+8, rect.y+32+i*row_h, rect.w-16, row_h-4) for i in range(len(panel.available_actions))]


def render_actions(panel, ctx):
    rect = ctx.layout.actions
    with RMS.clip(ctx.layout.content):
        ctx.panel(rect, 'Unit actions')
        if not panel.visible:
            ctx.text('Choose a unit or a target.', (rect.x+10, rect.y+44), size=16, color=MUTED, max_width=rect.w-20)
            return
        for action, button in zip(panel.available_actions, action_rects(panel, ctx)):
            key = action_hotkey(action.action_type.value)
            visual_key = ('action', action.label, action.cost_description, key,
                          action.enabled, id(ctx.font(18)), id(ctx.font(16)), id(ctx.font(14)))
            def paint(surface):
                surface.fill((39,56,68) if action.enabled else BACKGROUND)
                pygame.draw.rect(surface, BORDER, surface.get_rect(), 1)
                surface.blit(ctx.text_surface(action.label, size=18, color=TEXT if action.enabled else MUTED), (8,4))
                surface.blit(ctx.text_surface(f'[{key}]', size=16, color=ACCENT if action.enabled else MUTED), (button.w-33,4))
                surface.blit(ctx.text_surface(action.cost_description, size=14, color=MUTED, max_width=button.w-16), (8,20))
            RMS.draw(ctx.widget_surface(visual_key, button.size, paint), button.topleft)


def render_modal(system, ctx):
    world = system.world
    ui = world.get_singleton_component(c.UIState)
    if not ui or not (ui.show_help or ui.show_stats):
        return
    layout = ctx.layout
    with RMS.layer(200):
        width = min(980, layout.top.w-80)
        height = min(640, layout.viewport.h-40)
        rect = pygame.Rect((layout.top.w-width)//2, layout.top.h+20, width, height)
        ctx.panel(rect, 'Controls  /  F1 to close' if ui.show_help else 'Game statistics  /  Tab to close')
        if ui.show_help:
            lines = help_panel_lines()
        else:
            stats = world.get_singleton_component(c.GameStats)
            lines = []
            for faction, values in getattr(stats, 'faction_stats', {}).items():
                lines.append(f'{getattr(faction, "value", faction).upper()}:')
                lines.extend(f'  {key}: {value}' for key, value in values.items())
                lines.append('')
        # Two columns for help; long stats remain scrollable in the modal.
        columns = 2 if ui.show_help else 1
        split = (len(lines)+columns-1)//columns
        row_h = 20*layout.scale
        max_scroll = max(0, int(split*row_h-(height-62)))
        ctx.modal_scroll = min(ctx.modal_scroll, max_scroll)
        with RMS.clip(pygame.Rect(rect.x+12, rect.y+42, rect.w-24, rect.h-54)):
            for i, line in enumerate(lines):
                column, row = divmod(i, split or 1)
                ctx.text(line, (rect.x+16+column*(width//columns), rect.y+46+row*row_h-ctx.modal_scroll),
                         size=16, color=ACCENT if line.endswith(':') else TEXT, max_width=width//columns-32)
