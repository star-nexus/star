"""Combat kernel differential tests; public permissions/window gates are separate."""
import json

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from framework.engine.events import EBS
from rotk_env.components import Combat, Unit, UnitCount, UnitStatus, HexPosition, GameTime, ActionPoints, RngService
from rotk_env.prefabs.config import UnitType, UnitState, TerrainType
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.tests.test_native_movement import make_world


def combat_probe(n, kind, uid, target=None):
    return json.loads(n._combat_probe_json(json.dumps([dict(kind=kind,unit_id=uid,target_id=target)])))[0]


def compare(world,n):
    expected=export_initial_state(world)
    actual=json.loads(n.export_state_json())
    for key in ('entities','singletons','rng','systems','entity_counter'):
        assert actual[key]==expected[key],key


@pytest.mark.parametrize('unit_type',list(UnitType))
@pytest.mark.parametrize('terrain',list(TerrainType))
def test_effective_stats_preserve_enum_string_terrain_and_headcount(unit_type,terrain):
    world,(a,*_)=make_world('none',{(-1,0):terrain})
    system=next(s for s in world.systems if isinstance(s,CombatSystem))
    world.get_component(a,Unit).unit_type=unit_type
    combat=world.get_component(a,Combat)
    combat.base_attack,combat.base_defense=47,23
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        for status in list(UnitState)+[s.value for s in UnitState]:
            world.get_component(a,UnitStatus).current_status=status
            for count in (1,10,20,29,30,31,99,100):
                world.get_component(a,UnitCount).current_count=count
                n.reset(json.dumps(export_initial_state(world)))
                coeff=system._get_terrain_coefficient((-1,0),unit_type)
                expected=combat.get_effective_stats(world.get_component(a,UnitCount),world.get_component(a,UnitStatus),coeff)
                assert combat_probe(n,'effective',a)==list(expected)
                compare(world,n)
    finally:
        n.close();world.reset()


@pytest.mark.parametrize('seed',range(12))
def test_attacks_death_rng_recovery_state_and_event_order(seed,monkeypatch):
    world,(a,b,c)=make_world('none',{(1,1):TerrainType.FOREST,(-1,0):TerrainType.HILL})
    world.add_singleton_component(RngService(seed=seed))
    world.get_component(a,Unit).unit_type=UnitType.CAVALRY
    world.get_component(a,UnitStatus).charge_stacks=2
    for uid in (a,b,c):
        world.get_component(uid,Combat).attack_range=4
    recovery=ResourceRecoverySystem();world.add_system(recovery)
    system=next(s for s in world.systems if isinstance(s,CombatSystem))
    events=[]
    monkeypatch.setattr(EBS,'publish',lambda e:events.append({'type':type(e).__name__,'fields':encode(e)}))
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    clock=world.get_singleton_component(GameTime)
    try:
        # Rejected attacks consume no random numbers and preserve error precedence.
        for attacker,target in [(a,b),(a,999999),(999999,c)]:
            assert combat_probe(n,'attack',attacker,target)==system.execute_attack(attacker,target)
            compare(world,n)
        for i in range(60):
            attacker,target=(a,c) if i%2==0 else (c,a)
            if not world.has_entity(attacker) or not world.has_entity(target):
                break
            assert combat_probe(n,'ready',attacker,target)==system.can_attack(attacker,target)
            expected=system.execute_attack(attacker,target)
            assert combat_probe(n,'attack',attacker,target)==expected
            compare(world,n)
            assert json.loads(n.take_presentation_delta_json())['events']==events
            events.clear()
            clock.update(.7);recovery.update(.7);n.step(.7,clock.last_update_time)
            compare(world,n)
        assert not world.has_entity(a) or not world.has_entity(c)
    finally:
        n.close();world.reset()


@pytest.mark.parametrize('component',[Combat,UnitCount,ActionPoints,HexPosition,Unit])
def test_missing_attacker_components_preserve_rejections(component):
    world,(a,_,c)=make_world('none')
    world.remove_component(a,component)
    n=NativeRuntime(json.dumps(export_initial_state(world)))
    system=next(s for s in world.systems if isinstance(s,CombatSystem))
    try:
        assert combat_probe(n,'attack',a,c)==system.execute_attack(a,c)
        compare(world,n)
    finally:
        n.close();world.reset()
