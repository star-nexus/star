"""Advancing diagnostics must preserve ordinary step, including partial errors."""
import json

import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import prepare_scene


@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('mode', ['real_time', 'turn_based'])
def test_profile_matches_complete_state_and_delta(mode, display, threads):
    initial = prepare_scene(mode=mode, scenario='chibi-small', seed=42, display=display)
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    try:
        for paused, scale in [(False, 1.), (True, 1.), (False, .5), (False, 2.)]:
            plain.set_clock(paused, scale)
            measured.set_clock(paused, scale)
            for dt in [0., 1/30, .1, 2.3]:
                plain.step(dt, 1720000000.)
                timing = json.loads(measured._step_profile_json(dt, 1720000000.))
                assert {'clock', 'statistics', 'recovery', 'lifecycle', 'vision', 'captures'} <= timing['phases_ns'].keys()
                assert all(type(value) is int and value >= 0 for value in timing['phases_ns'].values())
                assert timing['native_ns'] >= sum(timing['phases_ns'].values())
                assert json.loads(plain.export_state_json()) == json.loads(measured.export_state_json())
                assert json.loads(plain.take_presentation_delta_json()) == json.loads(measured.take_presentation_delta_json())
        # Reset does not retain profiling data; an earlier timing owns its values.
        plain.reset(json.dumps(initial))
        measured.reset(json.dumps(initial))
        assert json.loads(plain.export_state_json()) == json.loads(measured.export_state_json())
    finally:
        plain.close()
        measured.close()


@pytest.mark.parametrize('dt,wall', [(-1., 0.), (float('nan'), 0.), (0., float('inf'))])
def test_profile_invalid_input_matches_step_without_mutation(dt, wall):
    initial = prepare_scene(mode='real_time', scenario='chibi-small', seed=42)
    plain = NativeRuntime(json.dumps(initial))
    measured = NativeRuntime(json.dumps(initial))
    try:
        with pytest.raises(RuntimeError) as expected:
            plain.step(dt, wall)
        with pytest.raises(RuntimeError) as actual:
            measured._step_profile_json(dt, wall)
        assert str(actual.value) == str(expected.value)
        assert json.loads(plain.export_state_json()) == initial
        assert json.loads(measured.export_state_json()) == initial
    finally:
        plain.close()
        measured.close()


def test_partial_capture_error_and_disabled_phase_match():
    from rotk_env.tests.test_native_unit_actions import setup
    from rotk_env.components import MapData, TerritoryControl
    from rotk_env.runtime.bootstrap import export_initial_state
    world, (unit, *_), _, _ = setup()
    tile = world.get_singleton_component(MapData).tiles[(-1, 0)]
    world.get_component(tile, TerritoryControl).capture_time_required = 0.
    initial = export_initial_state(world)
    initial['systems']['AnimationSystem'] = {'enabled': False}
    plain = NativeRuntime(json.dumps(initial))
    measured = NativeRuntime(json.dumps(initial))
    try:
        assert plain.start_capture(unit, (-1, 0), 1720000000., None)
        assert measured.start_capture(unit, (-1, 0), 1720000000., None)
        before = json.loads(plain.export_state_json())
        with pytest.raises(RuntimeError, match='float division by zero'):
            plain.step(.5, 1720000001.)
        with pytest.raises(RuntimeError, match='float division by zero'):
            measured._step_profile_json(.5, 1720000001.)
        after = json.loads(plain.export_state_json())
        assert after != before  # Preserve actual partial execution, not rollback.
        assert after == json.loads(measured.export_state_json())
        assert json.loads(plain.take_presentation_delta_json()) == json.loads(measured.take_presentation_delta_json())
        plain.reset(json.dumps(initial))
        measured.reset(json.dumps(initial))
        plain.step(.5, 1720000001.)
        timing = json.loads(measured._step_profile_json(.5, 1720000001.))
        assert 'movement' not in timing['phases_ns'] and 'visuals' not in timing['phases_ns']
        assert json.loads(plain.export_state_json()) == json.loads(measured.export_state_json())
    finally:
        plain.close()
        measured.close()
        world.reset()
    with pytest.raises(RuntimeError, match='closed'):
        measured._step_profile_json(0., 0.)
