"""E9 ordered Fog transitions, owned state, and per-call controls."""
import copy,json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import HexPosition,Vision
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_vision import make_vision_world,vprobe
from rotk_env.tests.test_native_system_candidates import same
from rotk_env.tests.test_native_movement import probe


def initial(display):
    world,ids,_=make_vision_world(display)
    try:
        for uid,center in zip(ids,[(0,0),(1,0),(0,0)]):
            p=world.get_component(uid,HexPosition);p.col,p.row=center
            v=world.get_component(uid,Vision);v.range=3;v.dirty=True
        state=export_initial_state(world,display=display)
        state['systems']['VisionSystem'].update(dirty=list(ids),capacity=1,geometry=[])
        return state,ids
    finally:world.reset()


@pytest.mark.parametrize('threads',[1,4])
@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('profile',[False,True])
def test_ordered_cache_motion_fog_and_lifecycle(threads,display,profile):
    state,(a,b,c)=initial(display)
    plain=NativeRuntime(json.dumps(state),threads);other=NativeRuntime(json.dumps(state),threads)
    try:
        same(plain,other);before_input=copy.deepcopy(state)
        for index in range(15):
            for n in (plain,other):
                if index in (2,8):vprobe(n,'toggle',enabled=index==8)
                if index==3:vprobe(n,'range',unit_id=c,range=6)
                if index==4:probe(n,'move',a,(-2,0))
            plain.step(.25,1720000000.+index)
            value=json.loads(other._vision_commit_step_json(.25,1720000000.+index,'stream_commit',profile))
            same(plain,other)
            if profile and index==0:
                assert value['vision']['geometry_misses']==3
                assert value['vision']['geometry_evictions']==2
                assert value['vision']['component_set_copies']==0
                assert value['vision']['old_set_copies']==0
                assert value['vision']['temporary_difference_sets']==0
                assert value['vision']['published_set_copies']==6
            if not profile:assert value is None
            if index==9:
                for n in (plain,other):n.reset(n.export_state_json())
                same(plain,other)
        assert state==before_input
        snap=other.export_state_json()
        with pytest.raises(RuntimeError,match='invalid E9'):other._vision_commit_step_json(1.,1720000001.,'bad')
        assert other.export_state_json()==snap
        other.close()
        with pytest.raises(RuntimeError,match='closed'):other._vision_commit_step_json(0.,0.)
    finally:plain.close();other.close()


@pytest.mark.parametrize('threads',[1,4])
@pytest.mark.parametrize('case',['empty-faction','missing-position','missing-vision','missing-info','no-fog','bootstrap','nonindexed','disabled','gameover','paused','scaled','terrain','owned-output'])
def test_boundaries_and_lazy_empty_maps(threads,case):
    state,ids=initial('window');a=ids[0];system=state['systems']['VisionSystem']
    unit=next(e for e in state['entities'] if e['id']==a)
    if case=='empty-faction':
        unit['components']['HexPosition'].update(col=-50,row=-50)
        unit['components']['Vision'].update(range=-2,dirty=True)
        unit['components']['Unit']['faction']='empty-new'
        system['unit_visibility'][str(a)]={'$set':[]}
        old_faction=system['unit_faction'][str(a)]
        system['counts'].pop(old_faction,None)
        state['singletons']['FogOfWar']['faction_vision'].pop(old_faction,None)
    elif case.startswith('missing-'):
        unit['components'].pop({'missing-position':'HexPosition','missing-vision':'Vision','missing-info':'Unit'}[case])
    elif case=='no-fog':state['singletons'].pop('FogOfWar')
    elif case=='bootstrap':system['bootstrapped']=False
    elif case=='nonindexed':system['indexed']=False
    elif case=='disabled':system['enabled']=False
    elif case=='gameover':
        state['rules']['max_realtime_seconds']=0.;state['systems']['RealtimeSystem']={'enabled':True,'indexed':True}
    elif case=='paused':state['clock']['paused']=True;state['singletons']['GameTime']['paused']=True
    elif case=='scaled':state['clock']['time_scale']=3.;state['singletons']['GameTime']['time_scale']=3.
    elif case=='terrain':system['terrain_revision']+=1;system['geometry']=[];system['dirty']=list(ids)
    plain=NativeRuntime(json.dumps(state),threads);other=NativeRuntime(json.dumps(state),threads)
    try:
        plain.step(.25,1720000000.)
        result=json.loads(other._vision_commit_step_json(.25,1720000000.,'stream_commit',True))
        same(plain,other)
        if case=='empty-faction':
            value=json.loads(other.export_state_json())
            assert old_faction in value['singletons']['FogOfWar']['faction_vision']
            assert 'empty-new' not in value['singletons']['FogOfWar']['faction_vision']
        if case=='gameover':assert json.loads(other.export_state_json())['singletons']['GameState']['game_over']
        if case=='owned-output':
            state['systems']['VisionSystem']['unit_visibility'].clear();result['vision']['geometry_hits']=999
            exported=json.loads(other.export_state_json());exported['systems']['VisionSystem']['unit_visibility'].clear()
            same(plain,other)
        for _ in range(3):
            plain.step(.1,1720000001.);other._vision_commit_step_json(.1,1720000001.,'baseline');same(plain,other)
    finally:plain.close();other.close()


@pytest.mark.parametrize('threads',[1,4])
def test_stage_errors_keep_the_same_successful_prefix(threads):
    from rotk_env.tests.test_native_movement_visuals import cases
    for case in cases():
        if case['name'] not in ['effect-error','id-exhausted','statistics-error','capture-error','hybrid']:continue
        plain=NativeRuntime(json.dumps(case['initial']),threads);other=NativeRuntime(json.dumps(case['initial']),threads)
        try:
            for index,dt in enumerate(case['steps'][:3]):
                errors=[]
                for n,mode in [(plain,'baseline'),(other,'stream_commit')]:
                    try:n._vision_commit_step_json(dt,1720000000.+index,mode);errors.append(None)
                    except RuntimeError as e:errors.append(str(e))
                assert errors[0]==errors[1],case['name'];same(plain,other)
        finally:plain.close();other.close()
