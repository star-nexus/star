"""Resource values AND scheduler ledgers must survive native handoff exactly."""
import copy
import json

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import GameTime, ActionPoints, MovementPoints, SkillPoints
from rotk_env.prefabs.config import ActionType, GameMode
from rotk_env.runtime.bootstrap import export_initial_state, export_recovery, encode
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.tests.test_native_movement import make_world, probe
from rotk_env.systems.movement_system import MovementSystem


def compare(world, recovery, native):
    state = json.loads(native.export_state_json())
    assert state['systems']['ResourceRecoverySystem'] == export_recovery(recovery)
    columns = {e['id']: e['components'] for e in state['entities']}
    for uid, components in world.entities.items():
        for cls in (ActionPoints, MovementPoints, SkillPoints):
            if cls in components:
                assert columns[uid][cls.__name__] == encode(components[cls])


@pytest.mark.parametrize('mode', [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize('fps', [24, 30])
@pytest.mark.parametrize('interval', [1., .1])
def test_consumption_cadence_pause_scale_and_checkpoint(mode, fps, interval):
    world, (a, b, _) = make_world('none')
    clock = world.get_singleton_component(GameTime)
    clock.current_mode = mode
    world.add_component(a, SkillPoints(current_sp=20, max_sp=20))
    recovery = ResourceRecoverySystem()
    recovery.ap_recovery_interval = interval
    recovery.skill_cooldown_interval = .3 if interval == .1 else 5.
    world.add_system(recovery)
    n = NativeRuntime(json.dumps(export_initial_state(world)))
    move = next(s for s in world.systems if isinstance(s, MovementSystem))
    def resource(uid, kind, **kwargs):
        if kind == 'ap':
            expected = world.get_component(uid, ActionPoints).consume_ap(ActionType.ATTACK)
            if expected:
                recovery.mark_action_points_spent(uid)
        else:
            expected = world.get_component(uid, SkillPoints).use_skill(kwargs['name'], kwargs['cost'], kwargs['cooldown'])
            if expected:
                recovery.mark_skill_cooldown_started(uid)
        op = dict(unit_id=uid, kind=kind, **kwargs)
        assert json.loads(n._resource_probe_json(json.dumps([op]))) == [expected]
        compare(world, recovery, n)
    try:
        resource(a, 'ap')
        resource(a, 'skill', name='scout', cost=1, cooldown=4)
        assert probe(n, 'move', a, (-2, 0)) == json.loads(json.dumps(move.move_unit(a, (-2, 0))))
        compare(world, recovery, n)  # MP pending, not scheduled until next advancing boundary.
        for index in range(fps * 12):
            if index == 1:
                resource(a, 'ap')  # Does not reset an existing AP cadence.
                resource(a, 'skill', name='defend', cost=1, cooldown=7)
            if index == fps:
                assert probe(n, 'move', a, (-1, 0)) == json.loads(json.dumps(move.move_unit(a, (-1, 0))))
            paused = fps * 2 <= index < fps * 3
            scale = 2. if index > fps * 5 else .5
            clock.paused, clock.time_scale = paused, scale
            n.set_clock(paused, scale)
            dt = 1 / fps
            clock.update(dt)
            recovery.update(dt)
            n.step(dt, clock.last_update_time)
            compare(world, recovery, n)
            if index in (fps // 2, fps * 4):
                # Resume while active tasks and obsolete bucket entries coexist.
                state = json.loads(n.export_state_json())
                old = copy.deepcopy(state)
                n.reset(json.dumps(state))
                assert json.loads(n.export_state_json()) == old
                compare(world, recovery, n)
        clock.paused = False
        n.set_clock(False, clock.time_scale)
        clock.update(83.7)
        recovery.update(83.7)
        n.step(83.7, clock.last_update_time)
        compare(world, recovery, n)
    finally:
        n.close()
        world.reset()


def test_import_depleted_resources_before_first_boundary_and_disabled_scheduler():
    world, (a, *_)=make_world('none')
    clock=world.get_singleton_component(GameTime)
    world.get_component(a, ActionPoints).current_ap=0
    world.get_component(a, MovementPoints).current_mp=0
    world.add_component(a, SkillPoints(skill_cooldowns={'scout':3}))
    recovery=ResourceRecoverySystem()
    world.add_system(recovery)
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        for enabled in (False,True):
            recovery.enabled=enabled
            # New lifecycle imports the Python scheduler's actual enabled state.
            n.reset(json.dumps(export_initial_state(world)))
            for dt in (0.,.1,.9,2.,4.,30.):
                clock.update(dt)
                if enabled:
                    recovery.update(dt)
                n.step(dt,clock.last_update_time)
                compare(world,recovery,n)
    finally:
        n.close(); world.reset()


def test_invalid_deadline_restore_does_not_replace_running_world():
    world,(a,*_)=make_world('none')
    world.get_component(a,ActionPoints).current_ap=0
    recovery=ResourceRecoverySystem()
    world.add_system(recovery)
    scene=export_initial_state(world)
    n=NativeRuntime(json.dumps(scene))
    try:
        bad=copy.deepcopy(scene)
        bad['systems']['ResourceRecoverySystem']['ap']['buckets']=[]
        with pytest.raises(RuntimeError,match='deadline'):
            n.reset(json.dumps(bad))
        assert json.loads(n.export_state_json())==scene
    finally:
        n.close(); world.reset()
