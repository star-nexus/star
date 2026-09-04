from rotk_env.components import Camera, DamageNumber
from rotk_env.systems.window_animation_system import AnimationSystem


class _Query:
    def __init__(self, entities):
        self._entities = entities

    def with_all(self, *component_types):
        return self

    def entities(self):
        return list(self._entities)


class _World:
    def __init__(self):
        self.camera = Camera(offset_x=100.0, offset_y=200.0, zoom=1.0)
        self.damage = {
            7: DamageNumber(
                text="12",
                position=(40.0, -10.0),
                lifetime=2.0,
                velocity=(0.0, -50.0),
            )
        }
        self.destroyed = []

    def get_singleton_component(self, component_type):
        if component_type is Camera:
            return self.camera
        return None

    def query(self):
        return _Query(self.damage)

    def get_component(self, entity, component_type):
        if component_type is DamageNumber:
            return self.damage.get(entity)
        return None

    def destroy_entity(self, entity):
        self.destroyed.append(entity)
        self.damage.pop(entity, None)


def _system(world):
    system = AnimationSystem.__new__(AnimationSystem)
    system.world = world
    system._floating_world_positions = {7: [40.0, -10.0]}
    return system


def test_damage_position_tracks_camera_zoom_from_same_world_anchor():
    world = _World()
    system = _system(world)

    system._update_damage_numbers(0.0)
    assert world.damage[7].position == (40.0, -10.0)

    world.camera.zoom = 2.5
    system._update_damage_numbers(0.0)
    assert world.damage[7].position == (100.0, -25.0)

    # Renderers add translation separately, so final screen position is the
    # same canonical transform used by map/unit rendering.
    screen_x = world.damage[7].position[0] + world.camera.offset_x
    screen_y = world.damage[7].position[1] + world.camera.offset_y
    assert (screen_x, screen_y) == (200.0, 175.0)


def test_damage_float_velocity_remains_world_space_when_zoomed():
    world = _World()
    world.camera.zoom = 2.0
    system = _system(world)

    system._update_damage_numbers(0.1)

    # World y: -10 + (-50 * .1) = -15, then camera zoom projects it to -30.
    assert world.damage[7].position == (80.0, -30.0)
    assert system._floating_world_positions[7] == [40.0, -15.0]
