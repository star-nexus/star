"""R3 rest/territory/skill contracts compare the actual Python oracle, including quirks."""
import json

import pytest
pytest.importorskip('star_native')
from rotk_env.components import (ActionPoints, ConstructionPoints, SkillPoints, UnitSkills,
    UnitStatus, MatchRules, GameModeComponent, GameState, GameTime, HexPosition, Player, MapData, TerritoryControl)
from rotk_env.prefabs.config import Faction, GameMode, PlayerType, UnitState, TerrainType
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.systems.game_time_system import GameTimeSystem
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.systems.territory_system import TerritorySystem
from rotk_env.systems.turn_system import TurnSystem
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_movement import make_world
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_lifecycle import snapshot


def setup(display='none', mode=GameMode.REAL_TIME, territory=True, terrain=TerrainType.MOUNTAIN):
    world, ids = make_world(display, {(-1,0):terrain, (0,0):TerrainType.FOREST, (0,1):TerrainType.WATER, (1,0):TerrainType.CITY})
    world.add_singleton_component(MatchRules(game_actions=('move','attack','get_faction_state','end_turn','rest','occupy','fortify','skill')))
    world.get_singleton_component(GameModeComponent).mode=mode
    world.get_singleton_component(GameState).game_mode=mode
    world.add_system(GameTimeSystem())
    world.add_system(ResourceRecoverySystem())
    for uid in ids:
        world.add_component(uid,ConstructionPoints())
        world.add_component(uid,SkillPoints())
        world.add_component(uid,UnitSkills(available_skills={'hide','rockslide','arrow_evasion','unknown'}))
        world.get_component(uid,ActionPoints).current_ap=6
        world.get_component(uid,ActionPoints).max_ap=6
    for faction, units in [(Faction.WEI,set(ids[:2])),(Faction.SHU,{ids[2]})]:
        pid=world.create_entity();world.add_component(pid,Player(faction=faction,player_type=PlayerType.HUMAN,color=(255,255,255),units=units))
    if mode==GameMode.TURN_BASED:
        world.add_system(TurnSystem())
        world.get_singleton_component(GameState).current_player=Faction.WEI
    system=TerritorySystem() if territory else None
    if system:world.add_system(system)
    llm=LLMSystem();world.add_system(llm)
    return world,ids,system,llm


def command(world,native,llm,action,params,agent='alpha',display='none'):
    expected=llm._process_action_request(agent_id=agent,action_id=0,action=action,params=dict(params),send_response=False)
    result=native.execute_action(action,params,agent_id=agent)
    assert result==json.loads(json.dumps(expected)), (action,params,result,expected)
    snapshot(world,native,display)
    return result


def register(world,native,llm,display='none'):
    for agent,faction in [('alpha','wei'),('beta','wei'),('enemy','shu')]:
        command(world,native,llm,'register_agent_info',dict(faction=faction,provider='synthetic',model_id='fake',base_url='https://host'),agent,display)


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('mode',[GameMode.REAL_TIME,GameMode.TURN_BASED])
@pytest.mark.parametrize('territory',[False,True])
def test_rest_occupy_fortify_and_write_read_order(display,mode,territory,frozen):
    world,(a,b,c),system,llm=setup(display,mode,territory)
    status=world.get_component(a,UnitStatus);status.current_status=UnitState.CONFUSION;status.status_duration=5
    raw_status=world.get_component(b,UnitStatus);raw_status.current_status='confusion';raw_status.status_duration=5
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            register(world,native,llm,display)
            def call(action,params,agent='alpha'):return command(world,native,llm,action,params,agent,display)
            call('claim_units',{'unit_ids':[a,b]})
            for uid in (a,b,a,b):assert call('rest',{'unit_id':uid})['success']
            assert status.current_status==UnitState.NORMAL and raw_status.current_status=='confusion'
            call('rest',{'unit_id':a},'beta');call('rest',{'unit_id':c})
            for p in [(-1,0),(-1,0),(0,0),(0,1),(3,3)]:
                call('occupy',{'unit_id':a,'position':dict(col=p[0],row=p[1])})
                call('get_faction_state',{'faction':'wei'})
                call('fortify',{'unit_id':a,'position':dict(col=p[0],row=p[1])})
            # This valid boundary accepts bool coordinates exactly like Python's int.
            call('occupy',{'unit_id':b,'position':{'col':False,'row':False}})
            for dt in (1.,29.,.25):
                frozen[0]+=dt;world.update(dt);native.step(dt,wall_time=frozen[0]);snapshot(world,native,display)
            native.reset(native.export_state());snapshot(world,native,display)
            call('get_faction_state',{'faction':'wei','unit_ids':[b,a]})
    finally:world.reset()


