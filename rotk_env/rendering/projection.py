"""RoTK semantic read model. Internal native deltas never leave this boundary.

One host consumes every native publication. View snapshots are detached, omit
hidden enemies and retain last-seen terrain facts. IDs are decimal strings on
the Web boundary so JavaScript never rounds Rust u64 identifiers.
"""

from copy import deepcopy

from rotk_env import components as c
from rotk_env.prefabs.config import GameConfig, Faction, HexOrientation
from rotk_env.utils.hex_utils import HexConverter

TERRAIN_ASSETS = {
    'plain': 'texture/terrain/plain/Hex - Plains (lush) 5.png',
    'forest': 'texture/terrain/forest/Hex - Forest, conifer (lush).png',
    'mountain': 'texture/terrain/mountain/Hex - Mountains, medium (lush).png',
    'hill': 'texture/terrain/hill/Hex - Hills (lush).png',
    'water': 'texture/terrain/water/Hex - Water - Ocean (still water) 5 .png',
    'urban': 'texture/terrain/urban/Hex - Urban - City (lush).png',
    'city': 'texture/terrain/urban/Hex - Urban - City (lush).png',
}


class RenderProjection:
    def __init__(self, world, initial):
        self.epoch = None
        self.revision = self.tick = 0
        self.sequence = 0
        self.units = {}
        self.visuals = {}
        self.visible = {}
        self.explored = {}
        self.known_tiles = {}
        self.has_fog = False
        self.state = {}
        self.size = initial['rules']['hex_size']
        self.converter = HexConverter(self.size, HexOrientation(initial['rules']['hex_orientation']))
        map_data = world.get_singleton_component(c.MapData)
        self.tiles = {}
        self._tile_positions = {}
        for pos, uid in sorted(map_data.tiles.items()):
            terrain = world.get_component(uid, c.Terrain)
            control = world.get_component(uid, c.TerritoryControl)
            kind = terrain.terrain_type.value if terrain else 'plain'
            color = list(GameConfig.TERRAIN_COLORS.get(terrain.terrain_type, (135, 141, 106))) if terrain else [135, 141, 106]
            row = dict(id=str(uid), col=pos[0], row=pos[1], terrain=kind,
                       color=color, asset=TERRAIN_ASSETS.get(kind), owner=None, fortified=False)
            if control:
                row.update(owner=control.controlling_faction.value if control.controlling_faction else None,
                           fortified=control.fortified)
            self.tiles[str(uid)] = row
            self._tile_positions[pos] = str(uid)
        self.scene = dict(map_id=map_data.map_id, width=map_data.width, height=map_data.height,
            coordinate_system='star-offset-v1', hex_size=self.size,
            orientation=initial['rules']['hex_orientation'],
            tiles=[{k: row[k] for k in ('id', 'col', 'row')} for row in self.tiles.values()],
            factions=[dict(id=f.value, color=list(GameConfig.FACTION_COLORS[f]))
                      for f in Faction if f in GameConfig.FACTION_COLORS])
        self.scene['commands'] = ['wait', 'garrison']
        for command, capability in (('move', 'movement_system'), ('attack', 'combat_system')):
            if initial['interface'].get(capability):
                self.scene['commands'].append(command)
        if 'TerritorySystem' in initial['systems']:
            self.scene['commands'].extend(['capture', 'fortify'])
        if 'TurnSystem' in initial['systems']:
            self.scene['commands'].append('end_turn')

    def apply(self, delta):
        if self.epoch is not None and self.epoch != delta['epoch']:
            raise ValueError('Render epoch changed; recreate the projection')
        if self.epoch is not None and delta['revision'] < self.revision:
            raise ValueError('Stale render publication')
        if self.epoch is None and not delta['fog']['full']:
            raise ValueError('Render projection requires a Fog baseline')
        self.epoch, self.revision, self.tick = delta['epoch'], delta['revision'], delta['tick']
        self.sequence += 1
        for uid in delta['removed']:
            self.units.pop(str(uid), None)
        for row in delta['units']:
            self.units[str(row['id'])] = deepcopy(row)
        for row in delta['tiles']:
            tile = self.tiles.get(str(row['id']))
            if tile:
                tile.update(owner=row['control']['controlling_faction'],
                            fortified=row['control']['fortified'])
        self.state.update(deepcopy(delta['state']))
        fog = delta['fog']
        self.has_fog = fog['enabled'] is not None
        if fog['full']:
            self.visible.clear()
            self.explored.clear()
        for entry in fog['factions']:
            faction = entry['faction']
            visible = self.visible.setdefault(faction, set())
            explored = self.explored.setdefault(faction, set())
            for cell in entry['cells']:
                pos = (cell['col'], cell['row'])
                for cells, key in ((visible, 'visible'), (explored, 'explored')):
                    (cells.add if cell[key] else cells.discard)(pos)
        for faction, explored in self.explored.items():
            known = self.known_tiles.setdefault(faction, {})
            visible = self.visible.get(faction, set())
            for pos in explored | visible:
                uid = self._tile_positions.get(pos)
                if uid is None:
                    continue
                if pos in visible:
                    known[uid] = self.tiles[uid].copy()
                elif uid not in known:
                    known[uid] = {**self.tiles[uid], 'owner': None, 'fortified': False}
        for uid in delta['visuals']['removed']:
            self.visuals.pop(str(uid), None)
        for row in delta['visuals']['rows']:
            self.visuals[str(row['id'])] = deepcopy(row['components'])

    def _visible(self, faction, pos):
        # Native Fog.enabled is a desktop paint switch; it never grants a remote
        # faction access to hidden authoritative facts.
        return faction is None or not self.has_fog or pos in self.visible.get(faction, set())

    def _unit(self, uid, row, faction):
        position, unit, count = row['position'], row['unit'], row['count']
        if not position or not unit or not count or count['current_count'] <= 0:
            return None
        own = faction == unit['faction']
        pos = (position['col'], position['row'])
        if not own and not self._visible(faction, pos):
            return None
        x, y = self.converter.hex_to_pixel(*pos)
        movement = row['movement']
        if movement and movement['is_moving'] and movement['start_pixel_pos'] and movement['target_pixel_pos']:
            progress = min(1.0, max(0.0, movement['progress']))
            a, b = movement['start_pixel_pos'], movement['target_pixel_pos']
            x, y = (a[i] + (b[i]-a[i])*progress for i in range(2))
        result = dict(id=uid, col=pos[0], row=pos[1], faction=unit['faction'],
            unit_type=unit['unit_type'], count=count['current_count'], max_count=count['max_count'],
            position=[x/self.size, -y/self.size],
            asset=f"texture/units/{unit['faction'].lower()}/{unit['unit_type']}.png")
        if own or faction is None:
            ap, mp = row['action_points'], row['movement_points']
            result.update(ap=ap['current_ap'] if ap else None, max_ap=ap['max_ap'] if ap else None,
                          mp=mp['current_mp'] if mp else None)
        return result

    def _visual_rows(self, faction, units):
        out = []
        for uid, components in self.visuals.items():
            for kind, row in components.items():
                pos = row.get('world_position', row.get('effect_position', row.get('start_pos')))
                if kind == 'attack':
                    if uid not in units:
                        continue
                    target = row['target_position']
                    if not self._visible(faction, tuple(target)):
                        continue
                    target_xy = self.converter.hex_to_pixel(*target)
                    out.append(dict(id=uid, kind=kind, position=units[uid]['position'],
                        target=[target_xy[0]/self.size, -target_xy[1]/self.size], progress=row['progress']))
                elif pos and self._visible(faction, self.converter.pixel_to_hex(*pos)):
                    if kind == 'projectile' and not self._visible(faction, self.converter.pixel_to_hex(*row['target_pos'])):
                        continue
                    data = dict(id=uid, kind=kind, position=[pos[0]/self.size, -pos[1]/self.size])
                    if kind == 'damage':
                        data.update(text=row['text'], color=row['color'],
                                    progress=row['elapsed_time']/max(row['lifetime'], .001))
                    elif kind == 'projectile':
                        target = row['target_pos']
                        p = min(1.0, max(0.0, row['flight_progress']))
                        data['position'] = [(pos[0]+(target[0]-pos[0])*p)/self.size,
                                            -(pos[1]+(target[1]-pos[1])*p)/self.size]
                    out.append(data)
        return out

    def snapshot(self, view='spectator'):
        if self.epoch is None:
            raise ValueError('Render projection has no baseline')
        faction = None if view == 'spectator' else view
        if faction is not None and faction not in {f.value for f in Faction}:
            raise ValueError('Unknown view')
        units = {uid: result for uid, row in self.units.items()
                 if (result := self._unit(uid, row, faction)) is not None}
        tiles = []
        known = self.known_tiles.get(faction, {})
        for uid, tile in self.tiles.items():
            pos = (tile['col'], tile['row'])
            if self._visible(faction, pos):
                tiles.append({**tile, 'visibility': 'visible'})
            elif pos in self.explored.get(faction, set()):
                tiles.append({**known[uid], 'visibility': 'explored'})
            else:
                tiles.append(dict(id=uid, col=pos[0], row=pos[1], visibility='hidden',
                                  terrain=None, asset=None, color=[55, 64, 66], owner=None, fortified=False))
        state = self.state.get('GameState', {})
        clock = self.state.get('GameTime', {})
        return deepcopy(dict(schema=1, kind='snapshot', epoch=str(self.epoch),
            revision=str(self.revision), tick=str(self.tick), sequence=self.sequence,
            renderer_id='threejs', visual_version='starbench-web-v3', view=view,
            scene=self.scene, units=list(units.values()), tiles=tiles,
            visuals=self._visual_rows(faction, units),
            hud={key: state.get(key) for key in ('current_player', 'turn_number', 'game_over', 'winner', 'end_reason')}
                | {'mode': state.get('game_mode'), 'elapsed': clock.get('game_elapsed_time', 0)}))


def diff_snapshot(previous, current):
    """Diff complete authorized views, including visibility-only births/removals."""
    if previous is None or previous['epoch'] != current['epoch'] or previous['view'] != current['view']:
        return deepcopy(current)
    packet = {key: current[key] for key in ('schema', 'epoch', 'revision', 'tick', 'sequence',
                                          'renderer_id', 'visual_version', 'view', 'hud', 'visuals')}
    packet.update(kind='delta', base_sequence=previous['sequence'])
    for key in ('units', 'tiles'):
        before = {row['id']: row for row in previous[key]}
        after = {row['id']: row for row in current[key]}
        packet[key] = [row for uid, row in after.items() if before.get(uid) != row]
        if key == 'units':
            packet['removed'] = [uid for uid in before if uid not in after]
    return deepcopy(packet)
