"""Exact native spatial broad phase: no changes to masks, Fog or ID ordering."""
import json
import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env import components as c
from rotk_env.prefabs.config import Faction
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.tests.test_native_observation import setup, observe
from rotk_env.tests.test_faction_state_affordances import _spawn
from rotk_env.tests.test_native_movement import probe
from rotk_env.tests.test_native_combat import combat_probe
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index


@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('origin', [(-2,-1), (-1,1), (0,0), (1,-2)])
@pytest.mark.parametrize('radius', [-1, 0, 1, 3, 50])
@pytest.mark.parametrize('fog', [False, True])
def test_index_matches_full_python_masks_for_hex_parity_fog_and_ranges(display, origin, radius, fog):
    world, (a,b,target), _ = setup(display)
    world.get_component(a,c.HexPosition).col, world.get_component(a,c.HexPosition).row = origin
    world.get_component(a,c.Combat).attack_range = radius
    # Reverse creation order defeats accidental cell-order equivalence. Include
    # stacked targets, three factions, dead and positionless entries.
    for i,(col,row) in enumerate(reversed([(x,y) for x in range(-4,5) for y in range(-4,5)])):
        uid = _spawn(world,faction=Faction.WU if i%3==0 else Faction.SHU,col=col,row=row,mp=0)
        if i%11==0: world.get_component(uid,c.UnitCount).current_count=0
        if i%13==0: world.remove_component(uid,c.HexPosition)
    for _ in range(3): _spawn(world,faction=Faction.SHU,col=origin[0],row=origin[1],mp=0)
    view=world.get_singleton_component(c.FogOfWar);view.enabled=fog
    view.faction_vision[Faction.WEI]={(col,row) for col in range(-4,5) for row in range(-4,5) if (col+row)%2==0}
    if display=='window':rebuild_unit_spatial_index(world)
    params={'faction':'wei','agent_id':'alpha','unit_ids':[a,a]}
    try:
        with_native = NativeRuntime(json.dumps(export_initial_state(world,display=display)))
        try:
            before=with_native.export_state_json()
            result=observe(with_native,[params,params])
            expected=LLMActionHandler(world).handle_faction_state(params)
            assert result['results']==[expected,expected]
            ids=result['results'][0]['units'][0]['attackable']
            assert ids==sorted(ids) and len(ids)==len(set(ids))
            assert with_native.export_state_json()==before
            assert result['metrics']['panel_builds']==1
            if radius<0:assert result['metrics']['attack_rule_checks']==0
            if radius==50:assert result['metrics']['attack_cell_lookups']==0
        finally: with_native.close()
    finally:world.reset()


@pytest.mark.parametrize('missing', [None,c.Combat,c.HexPosition,c.ActionPoints])
@pytest.mark.parametrize('ap', [0,1])
def test_ineligible_attackers_and_missing_components_match_python(missing,ap):
    world,(a,_,_),_=setup()
    world.get_singleton_component(c.FogOfWar).enabled=False
    world.get_component(a,c.ActionPoints).current_ap=ap
    if missing:world.remove_component(a,missing)
    params={'faction':'wei','unit_ids':[a]}
    try:
        n=NativeRuntime(json.dumps(export_initial_state(world)))
        try:
            actual=observe(n,[params])
            assert actual['results']==[LLMActionHandler(world).handle_faction_state(params)]
            if missing or not ap:
                assert actual['metrics']['attack_cell_lookups']==actual['metrics']['attack_distance_checks']==actual['metrics']['attack_rule_checks']==0
        finally:n.close()
    finally:world.reset()


@pytest.mark.parametrize('display',['none','dummy','window'])
def test_index_tracks_movement_commit_death_and_reset(display):
    world,(a,b,target),_=setup(display)
    world.get_singleton_component(c.FogOfWar).enabled=False
    for i in range(80):_spawn(world,faction=Faction.SHU,col=50+i,row=0,mp=0)
    world.get_component(target,c.UnitCount).current_count=1
    if display=='window':rebuild_unit_spatial_index(world)
    params={'faction':'wei','unit_ids':[a]}
    n=NativeRuntime(json.dumps(export_initial_state(world,display=display)))
    handler=LLMActionHandler(world)
    movement=next(s for s in world.systems if isinstance(s,MovementSystem))
    from rotk_env.systems.combat_system import CombatSystem
    combat=next(s for s in world.systems if isinstance(s,CombatSystem))
    def check():
        report=observe(n,[params]);assert report['results']==[handler.handle_faction_state(params)]
        assert report['metrics']['attack_cell_lookups']==7
        return report['results'][0]['units'][0]['attackable']
    try:
        assert target not in check()
        assert probe(n,'move',target,(0,1))==json.loads(json.dumps(movement.move_unit(target,(0,1))))
        check()  # Animated modes still use the old committed cell.
        if display!='none':
            animation=next(s for s in world.systems if isinstance(s,AnimationSystem))
            for dt in [.01, .1, 1.]:
                animation._update_movement_animations(dt);n.step(dt,1720000000.)
                check()
        assert target in check()
        assert combat_probe(n,'attack',a,target)==combat.execute_attack(a,target)
        assert target not in check()
        state=n.export_state_json();n.reset(state);check()
    finally:n.close();world.reset()


@pytest.mark.parametrize('radius',[10**9,2**63-1])
def test_huge_range_falls_back_without_enumerating_disc(radius):
    world,(a,_,_),_=setup('none')
    world.get_component(a,c.Combat).attack_range=radius
    world.get_singleton_component(c.FogOfWar).enabled=False
    params={'faction':'wei','unit_ids':[a]}
    try:
        n=NativeRuntime(json.dumps(export_initial_state(world)))
        try:
            report=observe(n,[params])
            assert report['results']==[LLMActionHandler(world).handle_faction_state(params)]
            assert report['metrics']['attack_cell_lookups']==0
        finally:n.close()
    finally:world.reset()
