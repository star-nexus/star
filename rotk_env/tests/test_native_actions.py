"""Incremental trusted-dispatch contract; complete Agent closure is still pending."""
import datetime
import json
import time
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components.agent_info import AgentInfoRegistry
from rotk_env.components import Combat, UnitCount
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world


def request(native,agent,action,params):
    metadata=dict(agent_id=agent,action=action,parameters=params,wall_time=time.time(),
                  registration_time=datetime.datetime.now().isoformat(),
                  sanitized_base_url=AgentInfoRegistry.sanitize_url(params.get('base_url','')))
    return json.loads(native.execute_action_json(json.dumps(metadata)))


def test_register_identity_reregister_counter_and_query(monkeypatch):
    monkeypatch.setattr(time,'time',lambda:1720000000.)
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,9,12,12,0,0)
    monkeypatch.setattr(datetime,'datetime',Frozen)
    world,(a,b,c),vision=make_vision_world('none')
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    llm=LLMSystem();world.add_system(llm)
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    registration={'faction':'wei','provider':'synthetic','model_id':'fake','base_url':'https://host/v1/?token=removed#fragment'}
    operations=[('missing','get_faction_state',{'faction':'wei'}),
                ('new','get_action_list',{}),
                ('alpha','register_agent_info',{**registration,'agent_id':'spoofed'}),
                ('beta','register_agent_info',registration),
                ('alpha','register_agent_info',{**registration,'model_id':'replaced'}),
                ('alpha','get_faction_state',{'faction':'wei','unit_ids':[a]}),
                ('alpha','get_faction_state',{'faction':'shu'}),
                ('alpha','get_action_list',{}),
                ('alpha','does_not_exist',{}),
                ('alpha','rest',{'unit_id':a}),
                ('enemy','register_agent_info',{**registration,'faction':'shu'}),
                ('alpha','list_team',{}),
                ('alpha','broadcast_to_team',{'text':'hold position','metadata':{'order':[a,b]}}),
                ('beta','read_team_messages',{'agent_id':'alpha'}),
                ('enemy','read_team_messages',{}),
                ('alpha','claim_units',{'unit_ids':[a]}),
                ('beta','move',{'unit_id':a,'target_position':{'col':-2,'row':0},'agent_id':'alpha'}),
                ('enemy','move',{'unit_id':a,'target_position':{'col':-2,'row':0}}),
                ('beta','claim_units',{'unit_ids':[b,a]}),
                ('beta','claim_units',{'unit_ids':[b,a],'exclusive':False}),
                ('alpha','release_units',{}),
                ('beta','get_faction_state',{'faction':'wei','unit_ids':[a,b,a]}),
                ('beta','move',{'unit_id':a,'target_position':{'col':-2,'row':0}}),
                ('alpha','get_faction_state',{'faction':'wei'}),
                ('beta','attack',{'unit_id':a,'target_id':c}),
                ('beta','get_faction_state',{'faction':'wei'}),
                ('beta','release_units',{}),
                ('alpha','register_agent_info',{**registration,'faction':'shu'}),
                ('alpha','get_faction_state',{'faction':'shu','unit_ids':[c]})]
    try:
        for index,(agent,action,params) in enumerate(operations):
            expected=llm._process_action_request(agent_id=agent,action_id=index,action=action,params=dict(params),send_response=False)
            actual=request(native,agent,action,params)
            assert actual==json.loads(json.dumps(expected)),(index,action)
            assert json.loads(native.export_state_json())==export_initial_state(world),(index,action)
    finally:
        native.close();world.reset()


@pytest.mark.parametrize('action,params',[
    ('move',{}),('move',{'unit_id':None}),('move',{'unit_id':'a'}),
    ('move',{'unit_id':True,'target_position':{'col':-2,'row':0}}),
    ('move',{'unit_id':'a','target_position':[]}),('move',{'unit_id':'a','target_position':{}}),
    ('move',{'unit_id':'a','target_position':{'col':1.5,'row':0}}),
    ('move',{'unit_id':'a','target_position':{'col':99999,'row':0}}),
    ('move',{'unit_id':-1,'target_position':{'col':-2,'row':0}}),
    ('move',{'unit_id':'a','target_position':{'col':0,'row':0}}),
    ('move',{'unit_id':'a','target_position':{'col':-2,'row':0}}),
    ('attack',{}),('attack',{'unit_id':'a','target_id':None}),
    ('attack',{'unit_id':-1,'target_id':'c'}),('attack',{'unit_id':'a','target_id':99999}),
    ('attack',{'unit_id':'a','target_id':'b'}),('attack',{'unit_id':'a','target_id':'c'}),
    ('claim_units',{'unit_ids':[99999]}),('claim_units',{'unit_ids':['not int']}),
    ('claim_units',{'unit_ids':0}),('claim_units',{'unit_ids':['c']}),
    ('broadcast_to_team',{'text':''}),('broadcast_to_team',{'text':5}),
    ('broadcast_to_team',{'text':'alone','metadata':None}),
    ('release_units',{'unit_ids':[]}),('release_units',{'unit_ids':3}),
    ('release_units',{'unit_ids':[{}]}),('release_units',{'unit_ids':'abc'}),('read_team_messages',{}),
])
def test_request_validation_precedence_and_complete_state(action,params,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:1720000000.)
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,9,12,12,0,0)
    monkeypatch.setattr(datetime,'datetime',Frozen)
    world,(a,b,c),vision=make_vision_world('none')
    llm=LLMSystem();world.add_system(llm)
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    params=dict(params)
    for key in ('unit_id','target_id'):
        if isinstance(params.get(key),str) and params[key] in ('a','b','c'):
            params[key]={'a':a,'b':b,'c':c}[params[key]]
    if params.get('unit_ids')==['c']:params['unit_ids']=[c]
    registration={'faction':'wei','provider':'synthetic','model_id':'fake','base_url':'https://host/v1'}
    try:
        for index,(verb,payload) in enumerate([('register_agent_info',registration),(action,params)]):
            expected=llm._process_action_request(agent_id='alpha',action_id=index,action=verb,params=dict(payload),send_response=False)
            assert request(native,'alpha',verb,payload)==json.loads(json.dumps(expected)),(verb,payload)
            assert json.loads(native.export_state_json())==export_initial_state(world),(verb,payload)
    finally:
        native.close();world.reset()