@pytest.mark.parametrize('action',['rest','occupy','fortify','skill'])
@pytest.mark.parametrize('case',['bad_id','missing_id','bad_position','bad_coordinate','empty_ap','no_status','no_cp','no_sp','no_skills','no_position','other_turn'])
def test_action_validation_order(action,case,frozen):
    world,(a,b,c),system,llm=setup(mode=GameMode.TURN_BASED)
    params={'unit_id':a,'position':{'col':-1,'row':0},'skill_name':'hide'}
    if case=='bad_id':params['unit_id']='17'
    elif case=='missing_id':params['unit_id']=-10
    elif case=='bad_position':params['position']=[]
    elif case=='bad_coordinate':params['position']['col']=1.5
    elif case=='empty_ap':world.get_component(a,ActionPoints).current_ap=0
    elif case=='no_status':world.remove_component(a,UnitStatus)
    elif case=='no_cp':world.remove_component(a,ConstructionPoints)
    elif case=='no_sp':world.remove_component(a,SkillPoints)
    elif case=='no_skills':world.remove_component(a,UnitSkills)
    elif case=='no_position':world.remove_component(a,HexPosition)
    elif case=='other_turn':world.get_singleton_component(GameState).current_player=Faction.SHU
    try:
        with RustRuntime(export_initial_state(world)) as native:
            register(world,native,llm)
            command(world,native,llm,action,params)
    finally:world.reset()


@pytest.mark.parametrize('terrain',[TerrainType.PLAIN,TerrainType.FOREST,TerrainType.HILL,TerrainType.MOUNTAIN])
@pytest.mark.parametrize('name',['hide','rockslide','arrow_evasion','unknown','unavailable'])
def test_terrain_skill_preserves_result_key_failure_without_resource_writes(terrain,name,frozen):
    world,(a,b,c),system,llm=setup(terrain=terrain)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            register(world,native,llm)
            before=(world.get_component(a,ActionPoints).current_ap,world.get_component(a,SkillPoints).current_sp)
            result=command(world,native,llm,'skill',{'unit_id':a,'skill_name':name,'target':{'unit_id':c}})
            assert not result['success']
            assert before==(world.get_component(a,ActionPoints).current_ap,world.get_component(a,SkillPoints).current_sp)
            assert not world.get_component(a,UnitSkills).skill_cooldowns
    finally:world.reset()


