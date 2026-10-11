"""Compare all renderer adapters with identical rules, inputs and Agent reads.

Run with PYTHONPATH=. .venv/bin/python and native + pygame installed. SDL uses
the dummy driver; this probe never changes the checkout or native binary.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', HEADLESS='0')

from framework.engine.game_engine import GameEngine
from rotk_env.prefabs.config import Faction, PlayerType
from rotk_env.rendering.commands import CommandGateway, ViewGrant
from rotk_env.rendering.pygame.display import sync_game_config_from_display
from rotk_env.runtime.session import NativeSession


class Frozen(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 12, 12)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def unit_components(state):
    return {row['components']['Unit']['name']: row['components']
            for row in state['entities'] if 'Unit' in row['components']}


def initial_identity(state):
    return dict(entity_counter=state['entity_counter'],
        ui_buttons=[dict(id=row['id'], callback=row['components']['UIButton']['callback_name'])
                    for row in state['entities'] if 'UIButton' in row['components']],
        unit_ids={row['components']['Unit']['name']: row['id']
                  for row in state['entities'] if 'Unit' in row['components']})


def sample(renderer, mode):
    with NativeSession(renderer=renderer, display='window' if renderer == 'pygame' else 'none',
            simulation_profile='interactive', mode=mode, scenario='chibi-small', seed=42,
            players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.HUMAN}) as scene:
        states, responses = [], []
        uid = next(row['id'] for row in scene.runtime.export_state()['entities']
                   if row['components'].get('Unit', {}).get('faction') == 'wei')
        def checkpoint():
            scene.refresh()
            state = scene.runtime.export_state()
            scene.update_display(0, inputs=False)
            assert scene.runtime.export_state() == state
            states.append(state)
        def command(kind, faction='wei', **parameters):
            before = scene.runtime.export_state()
            if renderer == 'web':
                result = CommandGateway(scene).dispatch(ViewGrant(faction, True),
                    dict(epoch=str(scene.controls.epoch), command=kind, parameters=parameters))
            elif kind == 'end_turn':
                result = scene.controls.finish_turn()
            else:
                result = scene.controls.execute(kind, **parameters)
            # Historical desktop wait/end-turn calls return None on success;
            # the Web gateway supplies a transport acknowledgement instead.
            assert (result is True or isinstance(result, dict) and result.get('success') is True
                    or renderer != 'web' and kind in ('wait', 'end_turn') and result is None), (renderer, mode, kind, result)
            checkpoint()
            if kind == 'wait':
                ap = lambda state: next(row['components']['ActionPoints']['current_ap']
                    for row in state['entities'] if row['id'] == uid)
                assert ap(before) > 0 and ap(states[-1]) == ap(before) - 1
        checkpoint()
        command('move', unit_id=uid, position=(0, 3))
        scene.step(1, wall_time=1720000001.0)
        checkpoint()
        command('wait', unit_id=uid)
        if mode == 'turn_based':
            command('end_turn')
            command('end_turn', faction='shu')
        for action, parameters in [
            ('register_agent_info', dict(faction='wei', provider='synthetic', model_id='fixture', base_url='https://fixture')),
            ('get_faction_state', {'faction': 'wei'}),
            ('unknown_acceptance_action', {}),
        ]:
            responses.append(scene.runtime.execute_action(action, parameters, agent_id='acceptance-agent'))
            checkpoint()
        return states, responses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    record = dict(passed=True, seed=42, scenario='chibi-small', renderers=['none', 'pygame', 'web'],
                  drawing_preserves_authority=True, modes={})
    engine = GameEngine(width=1200, height=900, title='Renderer rules acceptance')
    sync_game_config_from_display()
    try:
        for mode in ('turn_based', 'real_time'):
            cases = {}
            for renderer in record['renderers']:
                with patch('time.time', lambda: 1720000000.), patch('datetime.datetime', Frozen):
                    cases[renderer] = sample(renderer, mode)
            states, responses = cases['web']
            full_equal = cases['none'][0] == cases['pygame'][0] == states
            response_equal = cases['none'][1] == cases['pygame'][1] == responses
            record['passed'] &= full_equal and response_equal
            record['modes'][mode] = dict(checkpoints=len(states),
                full_authority_state_equal=full_equal, agent_responses_equal=response_equal,
                none_web_complete_equal=cases['none'] == cases['web'],
                tested_unit_components_equal=all(unit_components(a) == unit_components(b) == unit_components(c)
                    for a, b, c in zip(cases['none'][0], cases['pygame'][0], states)),
                initial_identity={name: initial_identity(case[0][0]) for name, case in cases.items()},
                authority_sha256={name: [digest(s) for s in case[0]] for name, case in cases.items()},
                agent_response_equal_to_none={name: [a == b for a, b in zip(cases['none'][1], case[1])]
                                               for name, case in cases.items()},
                agent_responses_sha256={name: digest(case[1]) for name, case in cases.items()})
    finally:
        engine.quit()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(record, indent=2) + '\n')
    print('Three-adapter authority/Agent comparison:', 'PASS' if record['passed'] else 'FAIL; see output evidence')
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
