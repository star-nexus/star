"""Derived visual cache. No operation here can write native world state.

Rust supplies current lifecycle rows; this layer computes camera projection,
attack easing and projectile rotation using the existing Python render math.
"""

from dataclasses import fields
from rotk_env.components import (
    AttackAnimation,
    DamageNumber,
    EffectAnimation,
    ProjectileAnimation,
)
from rotk_env.systems.animation_system import AnimationSystem


class _RenderMath(AnimationSystem):
    def _create_projectile(self, attack_anim):
        # Projectile entity births belong to Rust's ordered lifecycle.
        pass


_MATH = _RenderMath.__new__(_RenderMath)
_TYPES = {
    "attack": AttackAnimation,
    "damage": DamageNumber,
    "effect": EffectAnimation,
    "projectile": ProjectileAnimation,
}
_FIELDS = {kind: {field.name for field in fields(cls)} for kind, cls in _TYPES.items()}


class VisualProjection:
    """Consume changed rows, retaining only current visual objects and positions."""

    def __init__(self):
        self.entities = {}
        self._floating = {}
        self._zoom = None

    def reset(self):
        self.entities.clear()
        self._floating.clear()
        self._zoom = None

    def apply(self, delta, *, zoom=1.0):
        for uid in delta["removed"]:
            self.entities.pop(uid, None)
            self._floating.pop(uid, None)
        for row in delta["rows"]:
            uid = row["id"]
            components = {}
            self._floating.pop(uid, None)
            for kind, state in row["components"].items():
                cls = _TYPES[kind]
                values = {
                    name: tuple(value) if isinstance(value, list) else value
                    for name, value in state.items()
                    if name in _FIELDS[kind]
                }
                visual = cls(**values)
                if kind == "attack":
                    if state["projectile_created"]:
                        visual._projectile_created = True
                    visual.current_render_pos = visual.start_pixel_pos
                    if visual.is_attacking and visual.total_duration > 0:
                        _MATH._update_attack_phase(visual)
                elif kind == "damage":
                    self._floating[uid] = tuple(state["world_position"])
                    visual.position = tuple(
                        value * zoom for value in self._floating[uid]
                    )
                elif kind == "projectile":
                    _MATH._calculate_projectile_position(visual)
                elif kind == "effect" and visual.duration != 0:
                    visual.progress = min(visual.elapsed_time / visual.duration, 1.0)
                components[cls] = visual
            if components:
                self.entities[uid] = components
            else:
                self.entities.pop(uid, None)  # Attack finished on a still-living unit.
        self.set_zoom(zoom)

    def set_zoom(self, zoom):
        if zoom == self._zoom:
            return
        self._zoom = zoom
        for uid, world_position in self._floating.items():
            self.entities[uid][DamageNumber].position = tuple(
                value * zoom for value in world_position
            )
