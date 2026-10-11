"""Human command ingress. Principals are granted by the host, never by payloads."""

from dataclasses import dataclass


class HumanCommandPolicy:
    """Owner-thread permission facts updated at the native publication boundary.

    This policy is installed only by a Web host. It cannot mutate gameplay or
    grant authority from a client-supplied faction. Desktop controls retain their
    existing contracts and do not pay for the additional view cache.
    """
    def __init__(self, initial):
        self.mode = initial['mode']
        self.systems = frozenset(initial['systems'])
        self.interface = dict(initial['interface'])
        self.players = {r['components']['Player']['faction']: r['components']['Player']['player_type']
                        for r in initial['entities'] if 'Player' in r['components']}
        self.units = {}
        self.visible = {}
        self.has_fog = True

    def observe(self, delta):
        for uid in delta['removed']:
            self.units.pop(uid, None)
        for row in delta['units']:
            unit, position, count = row['unit'], row['position'], row['count']
            if unit and position and count:
                ap = row['action_points']
                self.units[row['id']] = (unit['faction'], (position['col'], position['row']),
                                        count['current_count'], ap['current_ap'] if ap else None)
            else:
                self.units.pop(row['id'], None)
        fog = delta['fog']
        self.has_fog = fog['enabled'] is not None
        if fog['full']:
            self.visible.clear()
        for entry in fog['factions']:
            visible = self.visible.setdefault(entry['faction'], set())
            for cell in entry['cells']:
                (visible.add if cell['visible'] else visible.discard)((cell['col'], cell['row']))

    def validate(self, kind, parameters, faction, status):
        fields = {'end_turn': set(), 'move': {'unit_id', 'position'},
                  'attack': {'unit_id', 'target_id'}, 'wait': {'unit_id'},
                  'garrison': {'unit_id'}, 'capture': {'unit_id', 'position'},
                  'fortify': {'unit_id', 'position'}}
        if not isinstance(kind, str) or kind not in fields:
            raise ValueError('Unknown human command')
        if not isinstance(parameters, dict) or set(parameters) != fields[kind]:
            raise ValueError('Invalid command parameters')
        required = {'move': 'movement_system', 'attack': 'combat_system'}.get(kind)
        if required and not self.interface.get(required):
            raise ValueError('Action is not available in this match')
        if kind in ('capture', 'fortify') and 'TerritorySystem' not in self.systems:
            raise ValueError('Territory actions are not available in this match')
        if kind == 'end_turn' and 'TurnSystem' not in self.systems:
            raise ValueError('Turn actions are not available in this match')
        if self.players.get(faction) != 'human':
            raise PermissionError('Faction is not a human-controlled slot')
        if status['game_over']:
            raise ValueError('Game is over')
        if self.mode == 'turn_based' and status['current_player'] != faction:
            raise PermissionError('Wait for your faction turn')
        if kind == 'end_turn' and self.mode != 'turn_based':
            raise ValueError('End Turn is available only in turn-based mode')
        for key in ('unit_id', 'target_id'):
            if key in parameters and (type(parameters[key]) is not int or not 0 <= parameters[key] < 2**64):
                raise ValueError('Invalid unit ID')
        if 'position' in parameters:
            position = parameters['position']
            if not isinstance(position, (list, tuple)) or len(position) != 2 or any(type(n) is not int for n in position):
                raise ValueError('Position must contain two integer coordinates')
            if any(abs(n) > 2**31-1 for n in position):
                raise ValueError('Position outside coordinate range')
        if 'unit_id' in parameters:
            unit = self.units.get(parameters['unit_id'])
            if unit is None or unit[0] != faction or unit[2] <= 0:
                raise PermissionError('Select a living unit of your faction')
            if kind in ('wait', 'garrison') and (unit[3] is None or unit[3] < 1):
                raise ValueError('No action points available')
        if kind == 'attack':
            target = self.units.get(parameters['target_id'])
            if target is None or target[2] <= 0 or (self.has_fog and target[0] != faction
                                                    and target[1] not in self.visible.get(faction, set())):
                raise PermissionError('Target is outside this view')


@dataclass(frozen=True)
class ViewGrant:
    view: str
    can_control: bool = False


class CommandGateway:
    def __init__(self, session):
        self.session = session

    def dispatch(self, grant, request):
        if not grant.can_control or grant.view == 'spectator':
            raise PermissionError('This connection is read-only')
        self.session.refresh()
        if str(request.get('epoch')) != str(self.session.controls.epoch):
            raise ValueError('Scene changed; reconnect before issuing commands')
        command = request.get('command')
        params = request.get('parameters', {})
        if not isinstance(params, dict):
            raise ValueError('Command parameters must be an object')
        params = dict(params)
        for key in ('unit_id', 'target_id'):
            if key in params:
                value = params[key]
                if (isinstance(value, bool) or not isinstance(value, (str, int))
                        or (isinstance(value, str) and not (value.isascii() and value.isdecimal()))):
                    raise ValueError('Unit IDs must be decimal integers')
                try:
                    params[key] = int(value)
                except ValueError:
                    raise ValueError('Unit IDs must be decimal integers') from None
                if not 0 <= params[key] < 2**64:
                    raise ValueError('Unit ID outside u64 range')
        if command == 'attack':
            snapshot = self.session.renderer.model.snapshot(grant.view)
            if str(params.get('target_id')) not in {row['id'] for row in snapshot['units']}:
                raise PermissionError('Target is outside this view')
        # A rejected browser command is a client error, not a damaged session.
        # Keep the publication fence, without LocalControls' fatal-error hook.
        try:
            return self.session.runtime.execute_human_command(command, params,
                faction=grant.view, expected_epoch=self.session.controls.epoch)
        finally:
            self.session.refresh()
