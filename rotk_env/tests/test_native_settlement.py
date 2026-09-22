"""Complete report projection, offline waiting policy and native-only authority."""
from copy import deepcopy
import pytest

pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.components.settlement_report import SettlementReport
from rotk_env.prefabs.config import Faction
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.settlement import report_world, NativeSettlementFormatter, OfflineSettlementHost
from rotk_env.runtime import session as module
from rotk_env.systems.settlement_report_system import SettlementReportSystem
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_input import fonts


@pytest.mark.parametrize('mode',['real_time','turn_based'])
@pytest.mark.parametrize('display',['none','dummy'])
def test_full_report_data_matches_python_and_does_not_alias_authority(mode,display,frozen,fonts):
    source=build_skirmish_world(mode=mode,scenario='chibi-small',seed=42,display=display)
    try:
        llm=next(s for s in source.systems if type(s).__name__=='LLMSystem')
        for agent,faction in [('a','wei'),('b','wei'),('c','shu')]:
            for action,params in [('register_agent_info',dict(faction=faction,provider='synthetic',model_id=agent,base_url='https://host/v1')),
                                  ('report_llm_stats',dict(faction=faction,api_stats=dict(total_calls=7,prompt_tokens=100,completion_tokens=30))),
                                  ('strategy_ping',dict(faction=faction,score=.5,evidence='cooperate'))]:
                llm._process_action_request(agent_id=agent,action_id=0,action=action,params=params,send_response=False)
        stats=source.get_singleton_component(c.GameStats)
        stats.battle_history=[{'attacker':1,'defender':2,'damage':3,'faction':'wei'}]
        state=source.get_singleton_component(c.GameState);state.game_over=True;state.winner=Faction.WEI
        original=export_initial_state(source,display=display)
        with RustRuntime(original) as runtime:
            snapshot=runtime.export_state(expected_epoch=1)
            view=report_world(snapshot)
            try:
                old=SettlementReportSystem();old.initialize(source)
                new=NativeSettlementFormatter(snapshot['interface']['report_context']);new.initialize(view)
                expected=old._collect_comprehensive_statistics()
                actual=new._collect_comprehensive_statistics()
                assert encode(actual)==encode(expected)
                SettlementReport(**actual)  # Validate the actual downstream constructor.
                view.get_singleton_component(c.GameStats).battle_history.clear()
                assert runtime.export_state()==original
                assert snapshot==original
                assert not view.systems
            finally:view.reset()
    finally:source.reset()


@pytest.mark.parametrize('failure',[False,True])
def test_offline_host_exports_full_data_once_at_legacy_deadline(failure,monkeypatch,frozen):
    prepare=module.prepare_display_world
    def ended(**kwargs):
        world,initial=prepare(**kwargs)
        initial['singletons']['GameState'].update(game_over=True,winner='wei')
        return world,initial
    monkeypatch.setattr(module,'prepare_display_world',ended)
    saved=[]
    monkeypatch.setattr(NativeSettlementFormatter,'_save_report_to_files',lambda self,data:saved.append(deepcopy(data)))
    monkeypatch.setattr(NativeSettlementFormatter,'_print_report_summary',lambda self,data:None)
    if failure:
        monkeypatch.setattr(NativeSettlementFormatter,'_collect_comprehensive_statistics',lambda self:(_ for _ in ()).throw(ValueError('injected report error')))
    with module.NativeSession(display='none',mode='real_time',scenario='chibi-small',seed=42) as session:
        host=OfflineSettlementHost(session)
        exports=[];export=session.runtime.export_state
        def record(**kwargs):
            snapshot=export(**kwargs);exports.append(snapshot);return snapshot
        monkeypatch.setattr(session.runtime,'export_state',record)
        start=frozen[0]
        for offset in (0,1,30,59.99):
            host.update(start+offset)
        assert not exports and not saved
        assert export()['singletons']['GameStats']['can_generate_settlement_report']
        # Deliberately poison the HUD copy: it must not feed the final report.
        session.world.get_singleton_component(c.GameStats).initial_unit_counts.clear()
        before=export()
        host.update(start+60)
        assert len(exports)==1 and export()==before
        report=session.world.get_singleton_component(SettlementReport)
        if failure:
            assert report is None and not saved
        else:
            assert len(saved)==1 and report is not None
            assert saved[0]['units_info']['wei']['total_units']==5
        host.update(start+120)
        assert len(exports)==1 and host.report_generated
