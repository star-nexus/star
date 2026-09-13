"""Compact animation lifecycle handoff, separate from fonts, surfaces and camera.

Entity creation/removal and ranged-projectile birth affect external IDs, so the
native runtime owns those timers. Python derives render interpolation from them.
"""

from .bootstrap import encode

FIELDS = {
    "attack": (
        "target_position",
        "progress",
        "speed",
        "is_attacking",
        "attack_type",
        "start_pixel_pos",
        "target_pixel_pos",
        "total_duration",
        "prepare_ratio",
        "aim_ratio",
        "strike_ratio",
        "return_ratio",
        "aim_line_color",
    ),
    "damage": ("text", "lifetime", "elapsed_time", "velocity", "color", "font_size"),
    "effect": (
        "effect_type",
        "is_playing",
        "effect_position",
        "effect_size",
        "effect_color",
        "duration",
        "elapsed_time",
    ),
    "projectile": (
        "start_pos",
        "target_pos",
        "flight_progress",
        "flight_speed",
        "is_flying",
        "projectile_type",
        "arc_height",
        "size",
        "color",
    ),
}


def export_visual_lifecycle(world):
    from rotk_env.components import (
        AttackAnimation,
        DamageNumber,
        EffectAnimation,
        ProjectileAnimation,
    )

    animation = next(
        (s for s in world.systems if type(s).__name__ == "AnimationSystem"), None
    )
    floating = getattr(animation, "_floating_world_positions", {})
    out = {kind: {} for kind in FIELDS}
    for kind, cls in zip(
        FIELDS, (AttackAnimation, DamageNumber, EffectAnimation, ProjectileAnimation)
    ):
        for uid in world.query().with_all(cls).ordered_entities():
            component = world.get_component(uid, cls)
            row = {name: encode(getattr(component, name)) for name in FIELDS[kind]}
            if kind == "attack":
                row["projectile_created"] = hasattr(component, "_projectile_created")
            if kind == "damage":
                row["world_position"] = encode(floating.get(uid, component.position))
            out[kind][str(uid)] = row
    return out
