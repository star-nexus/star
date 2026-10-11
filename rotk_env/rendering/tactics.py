"""Read-only tactical hints over an authorized view, with no drawing or commands.

Reuse the game's MP budget, hex geometry and weighted path query. Unknown terrain
and hidden enemy occupancy never participate in these browser affordances; Rust
still decides whether a submitted command can actually execute.
"""
from collections import OrderedDict

from rotk_env import components as c
from rotk_env.utils.hex_utils import HexMath, PathFinding
from rotk_env.utils.map_query import movement_costs, impassable_terrain


class TacticalProjection:
    def __init__(self, world):
        self.world = world
        self.costs = movement_costs(world)
        self.impassable = impassable_terrain(world)
        self.cache = OrderedDict()
        self.computations = 0

    def selection(self, snapshot, raw_units, unit_id):
        if unit_id is None:
            return None
        unit = next((u for u in snapshot['units'] if u['id'] == unit_id), None)
        if (unit is None or snapshot['hud'].get('game_over') or
                (snapshot['view'] != 'spectator' and unit['faction'] != snapshot['view'])):
            return None
        raw = raw_units[unit_id]
        movement = c.MovementPoints(**raw['movement_points']) if raw['movement_points'] else None
        count = c.UnitCount(**raw['count'])
        moving = raw['movement'] and raw['movement']['is_moving']
        budget = max(0, movement.spendable(count)) if movement and not movement.has_moved and not moving else 0
        combat = self.world.get_component(int(unit_id), c.Combat)
        radius = max(0, combat.attack_range) if combat else 0
        commands = snapshot['scene']['commands']
        if 'move' not in commands:
            budget = 0
        if 'attack' not in commands:
            radius = 0
        origin = (unit['col'], unit['row'])
        local = HexMath.hex_in_range(*origin, max(budget, radius))
        known = {(t['col'], t['row']) for t in snapshot['tiles']
                 if t['visibility'] != 'hidden' and (t['col'], t['row']) in local}
        # Only authorized units contribute blockers, destinations and target IDs.
        occupants = tuple(sorted((u['id'], u['col'], u['row'], u['faction'])
                                 for u in snapshot['units'] if u['id'] != unit_id
                                 and (u['col'], u['row']) in local))
        key = (unit_id, origin, budget, radius, unit['faction'], frozenset(known), occupants)
        if key not in self.cache:
            occupied = {(col, row) for _, col, row, _ in occupants}
            enemies = {(col, row) for _, col, row, faction in occupants if faction != unit['faction']}
            reachable = PathFinding.get_movement_range(origin, budget,
                (self.impassable & known) | enemies, walkable=known,
                step_cost=lambda pos: self.costs.get(pos, 999)) if budget else set()
            attack = HexMath.hex_in_range(*origin, radius) & known if radius else set()
            reachable -= occupied | {origin}
            attack.discard(origin)
            self.cache[key] = dict(unit_id=unit_id, origin=list(origin),
                movement=[list(pos) for pos in sorted(reachable)],
                attack=[list(pos) for pos in sorted(attack)],
                targets=[uid for uid, col, row, faction in occupants
                         if faction != unit['faction'] and (col, row) in attack])
            self.computations += 1
            if len(self.cache) > 32:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]
