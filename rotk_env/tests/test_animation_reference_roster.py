from copy import deepcopy
from types import SimpleNamespace

import pytest

from framework.ecs.world import World
from rotk_env.components import HexPosition, MovementAnimation
from rotk_env.systems.animation_system import AnimationSystem


def fixture():
    world = World()
    system = AnimationSystem()
    system.world = world
    for i in range(3):
        entity = world.create_entity()
        world.add_component(entity, HexPosition(0,i))
        system.start_unit_movement(entity, [(0,i),(1,i),(2,i),(3,i)])
    return world, system


def state(world):
    return [(e,deepcopy(world.get_component(e,HexPosition)),
             deepcopy(world.get_component(e,MovementAnimation)))
            for e in world.query().with_all(HexPosition,MovementAnimation).entities()]


def test_steady_roster_reads_live_fields_without_new_world_queries(monkeypatch):
    world, system = fixture()
    system._update_movement_animations(.01)
    entries = system._movement_entries_cache
    anim = entries[1][2]
    anim.speed = 3
    prior = anim.progress
    def unexpected(*args):
        raise AssertionError('stable movement roster must reuse references')
    monkeypatch.setattr(world,'query',unexpected)
    monkeypatch.setattr(world,'get_component_pair',unexpected)
    monkeypatch.setattr(world,'get_component',unexpected)
    system._update_movement_animations(.02)
    assert system._movement_entries_cache is entries
    assert anim.progress == pytest.approx(prior+.06)


@pytest.mark.parametrize('action',['remove','replace','destroy','add','clear'])
def test_commit_callback_observes_current_rows_and_original_entity_snapshot(action):
    def run(cached):
        world, system = fixture()
        if not cached:
            world.component_reference_version = None
        ids = list(world.query().with_all(HexPosition,MovementAnimation).entities())
        second = ids[1]
        fired = False
        def commit(entity,col,row,*,arrived):
            nonlocal fired
            pos = world.get_component(entity,HexPosition)
            pos.col,pos.row=col,row
            if fired: return
            fired=True
            if action=='remove': world.remove_component(second,MovementAnimation)
            elif action=='destroy': world.destroy_entity(second)
            elif action=='replace':
                replacement=deepcopy(world.get_component(second,MovementAnimation))
                replacement.progress=.15
                replacement.speed=3
                world.add_component(second,replacement)
                world.add_component(second,HexPosition(4,5))
            elif action=='add':
                new = world.create_entity()
                world.add_component(new,HexPosition(0,8))
                system.start_unit_movement(new,[(0,8),(1,8)])
            elif action=='clear': world.clear_cache()
        system._get_movement_system=lambda:SimpleNamespace(commit_hex_position=commit)
        system._update_movement_animations(.6)
        first=state(world)
        system._update_movement_animations(.1)
        return first,state(world)
    assert run(True)==run(False)


def test_reference_replacement_between_frames_and_world_reuse():
    world, system = fixture()
    system._update_movement_animations(.01)
    old = system._movement_entries_cache
    entity = old[0][0]
    new = deepcopy(old[0][2]); new.speed = 4
    world.add_component(entity,new)
    before = new.progress
    system._update_movement_animations(.1)
    assert new.progress == pytest.approx(before+.4)
    assert system._movement_entries_cache is not old
    other, unused = fixture()
    system.world = other
    system._update_movement_animations(.01)
    assert system._movement_entries_world is other
    assert system._movement_entries_cache[0][1] is other.get_component(entity,HexPosition)
