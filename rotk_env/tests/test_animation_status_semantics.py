from framework.ecs.world import World

from rotk_env.components import UnitStatus
from rotk_env.prefabs.config import UnitState
from rotk_env.systems.animation_system import AnimationSystem


def test_animation_update_does_not_mutate_simulation_unit_status():
    world = World()
    entity = world.create_entity()
    status = UnitStatus(current_status=UnitState.HIDDEN, status_duration=2)
    world.add_component(entity, status)

    system = AnimationSystem()
    system.world = world
    system.update(1.0)

    assert status.current_status == UnitState.HIDDEN
    assert status.status_duration == 2
