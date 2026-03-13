"""
Multi-layer resource system components.

Implemented according to `MULTILAYER_RESOURCE_SYSTEM_DESIGN.md`.
"""

from dataclasses import dataclass, field
from typing import Dict, Set
from framework import Component
from ..prefabs.config import ActionType


@dataclass
class ActionPoints(Component):
    """Action points (AP) - decision-layer control."""

    current_ap: int = 2  # Current AP
    max_ap: int = 2  # Max AP

    def can_perform_action(self, action_type: ActionType) -> bool:
        """Return whether there is enough AP to perform the action."""
        cost = self._get_action_cost(action_type)
        return self.current_ap >= cost

    def consume_ap(self, action_type: ActionType) -> bool:
        """Consume AP for the action, if possible."""
        cost = self._get_action_cost(action_type)
        if self.current_ap >= cost:
            self.current_ap -= cost
            return True
        return False

    def _get_action_cost(self, action_type: ActionType) -> int:
        """Get AP cost for an action (decision layer)."""
        action_costs = {
            ActionType.MOVE: 1,  # Move: fixed cost 1
            ActionType.ATTACK: 1,  # Attack: fixed cost 1
            ActionType.REST: 1,  # Rest: fixed cost 1
            ActionType.SKILL: 1,  # Skill: fixed cost 1
            ActionType.OCCUPY: 1,  # Occupy: fixed cost 1
            ActionType.FORTIFY: 1,  # Fortify: fixed cost 1
        }
        return action_costs.get(action_type, 1)

    def reset(self):
        """Reset AP (at the start of a turn)."""
        self.current_ap = self.max_ap


@dataclass
class MovementPoints(Component):
    """Movement points (MP) - execution-layer movement."""

    current_mp: int = 3  # Current MP
    max_mp: int = 3  # Max MP (by unit type)
    base_mp: int = 3  # Base MP
    has_moved: bool = False  # Whether the unit has moved

    def get_effective_movement(self, unit_count) -> int:
        """Get effective MP after headcount scaling (only penalize severe losses)."""
        if not unit_count:
            return self.base_mp

        ratio = getattr(unit_count, "ratio", 1.0)

        if ratio > 0.2:
            penalty = 0
        else:
            penalty = 1

        effective = self.base_mp - penalty
        return max(2, effective)

    def can_move(self, cost: int) -> bool:
        """Return whether there is enough MP."""
        return self.current_mp >= cost

    def consume_movement(self, cost: int) -> bool:
        """Consume MP, if possible."""
        if self.current_mp >= cost:
            self.current_mp -= cost
            self.has_moved = True
            return True
        return False

    def reset(self):
        """Reset MP (at the start of a turn)."""
        self.current_mp = self.max_mp
        self.has_moved = False


@dataclass
class AttackPoints(Component):
    """Attack points - execution-layer attacks."""

    normal_attacks: int = 1  # Normal attack count
    max_normal_attacks: int = 1  # Max normal attacks
    skill_points: int = 2  # Skill points
    max_skill_points: int = 2  # Max skill points

    def can_normal_attack(self) -> bool:
        """Return whether a normal attack can be performed."""
        return self.normal_attacks > 0

    def can_use_skill(self, skill_cost: int) -> bool:
        """Return whether there are enough points to use a skill."""
        return self.skill_points >= skill_cost

    def consume_normal_attack(self) -> bool:
        """Consume one normal attack, if possible."""
        if self.normal_attacks > 0:
            self.normal_attacks -= 1
            return True
        return False

    def consume_skill_points(self, cost: int) -> bool:
        """Consume skill points, if possible."""
        if self.skill_points >= cost:
            self.skill_points -= cost
            return True
        return False

    def reset_normal_attacks(self):
        """Reset normal attacks (automatic per turn)."""
        self.normal_attacks = self.max_normal_attacks

    def restore_skill_points(self):
        """Restore skill points (requires a rest action)."""
        self.skill_points = self.max_skill_points


@dataclass
class ConstructionPoints(Component):
    """Construction points - execution-layer building."""

    current_cp: int = 3  # Current construction points (set to 3 per design doc)
    max_cp: int = 3  # Max construction points

    def can_build(self, cost: int) -> bool:
        """Return whether building is possible."""
        return self.current_cp >= cost

    def consume_construction(self, cost: int) -> bool:
        """Consume construction points, if possible."""
        if self.current_cp >= cost:
            self.current_cp -= cost
            return True
        return False

    def restore_to_city(self):
        """Restore construction points in a city/base."""
        self.current_cp = self.max_cp


@dataclass
class SkillPoints(Component):
    """Skill points - execution-layer skills (separate from attack skill points)."""

    current_sp: int = 3  # Current skill points
    max_sp: int = 3  # Max skill points
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)  # Skill cooldowns

    def can_use_skill(self, skill_name: str, cost: int = 1) -> bool:
        """Return whether a skill can be used now."""
        if skill_name in self.skill_cooldowns and self.skill_cooldowns[skill_name] > 0:
            return False
        return self.current_sp >= cost

    def use_skill(self, skill_name: str, cost: int = 1, cooldown: int = 0) -> bool:
        """Use a skill, consuming points and applying cooldown."""
        if self.can_use_skill(skill_name, cost):
            self.current_sp -= cost
            if cooldown > 0:
                self.skill_cooldowns[skill_name] = cooldown
            return True
        return False

    def restore_by_rest(self):
        """Restore skill points via a rest action."""
        self.current_sp = self.max_sp

    def update_cooldowns(self):
        """Update cooldown timers (called each turn)."""
        for skill_name in list(self.skill_cooldowns.keys()):
            self.skill_cooldowns[skill_name] -= 1
            if self.skill_cooldowns[skill_name] <= 0:
                del self.skill_cooldowns[skill_name]


# Backward-compatibility aliases (kept intentionally).
# Movement = MovementPoints
