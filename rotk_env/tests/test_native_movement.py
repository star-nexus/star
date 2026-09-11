"""R2 movement differential gate; does not claim complete Agent/ENV parity."""
import json

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import GameTime, RngService, Unit, HexPosition, UnitCount, MovementAnimation, MovementPoints, UnitStatus, MapData, Terrain
from rotk_env.prefabs.config import Faction, GameMode, TerrainType, UnitState
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.tests.test_faction_state_affordances import _world, _spawn
from rotk_env.utils.map_query import plan_hex_path
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index


def make_world(display, extras=None):
    world = _world(extras=extras)
    clock = GameTime(current_mode=GameMode.REAL_TIME)
    world.add_singleton_component(clock)
    world.add_singleton_component(RngService(seed=42))
    if display != 'none':
        # Test authoritative movement without fonts or rendering side effects.
        animation = AnimationSystem()
        animation.world = world
        world.systems.append(animation)
    a = _spawn(world,faction=Faction.WEI,col=-1,row=0,mp=4)
    b = _spawn(world,faction=Faction.WEI,col=0,row=0,mp=4)
    c = _spawn(world,faction=Faction.SHU,col=1,row=1,mp=4)
    if display=='window':
        from rotk_env.systems.window_movement_system import MovementSystem as WindowMovement
        world.systems=[s for s in world.systems if not isinstance(s,MovementSystem)]
        world.add_system(WindowMovement())
        rebuild_unit_spatial_index(world)
    return world, (a,b,c)


def probe(native, kind, uid, goal=None):
    op = {'kind':kind,'unit_id':uid}
    if goal is not None:
        op['goal']=goal
    return json.loads(native._movement_probe_json(json.dumps([op])))[0]


def assert_columns(world, native):
    imported = {e['id']:e['components'] for e in json.loads(native.export_state_json())['entities']}
    for uid,components in world.entities.items():
        for t in (HexPosition, Unit, UnitCount, MovementPoints, UnitStatus, MovementAnimation):
            if t in components:
                assert imported[uid][t.__name__] == encode(components[t]), (uid,t.__name__)


@pytest.mark.parametrize('display',['none','dummy','window'])
def test_path_masks_and_low_level_results_match_on_every_destination(display):
    world, (a,b,c) = make_world(display, {(0,1):TerrainType.FOREST, (1,0):TerrainType.WATER})
    initial=export_initial_state(world,display=display)
    native=NativeRuntime(json.dumps(initial))
    h=LLMActionHandler(world)
    try:
        for uid in (a,b,c):
            expected=h._unit_reachable(uid)
            assert probe(native,'reachable',uid)==[[c['col'],c['row']] for c in expected]
            for col in range(-4,5):
                for row in range(-4,5):
                    pos=world.get_component(uid,HexPosition)
                    path=plan_hex_path(world,(pos.col,pos.row),(col,row),mover=uid)
                    assert probe(native,'path',uid,(col,row))==[list(c) for c in path]
        # Independent acceptance/rejection comparisons, with a fresh native state.
        for goal in [(0,0),(-1,0),(1,0),(0,1),(3,-1),(3,3),(-2,0)]:
            w,ids=make_world(display,{(0,1):TerrainType.FOREST,(1,0):TerrainType.WATER})
            n=NativeRuntime(json.dumps(export_initial_state(w,display=display)))
            try:
                expected=next(s for s in w.systems if isinstance(s,MovementSystem)).move_unit(ids[0],goal)
                actual=probe(n,'move',ids[0],goal)
                assert actual==json.loads(json.dumps(expected))
                assert_columns(w,n)
            finally:
                n.close(); w.reset()
    finally:
        native.close(); world.reset()


@pytest.mark.parametrize('fps',[24,30,60])
def test_segments_overshoot_colocation_and_no_midroute_revalidation(fps):
    world,(a,b,c)=make_world('dummy')
    # Two accepted routes share a currently free destination; neither reserves it.
    native=NativeRuntime(json.dumps(export_initial_state(world,display='dummy')))
    move=next(s for s in world.systems if isinstance(s,MovementSystem))
    animation=next(s for s in world.systems if isinstance(s,AnimationSystem))
    try:
        for uid,goal in [(a,(-1,1)),(b,(-1,1))]:
            assert probe(native,'move',uid,goal)==json.loads(json.dumps(move.move_unit(uid,goal)))
        assert not probe(native,'move',a,(0,1))['success']
        for dt in [1/fps]*(fps//2)+[2.3,1/fps]:
            animation._update_movement_animations(dt)
            native.step(dt,1720000000.)
            assert_columns(world,native)
        assert world.get_component(a,HexPosition)==world.get_component(b,HexPosition)
        assert probe(native,'reachable',a)==[[t['col'],t['row']] for t in LLMActionHandler(world)._unit_reachable(a)]
    finally:
        native.close(); world.reset()


@pytest.mark.parametrize('status,count,mp', [('confusion',100,4),('normal',20,4),('normal',21,4),('normal',100,0)])
def test_existing_status_and_troop_loss_rules_are_preserved(status,count,mp):
    world,(a,*_)=make_world('none')
    world.get_component(a,UnitStatus).current_status=status
    world.get_component(a,UnitCount).current_count=count
    world.get_component(a,MovementPoints).current_mp=mp
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        expected=LLMActionHandler(world)._unit_reachable(a)
        assert probe(n,'reachable',a)==[[t['col'],t['row']] for t in expected]
        mover=next(s for s in world.systems if isinstance(s,MovementSystem))
        assert probe(n,'move',a,(2,-2))==json.loads(json.dumps(mover.move_unit(a,(2,-2))))
        assert_columns(world,n)
    finally:
        n.close();world.reset()


def test_tile_without_terrain_is_impassable():
    world,(a,*_)=make_world('none')
    tile=world.get_singleton_component(MapData).tiles[(-2,0)]
    world.remove_component(tile,Terrain)
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        assert probe(n,'path',a,(-2,0))==[]
        expected=LLMActionHandler(world)._unit_reachable(a)
        assert probe(n,'reachable',a)==[[t['col'],t['row']] for t in expected]
        mover=next(s for s in world.systems if isinstance(s,MovementSystem))
        assert probe(n,'move',a,(-2,0))==json.loads(json.dumps(mover.move_unit(a,(-2,0))))
    finally:
        n.close();world.reset()
