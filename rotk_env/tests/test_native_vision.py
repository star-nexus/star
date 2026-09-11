"""Native Fog maintains exact unit geometry, faction unions and exploration."""
import json

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import Combat, FogOfWar, GameTime, Vision, UnitCount
from rotk_env.prefabs.config import TerrainType
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.systems.vision_system import VisionSystem, mark_vision_dirty
from rotk_env.systems.window_vision_system import VisionSystem as WindowVision
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.tests.test_native_movement import make_world, probe
from rotk_env.tests.test_native_combat import combat_probe


def make_vision_world(display):
    world,ids=make_world(display,{(0,1):TerrainType.FOREST,(1,0):TerrainType.HILL})
    for uid in ids:
        world.add_component(uid,Vision(range=2))
    v=WindowVision() if display=='window' else VisionSystem()
    v._geometry_cache_max_entries=4  # exercise LRU eviction without changing geometry
    world.add_system(v)
    v.update(0.)
    return world,ids,v


def vprobe(n,kind,**kwargs):
    return json.loads(n._vision_probe_json(json.dumps([dict(kind=kind,**kwargs)])))[0]


def compare(world,n,display):
    expected=export_initial_state(world,display=display)
    actual=json.loads(n.export_state_json())
    for key in ('entities','singletons','systems','rng'):
        if actual[key]!=expected[key]:
            assert actual[key]==expected[key],key


@pytest.mark.parametrize('display',['none','dummy','window'])
def test_geometry_line_of_sight_id_zero_and_lru_across_map_edges(display):
    world,ids,v=make_vision_world(display)
    n=NativeRuntime(json.dumps(export_initial_state(world,display=display)))
    try:
        compare(world,n,display)
        for col in range(-4,5):
            for row in range(-4,5):
                for radius in (0,1,3,6):
                    expected=v._calculate_vision((col,row),radius,ids[0])
                    assert vprobe(n,'geometry',center=(col,row),range=radius)==encode(expected)
        compare(world,n,display)
        state=json.loads(n.export_state_json());n.reset(json.dumps(state))
        assert json.loads(n.export_state_json())==state
    finally:
        n.close();world.reset()


@pytest.mark.parametrize('display',['none','dummy','window'])
def test_movement_overlap_fog_toggle_exploration_and_range_changes(display):
    world,(a,b,c),v=make_vision_world(display)
    n=NativeRuntime(json.dumps(export_initial_state(world,display=display)))
    clock=world.get_singleton_component(GameTime)
    move=next(s for s in world.systems if isinstance(s,MovementSystem))
    animation=next((s for s in world.systems if isinstance(s,AnimationSystem)),None)
    try:
        for uid,goal in ((a,(-2,0)),(b,(-1,1))):
            assert probe(n,'move',uid,goal)==json.loads(json.dumps(move.move_unit(uid,goal)))
            compare(world,n,display)
        old_explored=encode(world.get_singleton_component(FogOfWar).explored_tiles)
        for index in range(20):
            if index in (1,12):
                enabled=index==12
                world.get_singleton_component(FogOfWar).enabled=enabled
                vprobe(n,'toggle',enabled=enabled)
            if index==8:
                world.get_component(c,Vision).range=4
                world.get_component(c,Vision).dirty=True
                mark_vision_dirty(world,c)
                vprobe(n,'range',unit_id=c,range=4)
            clock.update(.25)
            if animation is not None:animation._update_movement_animations(.25)
            v.update(.25);n.step(.25,clock.last_update_time)
            compare(world,n,display)
        assert encode(world.get_singleton_component(FogOfWar).explored_tiles)!=old_explored
    finally:
        n.close();world.reset()


def test_death_removes_only_dead_observer_contribution_on_next_vision_tick():
    world,(a,b,c),v=make_vision_world('none')
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    combat=next(s for s in world.systems if isinstance(s,CombatSystem))
    clock=world.get_singleton_component(GameTime)
    try:
        assert combat_probe(n,'attack',a,c)==combat.execute_attack(a,c)
        compare(world,n,'none')  # death queues invalidation; pre-tick union is retained
        clock.update(1/30);v.update(1/30);n.step(1/30,clock.last_update_time)
        compare(world,n,'none')
        assert not world.has_entity(c)
    finally:
        n.close();world.reset()
