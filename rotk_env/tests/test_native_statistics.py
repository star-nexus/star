"""Statistics action records and periodic profiles retain their historical timing."""
import json
import time

import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import BattleLog, Combat, FogOfWar, GameTime, UnitCount, UnitStatistics, UnitObservation
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.statistics_system import StatisticsSystem
from rotk_env.systems.window_statistics_system import StatisticsSystem as WindowStatistics
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.tests.test_native_vision import make_vision_world, compare, vprobe
from rotk_env.tests.test_native_movement import probe
from rotk_env.tests.test_native_combat import combat_probe


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('mode',[GameMode.REAL_TIME,GameMode.TURN_BASED])
def test_stats_sampling_actions_fog_and_midcycle_restore(display,mode,monkeypatch):
    now=[1720000000.]
    monkeypatch.setattr(time,'time',lambda:now[0])
    # Freeze default-factory metadata too (the factories were captured at import).
    for cls,field in ((UnitStatistics,'creation_time'),(UnitObservation,'last_seen_time')):
        original=cls.__init__
        def initialize(self,*args,_init=original,_field=field,**kwargs):
            _init(self,*args,**kwargs);setattr(self,_field,now[0])
        monkeypatch.setattr(cls,'__init__',initialize)
    world,(a,b,c),vision=make_vision_world(display)
    clock=world.get_singleton_component(GameTime);clock.current_mode=mode
    world.add_singleton_component(BattleLog())
    statistics=WindowStatistics(batch_size=1) if display=='window' else StatisticsSystem()
    world.add_system(statistics)
    recovery=ResourceRecoverySystem();world.add_system(recovery)
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    n=NativeRuntime(json.dumps(export_initial_state(world,display=display)))
    movement=next(s for s in world.systems if isinstance(s,MovementSystem))
    animation=next((s for s in world.systems if isinstance(s,AnimationSystem)),None)
    combat=next(s for s in world.systems if isinstance(s,CombatSystem))
    try:
        for index in range(40):
            now[0]+= .25
            n._set_wall_metadata(now[0])
            if index==0:
                expected=movement.move_unit(a,(-2,0))
                assert probe(n,'move',a,(-2,0))==json.loads(json.dumps(expected))
                compare(world,n,display)
            if index==4 and display=='none':
                expected=combat.execute_attack(a,c)
                assert combat_probe(n,'attack',a,c)==expected
                compare(world,n,display)
            if index in (6,16):
                enabled=index==16
                world.get_singleton_component(FogOfWar).enabled=enabled
                vprobe(n,'toggle',enabled=enabled)
            clock.paused=20<=index<24
            n.set_clock(clock.paused,clock.time_scale)
            clock.update(.25)
            # Canonical builder order: time, statistics, animation, recovery, vision.
            statistics.update(.25)
            if animation is not None:animation._update_movement_animations(.25)
            recovery.update(.25);vision.update(.25)
            n.step(.25,clock.last_update_time)
            compare(world,n,display)
            if index in (2,8,27):
                state=json.loads(n.export_state_json());n.reset(json.dumps(state))
                assert json.loads(n.export_state_json())==state
    finally:
        n.close();world.reset()
