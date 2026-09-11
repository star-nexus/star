"""Native team state preserves ownership and bounded FIFO semantics across restore."""
from collections import deque
import json
import time

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import TeamCoordination
from rotk_env.runtime.bootstrap import encode, export_initial_state
from rotk_env.tests.test_native_movement import make_world


def team_probe(native, kind, **params):
    return json.loads(native._team_probe_json(json.dumps([dict(kind=kind, **params)])))[0]


def check_team(coord, native):
    assert json.loads(native.export_state_json())['singletons']['TeamCoordination'] == encode(coord)


def test_claim_conflicts_atomic_transfer_duplicates_and_release_order():
    world, ids = make_world('none')
    coord = TeamCoordination(); world.add_singleton_component(coord)
    native = NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        for agent, selected, exclusive in [('alpha',[ids[2],ids[0],ids[2]],True),
                                            ('beta',[ids[1],ids[0]],True),
                                            ('beta',[ids[1],ids[0]],False)]:
            result = coord.claim_units(agent, selected, exclusive)
            assert team_probe(native,'claim',agent_id=agent,unit_ids=selected,exclusive=exclusive) == json.loads(json.dumps(result))
            check_team(coord,native)
        saved=native.export_state_json();native.reset(saved)
        for agent, selected in [('alpha',None),('beta',[ids[1],ids[1]]),('beta',None),('nobody',None)]:
            assert team_probe(native,'release',agent_id=agent,unit_ids=selected) == coord.release_units(agent,selected)
            check_team(coord,native)
    finally:
        native.close();world.reset()


@pytest.mark.parametrize('cap',[0,1,3,64])
def test_members_message_fifo_caps_and_reset(cap,monkeypatch):
    now=1720000000.
    monkeypatch.setattr(time,'time',lambda:now)
    world,ids=make_world('none')
    coord=TeamCoordination(history_cap=cap,inbox_cap=cap)
    world.add_singleton_component(coord)
    # Existing deque limits can differ from new-queue defaults, including unbounded.
    coord.team_inboxes['uncapped']=deque([{'old':True}])
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    native._set_wall_metadata(now)
    try:
        for faction,agent in [('wei','alpha'),('shu','enemy'),('wei','beta'),('wei','uncapped'),('wei','alpha'),('shu','alpha')]:
            assert team_probe(native,'member',faction=faction,agent_id=agent)==coord.register_member(faction,agent)
            check_team(coord,native)
        for faction in ('wei','shu','wu'):
            for agent in ('alpha',None):
                assert team_probe(native,'teammates',faction=faction,agent_id=agent)==coord.teammates_of(faction,agent)
        for i in range(10):
            native._set_wall_metadata(now)  # each request supplies fresh external metadata
            metadata={'nested':[i,{'label':'协作'}]}
            assert team_probe(native,'broadcast',agent_id='alpha',faction='wei',text=f'order{i}',metadata=metadata)==coord.broadcast('alpha','wei',f'order{i}',metadata)
            check_team(coord,native)
            if i==4:
                native.reset(native.export_state_json())
        for agent in ('beta','uncapped','alpha','enemy','missing'):
            assert team_probe(native,'drain',agent_id=agent)==coord.drain_inbox(agent)
            check_team(coord,native)
        assert team_probe(native,'snapshot')==json.loads(json.dumps(coord.snapshot()))
    finally:
        native.close();world.reset()


def test_existing_queue_limits_survive_new_default_caps():
    world,ids=make_world('none');coord=TeamCoordination(history_cap=3,inbox_cap=3)
    world.add_singleton_component(coord)
    coord.register_member('wei','alpha');coord.register_member('wei','beta')
    coord.broadcast('alpha','wei','old')
    coord.history_cap=0;coord.inbox_cap=1
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        for agent in ('new','newer'):
            assert team_probe(native,'member',faction='wei',agent_id=agent)==coord.register_member('wei',agent)
        for i in range(7):
            wall=100.+i
            native._set_wall_metadata(wall)
            # Compare a deterministic component timestamp without changing simulation dt.
            from unittest.mock import patch
            with patch('time.time',return_value=wall):
                expected=coord.broadcast('alpha','wei',str(i))
            assert team_probe(native,'broadcast',agent_id='alpha',faction='wei',text=str(i))==expected
            check_team(coord,native)
        assert len(coord.team_inboxes['beta'])==3
        assert len(coord.team_inboxes['new'])==1
        assert len(coord.team_history['wei'])==3
    finally:
        native.close();world.reset()


def test_authorization_is_per_unit_with_unclaimed_default():
    world,ids=make_world('none');coord=TeamCoordination()
    world.add_singleton_component(coord);coord.claim_units('alpha',[ids[0]])
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        for uid in ids:
            assert team_probe(native,'owner',unit_id=uid)==coord.owner_of(uid)
            for agent in (None,'alpha','beta'):
                assert team_probe(native,'authorized',unit_id=uid,agent_id=agent)==coord.is_authorized(agent,uid)
        check_team(coord,native)
    finally:
        native.close();world.reset()


def test_invalid_team_restore_preserves_live_world():
    world,ids=make_world('none');coord=TeamCoordination()
    world.add_singleton_component(coord);coord.register_member('wei','alpha')
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        state=json.loads(native.export_state_json())
        state['singletons']['TeamCoordination']['inbox_maxlen']={}
        with pytest.raises(RuntimeError,match='inconsistent team queue limits'):
            native.reset(json.dumps(state))
        check_team(coord,native)
    finally:
        native.close();world.reset()
