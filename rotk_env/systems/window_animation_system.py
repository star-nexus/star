"""Window animation coordinates for camera-scaled floating combat text.

Combat creates damage/MISS/CRIT text from hex positions in world-pixel space,
and the renderer consumes screen-relative coordinates. This window system keeps
the authoritative floating-text trajectory in world pixels and publishes
a camera-zoomed, screen-relative ``DamageNumber.position`` before rendering.
Renderers then add the camera offset exactly once.
"""

from __future__ import annotations

from typing import Tuple

from ..components import Camera, DamageNumber
from .animation_system import AnimationSystem as BaseAnimationSystem


class AnimationSystem(BaseAnimationSystem):
    """Visible-window AnimationSystem with canonical world→screen text motion."""

    def __init__(self):
        super().__init__()
        self._floating_world_positions: dict[int, list[float]] = {}

    def initialize(self, world) -> None:
        super().initialize(world)
        self._floating_world_positions.clear()

    def _screen_relative_position(
        self, world_pos: Tuple[float, float]
    ) -> Tuple[float, float]:
        """Apply camera zoom but not camera translation.

        Damage renderers already add the camera offset. Keeping translation out
        here prevents double application while making the same DamageNumber
        follow zoom changes just like the unit sprite below it.
        """
        camera = self.world.get_singleton_component(Camera)
        zoom = float(getattr(camera, "zoom", 1.0)) if camera is not None else 1.0
        return (float(world_pos[0]) * zoom, float(world_pos[1]) * zoom)

    def _create_floating_text(
        self,
        *,
        text: str,
        world_pos: Tuple[float, float],
        lifetime: float,
        velocity: Tuple[float, float],
        color: Tuple[int, int, int],
        font_size: int,
    ) -> int:
        entity = self.world.create_entity()
        self._floating_world_positions[entity] = [
            float(world_pos[0]),
            float(world_pos[1]),
        ]
        self.world.add_component(
            entity,
            DamageNumber(
                text=text,
                position=self._screen_relative_position(world_pos),
                lifetime=lifetime,
                velocity=velocity,
                color=color,
                font_size=font_size,
            ),
        )
        return entity

    def create_damage_number(self, damage: int, world_pos: Tuple[float, float]):
        return self._create_floating_text(
            text=str(damage),
            world_pos=world_pos,
            lifetime=2.0,
            velocity=(0, -50),
            color=(255, 0, 0) if damage > 0 else (0, 255, 0),
            font_size=24,
        )

    def create_miss_indicator(self, world_pos: Tuple[float, float]):
        return self._create_floating_text(
            text="MISS",
            world_pos=world_pos,
            lifetime=1.5,
            velocity=(0, -30),
            color=(128, 128, 128),
            font_size=20,
        )

    def create_crit_indicator(self, world_pos: Tuple[float, float]):
        return self._create_floating_text(
            text="CRIT!",
            world_pos=world_pos,
            lifetime=2.5,
            velocity=(0, -60),
            color=(255, 255, 0),
            font_size=28,
        )

    def create_healing_number(self, healing: int, world_pos: Tuple[float, float]):
        return self._create_floating_text(
            text=f"+{healing}",
            world_pos=world_pos,
            lifetime=2.0,
            velocity=(0, -40),
            color=(0, 255, 0),
            font_size=24,
        )

    def create_text_indicator(
        self,
        text: str,
        world_pos: Tuple[float, float],
        color: Tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
        lifetime: float = 2.0,
        velocity: Tuple[float, float] = (0, -50),
    ):
        return self._create_floating_text(
            text=text,
            world_pos=world_pos,
            lifetime=lifetime,
            velocity=velocity,
            color=color,
            font_size=font_size,
        )

    def _update_damage_numbers(self, delta_time: float):
        """Advance world-space trajectories, then project them for this zoom."""
        entities_to_remove = []
        entities = self.world.query().with_all(DamageNumber).entities()

        for entity in entities:
            damage_num = self.world.get_component(entity, DamageNumber)
            if damage_num is None:
                continue

            damage_num.elapsed_time += delta_time
            if damage_num.elapsed_time >= damage_num.lifetime:
                entities_to_remove.append(entity)
                continue

            world_pos = self._floating_world_positions.get(entity)
            if world_pos is None:
                # Components created outside the public AnimationSystem factory
                # are interpreted as world-pixel coordinates.
                world_pos = [
                    float(damage_num.position[0]),
                    float(damage_num.position[1]),
                ]
                self._floating_world_positions[entity] = world_pos

            world_pos[0] += float(damage_num.velocity[0]) * delta_time
            world_pos[1] += float(damage_num.velocity[1]) * delta_time
            damage_num.position = self._screen_relative_position(
                (world_pos[0], world_pos[1])
            )

        for entity in entities_to_remove:
            self._floating_world_positions.pop(entity, None)
            self.world.destroy_entity(entity)
