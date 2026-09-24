"""Derived unit membership and exact smaller-set terrain projection."""
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env import components as c
from rotk_env.prefabs.config import Faction
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_observation import setup,observe
from rotk_env.tests.test_native_combat import combat_probe
from rotk_env.tests.test_faction_state_affordances import _disc,_spawn
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.combat_system import CombatSystem


@pytest.mark.parametrize('fog_mode',['disabled','missing','empty','local','large'])
@pytest.mark.parametrize('radius',[3,30])
@pytest.mark.parametrize('threads',[1,2,4])
def test_public_facts_visit_units_and_smaller_terrain_set_only(fog_mode,radius,threads):
    world,(a,b,target),_=setup('none')
    for tid in list(world.get_singleton_component(c.MapData).tiles.values()):world.destroy_entity(tid)
    board=_disc(world,radius)
    # Non-gameplay resident entities must not enter the unit census.
    for _ in range(250):world.create_entity()
    dead=_spawn(world,faction=Faction.WEI,col=0,row=2,count=0)
    no_count=_spawn(world,faction=Faction.WEI,col=0,row=2)
    world.remove_component(no_count,c.UnitCount)
    world.remove_component(b,c.HexPosition)
    fog=world.get_singleton_component(c.FogOfWar);fog.enabled=fog_mode!='disabled';fog.faction_vision.clear()
    local={(0,0),(-1,0),(1,0),(999,999)}
    if fog_mode!='missing':fog.faction_vision[Faction.WEI]=set() if fog_mode=='empty' else (set(board.tiles)|local if fog_mode=='large' else local)
    # A mapped cell without Terrain remains excluded rather than synthesized.
    world.remove_component(board.tiles[(0,0)],c.Terrain)
    params={'faction':'wei','unit_ids':[a]}
    try:
        n=NativeRuntime(json.dumps(export_initial_state(world)),threads)
        try:
            before=n.export_state_json();report=observe(n,[params,params])
            expected=LLMActionHandler(world).handle_faction_state(params)
            assert report['results']==[expected,expected]
            assert n.export_state_json()==before
            assert report['metrics']['census_entities_visited']==5
            assert report['metrics']['enemy_entities_visited']==5
            budget={'disabled':len(board.tiles),'missing':0,'empty':0,'local':4,'large':len(board.tiles)}[fog_mode]
            assert report['metrics']['terrain_cells_visited']==budget
            assert expected['total_units']==4 and expected['alive_units']==2
        finally:n.close()
    finally:world.reset()


def test_catalog_is_rebuilt_on_reset_and_updated_on_death():
    world,(a,b,target),_=setup('none')
    world.get_singleton_component(c.FogOfWar).enabled=False
    world.get_component(a,c.Combat).attack_range=10
    world.get_component(target,c.UnitCount).current_count=1
    params={'faction':'wei','unit_ids':[a]}
    initial=export_initial_state(world)
    combat=next(s for s in world.systems if isinstance(s,CombatSystem))
    try:
        n=NativeRuntime(json.dumps(initial))
        try:
            baseline=observe(n,[params])
            assert baseline['metrics']['census_entities_visited']==3
            assert combat_probe(n,'attack',a,target)==combat.execute_attack(a,target)
            after=observe(n,[params]);assert after['results']==[LLMActionHandler(world).handle_faction_state(params)]
            assert after['metrics']['census_entities_visited']==2
            n.reset(json.dumps(initial));assert observe(n,[params])==baseline
            world2,_,_=setup('none')
            try:
                _spawn(world2,faction=Faction.WU,col=0,row=2)
                n.reset(json.dumps(export_initial_state(world2)))
                assert observe(n,[params])['metrics']['census_entities_visited']==4
            finally:world2.reset()
        finally:n.close()
    finally:world.reset()


def test_expiring_imported_visual_unit_cannot_leave_catalog_tombstone():
    world,(a,b,target),_=setup('dummy')
    world.get_singleton_component(c.FogOfWar).enabled=False
    world.add_component(target,c.DamageNumber())
    initial=export_initial_state(world,display='dummy')
    # This unusual but accepted scene destroys the entire visual entity at
    # expiry, as the existing visual lifecycle already does. The catalog follows.
    params={'faction':'wei','unit_ids':[a]}
    try:
        n=NativeRuntime(json.dumps(initial))
        try:
            assert observe(n,[params])['metrics']['census_entities_visited']==3
            n.step(100.,1720000000.)
            report=observe(n,[params])
            assert report['metrics']['census_entities_visited']==2
            assert not report['results'][0]['visible_enemy_units']
        finally:n.close()
    finally:world.reset()
