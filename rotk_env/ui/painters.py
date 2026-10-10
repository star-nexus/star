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
    timing = clock.get_current_time_display() if clock else f'Turn {getattr(state, "turn_number", 0)}'
    phase = 'Simultaneous turns' if state and state.game_mode == GameMode.REAL_TIME else f'Active: {getattr(getattr(state, "current_player", None), "value", "—")}'
    ctx.text(f'{mode}  /  {timing}  /  {phase}', (170, 12), size=20, max_width=layout.top.w-400)
    llm = next((s for s in world.systems if type(s).__name__ == 'LLMSystem'), None)
    client = getattr(llm, 'client', None)
    stats = world.get_singleton_component(c.GameStats)
    registered = len(getattr(stats, 'agent_id_to_faction', {})) if stats else 0
    if ctx.controller == 'hub':
        controller = f'Hub {"connected" if getattr(client, "connected", False) else "disconnected"}  /  Registered: {registered}'
    elif ctx.controller == 'mock_ai':
        controller = 'Local rule BOT'
    else:
        controller = 'Offline  /  Static AI slots — no controller'
    ctx.text(f'{ctx.backend.upper()}  /  {controller}', (170, 37), size=16, color=MUTED, max_width=layout.top.w-400)
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
    with RMS.clip(ctx.layout.content):
        ctx.panel(rect, 'Selected unit')
        entity = ui.selected_unit if ui else None
        unit = world.get_component(entity, c.Unit) if entity is not None else None
        if not unit:
            ctx.text('Select a human unit on the map.', (rect.x+10, rect.y+44), color=MUTED, max_width=rect.w-20)
            ctx.text('1 infantry  /  2 cavalry  /  3–5 archers', (rect.x+10, rect.y+70), size=14, color=MUTED, max_width=rect.w-20)
        else:
            count = world.get_component(entity, c.UnitCount)
            mp = world.get_component(entity, c.MovementPoints)
            combat = world.get_component(entity, c.Combat)
            pos = world.get_component(entity, c.HexPosition)
            status = world.get_component(entity, c.UnitStatus)
            faction_badge(unit.faction, (rect.x+15, rect.y+44))
            ctx.text(f'{unit.faction.value.upper()}  ·  {unit.unit_type.value.title()}', (rect.x+30, rect.y+36), size=20, max_width=rect.w-40)
            lines = []
            if count:
                lines.append(f'Strength: {count.current_count}/{count.max_count}')
            if mp and count:
                lines.append(f'Movement: {mp.current_mp:.1f}/{mp.get_effective_movement(count):.1f}')
            if combat:
                lines.append(f'Attack: {combat.base_attack}')
            if pos:
                lines.append(f'Location: ({pos.col}, {pos.row})')
            if status:
                value = getattr(status.current_status, 'value', status.current_status)
                lines.append(f'Status: {value}')
            for index, line in enumerate(lines):
                ctx.text(line, (rect.x+12, rect.y+64+index*21*ctx.layout.scale), size=16, max_width=rect.w-24)
        rect = ctx.layout.log
        ctx.panel(rect)
        ctx.text(f'Battle log  {"+" if ctx.log_collapsed else "−"}', (rect.x+10, rect.y+8), color=ACCENT)
        log = world.get_singleton_component(c.BattleLog)
        if log and log.show_log and not ctx.log_collapsed:
            with RMS.clip(pygame.Rect(rect.x+8, rect.y+32, rect.w-16, rect.h-38)):
                for index, entry in enumerate(log.get_visible_entries()):
                    ctx.text(f'[{entry.game_time_display or "00:00"}] {entry.message}',
                             (rect.x+10, rect.y+34+index*19*ctx.layout.scale), size=14, color=MUTED, max_width=rect.w-20)


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
            RMS.rect((39, 56, 68) if action.enabled else BACKGROUND, button)
            RMS.rect(BORDER, button, 1)
            color = TEXT if action.enabled else MUTED
            ctx.text(action.label, (button.x+8, button.y+4), size=18, color=color)
            key = action_hotkey(action.action_type.value)
            ctx.text(f'[{key}]', (button.right-33, button.y+4), size=16, color=ACCENT if action.enabled else MUTED)
            ctx.text(action.cost_description, (button.x+8, button.y+20), size=14, color=MUTED, max_width=button.w-16)


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
