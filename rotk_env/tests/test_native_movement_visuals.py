"""E5 whole-state, ordered visual prefix and per-call scheduling controls."""
import copy
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_combat import combat_probe
from rotk_env.tests.test_native_movement import probe
from rotk_env.tests.test_native_system_candidates import same


def cases():
    world, (a, b, c), _ = make('window', GameMode.REAL_TIME, 'ranged')
    try:
        initial = export_initial_state(world, display='window')
    finally:
        world.reset()
    native = NativeRuntime(json.dumps(initial))
    try:
        assert combat_probe(native, 'attack', a, c)['success']
        assert probe(native, 'move', b, (-1, 1))['success']
        base = json.loads(native.export_state_json())
    finally:
        native.close()
    output = []
    steps = [.01]*25 + [.5, 1., 2., 60.]
    for display in ['none', 'dummy', 'window']:
        state = copy.deepcopy(base)
        state['display'] = display
        output.append(dict(name=display, initial=state, steps=steps))
    for name in ['hybrid', 'effect-error', 'id-exhausted', 'disabled', 'absent', 'paused', 'scaled', 'game-over', 'statistics-error', 'capture-error']:
        state = copy.deepcopy(base)
        visual = state['systems']['VisualLifecycle']
        if name in ['hybrid', 'effect-error']:
            visual['damage'][str(b)] = copy.deepcopy(next(iter(visual['damage'].values())))
            visual['projectile'][str(b)] = dict(start_pos=[0., 0.], target_pos=[0.,0.], flight_progress=0.,flight_speed=600.,is_flying=True)
        if name == 'effect-error':
            next(iter(visual['effect'].values()))['duration'] = 0.
        elif name == 'id-exhausted':
            state['entity_counter'] = 2**64-2
            state['systems']['ResourceRecoverySystem']['known'] = 2**64-2
            visual['attack'][str(c)] = copy.deepcopy(visual['attack'][str(a)])
            for attack in visual['attack'].values():
                attack['progress'] = .4
        elif name == 'disabled':
            state['systems']['AnimationSystem']['enabled'] = False
        elif name == 'absent':
            del state['systems']['AnimationSystem']
        elif name == 'paused':
            state['clock']['paused'] = True
            state['singletons']['GameTime']['paused'] = True
        elif name == 'scaled':
            state['clock']['time_scale'] = 3.
            state['singletons']['GameTime']['time_scale'] = 3.
        elif name == 'game-over':
            state['rules']['max_realtime_seconds'] = 0.
            state['systems']['RealtimeSystem'] = {'enabled': True, 'indexed': True}
        elif name == 'statistics-error':
            from rotk_env.tests.test_native_statistics_compute import initial_statistics
            state, ids = initial_statistics('window')
            next(e for e in state['entities'] if e['id'] == ids[1])['components']['UnitCount']['max_count'] = 0
        if name == 'capture-error':
            pos = next(e for e in state['entities'] if e['id'] == a)['components']['HexPosition']
            tile = next(e for e in state['entities'] if e['components'].get('HexPosition') == pos and 'TerritoryControl' in e['components'])
            tile['components']['TerritoryControl']['capture_time_required'] = 0.
            native = NativeRuntime(json.dumps(state))
            try:
                assert native.start_capture(a, (pos['col'], pos['row']), 1720000000., None)
                state = json.loads(native.export_state_json())
            finally:
                native.close()
        output.append(dict(name=name, initial=state, steps=steps))
    return output

@pytest.mark.parametrize('threads', [1,2,4])
@pytest.mark.parametrize('mode', ['baseline','empty_fork','split_serial','parallel'])
def test_complete_visual_prefix_and_lifecycle(threads, mode):
    selected = 0
    for case in cases():
        plain = NativeRuntime(json.dumps(case['initial']), threads)
        measured = NativeRuntime(json.dumps(case['initial']), threads)
        try:
            same(plain, measured)
            for index, dt in enumerate(case['steps']):
                errors = []
                try:
                    plain.step(dt, 1720000000.+index)
                    errors.append(None)
                except RuntimeError as e:
                    errors.append(str(e))
                try:
                    timing = json.loads(measured._movement_visuals_step_json(dt, 1720000000.+index, mode, 0, True))
                    selected += timing['phases_ns'].get('e5_eligible', 0)
                    errors.append(None)
                except RuntimeError as e:
                    errors.append(str(e))
                assert errors[0] == errors[1], case['name']
                same(plain, measured)
                if index == 10:
                    for native in (plain, measured):
                        native.reset(native.export_state_json())
                    same(plain, measured)
            before = measured.export_state_json()
            with pytest.raises(RuntimeError, match='invalid E5'):
                measured._movement_visuals_step_json(.1, 0., 'bad')
            assert before == measured.export_state_json()
            measured.close()
            with pytest.raises(RuntimeError, match='closed'):
                measured._movement_visuals_step_json(.1, 0., mode)
        finally:
            plain.close()
            measured.close()
    if mode == 'split_serial' or (mode != 'baseline' and threads > 1):
        assert selected > 0
    else:
        assert selected == 0

@pytest.mark.parametrize('threads', [1,2,4])
def test_game_over_keeps_vision_after_visual_join(threads):
    from rotk_env.components import Vision
    from rotk_env.systems.window_vision_system import VisionSystem
    world, ids, _ = make('window', GameMode.REAL_TIME, 'ranged')
    try:
        for uid in ids:
            world.add_component(uid, Vision(range=2))
        vision = VisionSystem()
        world.add_system(vision)
        vision.update(0.)
        initial = export_initial_state(world, display='window')
    finally:
        world.reset()
    initial['rules']['max_realtime_seconds'] = 0.
    initial['systems']['RealtimeSystem'] = {'enabled': True, 'indexed': True}
    initial['systems']['VisionSystem']['dirty'] = list(ids)
    unit = next(e for e in initial['entities'] if e['id'] == ids[0])
    unit['components']['Vision'].update(range=4, dirty=True)
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    try:
        for native in (plain, measured):
            assert combat_probe(native, 'attack', ids[0], ids[2])['success']
            assert probe(native, 'move', ids[1], (-2,1))['success']
        plain.step(.1, 1720000000.)
        report = json.loads(measured._movement_visuals_step_json(.1, 1720000000., 'parallel', 0, True))
        state = json.loads(measured.export_state_json())
        assert state['singletons']['GameState']['game_over'] is True
        unit = next(e for e in state['entities'] if e['id'] == ids[0])
        assert unit['components']['Vision']['_last_range'] == 4
        assert report['phases_ns'].get('e5_eligible',0) == int(threads>1)
        same(plain, measured)
        crossings = 0
        for index in range(5):
            plain.step(5., 1720000001.+index)
            report = json.loads(measured._movement_visuals_step_json(5., 1720000001.+index, 'parallel', 0, True))
            crossings += report['candidates']['movement']['crossings']
            same(plain, measured)
        assert crossings >= 2
    finally:
        plain.close()
        measured.close()
