"""E4 negative control preserves whole-step semantics and per-call policy."""
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_combat import combat_probe
from rotk_env.tests.test_native_movement import probe
from rotk_env.tests.test_native_system_candidates import same
from rotk_env.prefabs.config import GameMode

@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
def test_empty_fork_motion_visual_recovery_reset_close(threads, display):
    world, (a, b, c), _ = make(display, GameMode.REAL_TIME, 'ranged')
    from rotk_env.components import Vision
    from rotk_env.systems.vision_system import VisionSystem
    from rotk_env.systems.window_vision_system import VisionSystem as WindowVision
    for uid in (a, b, c):
        world.add_component(uid, Vision(range=2))
    vision = WindowVision() if display == 'window' else VisionSystem()
    world.add_system(vision)
    vision.update(0.)
    initial = export_initial_state(world, display=display)
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    forked = 0
    try:
        for native in (plain, measured):
            assert combat_probe(native, 'attack', a, c)['success']
            assert probe(native, 'move', b, (-1, 1))['success']
        for dt in [.01]*80 + [5., 60.]:
            plain.step(dt, 1720000000.)
            timing = json.loads(measured._between_systems_step_json(dt, 1720000000., 'empty_fork', True))
            forked += timing['phases_ns'].get('forked', 0)
            same(plain, measured)
        if display == 'window' and threads != 1:
            assert forked > 0
        else:
            assert forked == 0
        before = measured.export_state_json()
        for mode in ['parallel', 'split_serial', 'unknown']:
            with pytest.raises(RuntimeError, match='stage one'):
                measured._between_systems_step_json(.1, 1720000000., mode)
            assert measured.export_state_json() == before
        for dt, wall in [(-1., 1720000000.), (.1, float('nan'))]:
            with pytest.raises(RuntimeError):
                measured._between_systems_step_json(dt, wall, 'empty_fork')
            assert measured.export_state_json() == before
        for native in (plain, measured):
            native.reset(json.dumps(initial))
            native.step(.1, 1720000000.)
        same(plain, measured)
        measured.close()
        with pytest.raises(RuntimeError, match='closed'):
            measured._between_systems_step_json(.1, 1720000000., 'baseline')
    finally:
        plain.close()
        measured.close()
        world.reset()

@pytest.mark.parametrize('threads', [1, 2, 4])
def test_statistics_error_prevents_fork_and_keeps_same_partial_state(threads):
    from rotk_env.tests.test_native_statistics_compute import initial_statistics
    initial, ids = initial_statistics('window')
    next(e for e in initial['entities'] if e['id'] == ids[1])['components']['UnitCount']['max_count'] = 0
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    try:
        with pytest.raises(RuntimeError, match='statistics health division by zero'):
            plain.step(.25, 1720000000.)
        with pytest.raises(RuntimeError, match='statistics health division by zero'):
            measured._between_systems_step_json(.25, 1720000000., 'empty_fork', True)
        same(plain, measured)
    finally:
        plain.close()
        measured.close()

@pytest.mark.parametrize('threads', [1, 2, 4])
def test_game_over_does_not_skip_dirty_vision_after_fork(threads):
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
    initial['systems']['ResourceRecoverySystem']['known'] = 0
    unit = next(e for e in initial['entities'] if e['id'] == ids[0])
    unit['components']['Vision']['range'] = 4
    unit['components']['Vision']['dirty'] = True
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    try:
        plain.step(.1, 1720000000.)
        timing = json.loads(measured._between_systems_step_json(.1, 1720000000., 'empty_fork', True))
        state = json.loads(measured.export_state_json())
        assert state['singletons']['GameState']['game_over'] is True
        result = next(e for e in state['entities'] if e['id'] == ids[0])
        assert result['components']['Vision']['_last_range'] == 4
        assert timing['phases_ns'].get('forked', 0) == int(threads != 1)
        same(plain, measured)
    finally:
        plain.close()
        measured.close()