@pytest.mark.parametrize('kind',['unit_cooldown','resource_cooldown','empty_sp','no_ap','invalid_name'])
def test_separate_skill_gates(kind,frozen):
    world,(a,b,c),system,llm=setup()
    params={'unit_id':a,'skill_name':'rockslide'}
    if kind=='unit_cooldown':world.get_component(a,UnitSkills).skill_cooldowns['rockslide']=3
    elif kind=='resource_cooldown':world.get_component(a,SkillPoints).skill_cooldowns['rockslide']=3
    elif kind=='empty_sp':world.get_component(a,SkillPoints).current_sp=0
    elif kind=='no_ap':world.remove_component(a,ActionPoints)
    else:params['skill_name']=False
    try:
        with RustRuntime(export_initial_state(world)) as native:
            register(world,native,llm)
            command(world,native,llm,'skill',params)
    finally:world.reset()


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('mode',[GameMode.REAL_TIME,GameMode.TURN_BASED])
@pytest.mark.parametrize('case',['complete','move_away','disabled','already_own','no_ap','double_start','city'])
def test_timed_capture_lifecycle_and_stable_entity_ids(display,mode,case,frozen):
    world,(a,b,c),system,llm=setup(display,mode)
    pos=(-1,0)
    if case=='city':
        # Construct on a city from the initial snapshot; AP cost field is 2,
        # while the actual legacy consume operation still subtracts only 1.
        pos=(1,0);p=world.get_component(a,HexPosition);p.col,p.row=pos
    if case=='already_own':system.occupy_territory(a,pos)
    if case=='no_ap':world.get_component(a,ActionPoints).current_ap=0
    if case=='disabled':system.enabled=False
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            assert native.start_capture(a,pos,wall_time=frozen[0])==system.start_capture(a,pos)
            snapshot(world,native,display)
            if case=='double_start':
                assert native.start_capture(a,pos,wall_time=frozen[0])==system.start_capture(a,pos)==False
            if case=='move_away':
                register(world,native,llm,display)
                command(world,native,llm,'move',{'unit_id':a,'target_position':{'col':-2,'row':0}},display=display)
            for index in range(25):
                frozen[0]+=1000  # World capture timers still advance by 0.5 simulation seconds.
                world.update(.5);native.step(.5,wall_time=frozen[0]);snapshot(world,native,display)
                if index==3:native.reset(native.export_state())
            tile=world.get_singleton_component(MapData).tiles[pos]
            control=world.get_component(tile,TerritoryControl)
            if case in ('complete','city','double_start'):assert control.controlling_faction==Faction.WEI
            if case=='move_away':assert not control.being_captured and control.controlling_faction is None
    finally:world.reset()


@pytest.mark.parametrize('mounted',[False,True])
@pytest.mark.parametrize('friendly',[False,True])
@pytest.mark.parametrize('fortified',[False,True])
def test_territory_changes_attack_damage_and_report_only_when_system_mounted(mounted,friendly,fortified,frozen):
    from rotk_env.components import Combat, UnitCount
    world,(a,b,c),system,llm=setup(territory=True)
    world.get_component(a,Combat).attack_range=5
    world.get_component(a,Combat).base_attack=100
    world.get_component(c,UnitCount).current_count=1000
    world.get_component(c,UnitCount).max_count=1000
    tiles=world.get_singleton_component(MapData).tiles
    for uid,faction in [(a,Faction.WEI),(c,Faction.SHU)]:
        p=world.get_component(uid,HexPosition)
        control=world.get_component(tiles[p.col,p.row],TerritoryControl)
        control.controlling_faction=faction if friendly else Faction.WU
        control.fortified=fortified;control.fortification_level=3;control.is_city=True
    if not mounted:world.systems.remove(system)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            register(world,native,llm)
            assert command(world,native,llm,'attack',{'unit_id':a,'target_id':c})['success']
    finally:world.reset()


def test_capturing_unit_death_removes_task_but_preserves_legacy_tile_marker(frozen):
    from rotk_env.components import Combat, UnitCount, CaptureAction
    world,(a,b,c),system,llm=setup()
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    position=world.get_component(c,HexPosition);cell=(position.col,position.row)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            register(world,native,llm)
            assert system.start_capture(c,cell)==native.start_capture(c,cell)==True
            command(world,native,llm,'attack',{'unit_id':a,'target_id':c})
            world.update(.5);native.step(.5,wall_time=frozen[0]);snapshot(world,native,'none')
            assert not world.query().with_all(CaptureAction).entities()
            tile=world.get_singleton_component(MapData).tiles[cell]
            # Python removes the task without cancel_capture if the unit vanished.
            assert world.get_component(tile,TerritoryControl).being_captured
    finally:world.reset()
