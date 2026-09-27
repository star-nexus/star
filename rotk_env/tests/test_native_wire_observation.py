"""The transport form must preserve the authenticated, current observation."""
import json

import pytest

from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.tests.test_native_observation import setup


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('case', ['all', 'selected', 'empty', 'duplicates', 'foreign',
                                  'unknown', 'invalid', 'other_owner', 'denied', 'unregistered'])
def test_wire_matches_dictionary_response_and_authoritative_state(case, threads):
    world, (a, b, enemy), _ = setup('window')
    try:
        initial = export_initial_state(world, display='window')
        kwargs = dict(agent_id='alpha', wall_time=1720000000.)
        faction = 'wei'
        subsets = dict(selected=[a], empty=[], duplicates=[b, a, b], foreign=[enemy],
                       unknown=[999999999], invalid='invalid')
        if case in subsets:
            kwargs['unit_ids'] = subsets[case]
        if case == 'other_owner':
            kwargs.update(agent_id='beta', unit_ids=[a])
        if case == 'denied':
            faction = 'shu'
        if case == 'unregistered':
            kwargs['agent_id'] = 'unknown-agent'
        with RustRuntime(initial, threads=threads) as wire, RustRuntime(initial, threads=threads) as obj:
            payload = wire.get_faction_state_json(faction, **kwargs)
            assert isinstance(payload, str)
            assert json.loads(payload) == obj.get_faction_state(faction, **kwargs)
            assert wire.export_state() == obj.export_state()
    finally:
        world.reset()


def test_wire_snapshot_survives_later_writes_reset_and_close():
    world, (a, _, _), _ = setup('window')
    try:
        initial = export_initial_state(world, display='window')
        kwargs = dict(agent_id='alpha', unit_ids=[a], wall_time=1720000000.)
        with RustRuntime(initial) as wire, RustRuntime(initial) as obj:
            for n in (wire, obj):
                n.execute_action('move', dict(unit_id=a, target_position=dict(col=-2, row=0)),
                                 agent_id='alpha', wall_time=1720000000.)
                n.step(1/30, wall_time=1720000000.)
            payload = wire.get_faction_state_json('wei', **kwargs)
            expected = obj.get_faction_state('wei', **kwargs)
            assert json.loads(payload) == expected
            wire.step(1, wall_time=1720000001.)
            wire.reset(initial)
            assert json.loads(wire.get_faction_state_json('wei', **kwargs)) != expected
        assert json.loads(payload) == expected
        with pytest.raises(RuntimeError, match='closed'):
            wire.get_faction_state_json('wei', **kwargs)
    finally:
        world.reset()


def test_forwarding_does_not_decode_the_response_on_the_server(monkeypatch):
    world, _, _ = setup()
    try:
        with RustRuntime(export_initial_state(world)) as n:
            def forbidden(*args, **kwargs):
                raise AssertionError('server decoded an already encoded response')
            with monkeypatch.context() as patch:
                patch.setattr(json, 'loads', forbidden)
                payload = n.get_faction_state_json('wei', agent_id='alpha', wall_time=1720000000.)
            assert json.loads(payload)['success']
    finally:
        world.reset()
