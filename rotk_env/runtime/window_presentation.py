"""Battlefield rendering over a native-derived World, without Python simulation."""

from rotk_env.systems.window_animation_system import AnimationSystem as _LegacyAnimation


class AnimationSystem(_LegacyAnimation):
    """Keep cached floating-text drawing; all lifecycle advancement belongs to Rust.

    Existing unit renderers discover this system by its historical class name.
    They can call its drawing helpers, while World.update only projects the camera.
    """

    def __init__(self, presentation):
        super().__init__()
        self.presentation = presentation

    def update(self, delta_time):
        self.presentation.update_camera()


def attach_battlefield_renderers(presentation):
    """Mount the existing map/unit/effect renderers on an inactive display World.

    The engine and fonts must be initialized. Inputs, HUD/settlement and the scene
    lifecycle are wired separately; this function must not retain gameplay systems.
    """
    from rotk_env.systems.optimized_render_systems import MapRenderSystem
    from rotk_env.systems.window_unit_render_system import UnitRenderSystem
    from rotk_env.systems.window_effect_render_system import EffectRenderSystem

    world = presentation.world
    if world.systems:
        raise ValueError("Battlefield presentation requires a World without systems")
    systems = [
        AnimationSystem(presentation),
        MapRenderSystem(),
        UnitRenderSystem(),
        EffectRenderSystem(),
    ]
    for system in systems:
        world.add_system(system)
    return systems
