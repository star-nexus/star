"""Internal attribution preserves cache order, motion and visual phase fences."""
import json

import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import HexPosition, Vision
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_combat import combat_probe
from rotk_env.tests.test_native_movement import probe


def same(plain, measured):
    assert json.loads(plain.export_state_json()) == json.loads(measured.export_state_json())
    assert json.loads(plain.take_presentation_delta_json()) == json.loads(measured.take_presentation_delta_json())


@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('capacity', [1, 4])
def test_vision_repeated_key_lru_order_and_detached_diagnostics(threads, display, capacity):
    world, (a, b, c), _ = make_vision_world(display)
    try:
        for uid, center in [(a, (0, 0)), (b, (1, 0)), (c, (0, 0))]:
            pos = world.get_component(uid, HexPosition)
            pos.col, pos.row = center
            vision = world.get_component(uid, Vision)
            vision.range, vision.dirty = 3, True
        initial = export_initial_state(world, display=display)
        state = initial['systems']['VisionSystem']
        state.update(capacity=capacity, geometry=[], dirty=[a, b, c])
        plain = NativeRuntime(json.dumps(initial), threads)
        measured = NativeRuntime(json.dumps(initial), threads)
        try:
            plain.step(0., 1720000000.)
            timing = json.loads(measured._step_profile_json(0., 1720000000.))
            same(plain, measured)
            vision = timing['candidates']['vision']
            assert vision['recompute_rows'] == 3
            # A,B,A must evict twice at capacity 1; grouping equal keys would alter this.
            assert vision['geometry_misses'] == (3 if capacity == 1 else 2)
            assert vision['geometry_hits'] == (0 if capacity == 1 else 1)
            assert vision['geometry_evictions'] == (2 if capacity == 1 else 0)
            assert vision['geometry_tiles'] > 0
            plain.step(0., 1720000000.)
            following = json.loads(measured._step_profile_json(0., 1720000000.))
            same(plain, measured)
            assert following['candidates']['vision']['recompute_rows'] == 0
            measured.reset(json.dumps(initial))
            measured.close()
            assert timing['candidates']['vision'] == vision
        finally:
            plain.close()
            measured.close()
    finally:
        world.reset()


@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('display', ['dummy', 'window'])
def test_motion_visual_spawn_and_recovery_match_complete_tick(threads, display):
    world, (a, b, c), _ = make(display, GameMode.REAL_TIME, 'ranged')
    initial = export_initial_state(world, display=display)
    plain = NativeRuntime(json.dumps(initial), threads)
    measured = NativeRuntime(json.dumps(initial), threads)
    try:
        for native in (plain, measured):
            assert combat_probe(native, 'attack', a, c)['success']
            assert probe(native, 'move', b, (-1, 1))['success']
        same(plain, measured)
        crossings = spawned = recovery_entries = 0
        for dt in [0.01] * 80 + [5., 60.]:
            plain.step(dt, 1720000000.)
            timing = json.loads(measured._step_profile_json(dt, 1720000000.))
            same(plain, measured)
            candidates = timing['candidates']
            crossings += candidates['movement']['crossings']
            visuals = candidates['visuals']
            spawned += visuals['spawned']
            if visuals['spawned']:
                assert visuals['projectile_rows'] >= visuals['spawned']
            recovery = candidates['recovery']
            recovery_entries += recovery['ap_entries'] + recovery['mp_entries'] + recovery['skill_entries']
        assert crossings > 0 and spawned > 0 and recovery_entries > 0
    finally:
        plain.close()
        measured.close()
        world.reset()
