"""Benchmark GAP G004: Player membership is part of the derived view contract."""
from copy import deepcopy
import pytest
pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.runtime.bootstrap import export_initial_state,encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.world_presentation import WorldPresentation
from rotk_env.tests.test_native_world_presentation import detached_world
from rotk_env.tests.test_native_combat_presentation import make,request
from rotk_env.tests.test_native_unit_actions import register
from rotk_env.tests.test_native_request_batch import frozen


def player_rows(world):
    return {uid:encode(world.get_component(uid,c.Player)) for uid in world.query().with_component(c.Player).ordered_entities()}


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('mode',[GameMode.REAL_TIME,GameMode.TURN_BASED])
@pytest.mark.parametrize('threads',[1,2,4])
@pytest.mark.parametrize('drain_before',[False,True])
def test_player_baseline_and_death_journal_match_python(display,mode,threads,drain_before,frozen):
    world,(a,b,target),llm=make(display,mode,'melee',dead=True)
    # Duplicate faction Players preserve the old first-matching deletion rule.
    duplicate=world.create_entity()
    world.add_component(duplicate,c.Player(Faction.SHU,PlayerType.HUMAN,(1,2,3),units={target},resources=7,score=9,name='duplicate'))
    derived=detached_world(world);projection=WorldPresentation(derived)
    try:
        with RustRuntime(export_initial_state(world,display=display),threads=threads) as runtime:
            if drain_before:projection.apply(runtime.take_presentation_delta())
            register(world,runtime,llm,display)
            request(world,runtime,llm,'attack',dict(unit_id=a,target_id=target),display)
            before=runtime.export_state();delta=runtime.take_presentation_delta();projection.apply(delta)
            assert runtime.export_state()==before
            assert player_rows(derived)==player_rows(world)
            assert derived.get_component(duplicate,c.Player).units=={target}
            if drain_before:
                assert delta['players']['rows']==[]
                assert len(delta['players']['units_removed'])==1
                assert delta['players']['units_removed'][0]['unit_ids']==[target]
            else:
                assert delta['players']['full'] and delta['players']['units_removed']==[]
            held=deepcopy(delta)
            assert runtime.take_presentation_delta()['players']==dict(full=False,rows=[],units_removed=[])
            runtime.reset(before)
            with pytest.raises(ValueError,match='epoch'):projection.apply(runtime.take_presentation_delta())
            assert delta==held
    finally:world.reset();derived.reset()


def test_baseline_replaces_stale_player_data_and_is_detached(frozen):
    world,_,_=make('none',GameMode.REAL_TIME,'melee')
    derived=detached_world(world);projection=WorldPresentation(derived)
    uid=next(iter(player_rows(world)))
    derived.get_component(uid,c.Player).units.clear()
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            delta=runtime.take_presentation_delta()
            missing=deepcopy(delta);missing['players']['full']=False
            with pytest.raises(ValueError,match='Player baseline'):projection.apply(missing)
            assert projection.epoch is None
            projection.apply(delta)
            assert player_rows(derived)==player_rows(world)
            before=runtime.export_state()
            derived.get_component(uid,c.Player).units.add(987654)
            assert runtime.export_state()==before
            assert 987654 not in delta['players']['rows'][0]['player']['units']['$set']
    finally:world.reset();derived.reset()
