"""
Unit-related components.
"""

from dataclasses import dataclass, field
import math
from typing import Set, Optional, Dict
from framework import Component
from ..prefabs.config import UnitType, Faction, UnitState, ActionType


@dataclass
class Unit(Component):
    """Unit component."""

    unit_type: UnitType
    faction: Faction
    name: str = ""
    level: int = 1
    experience: int = 0


@dataclass
class UnitCount(Component):
    """Unit headcount component."""

    current_count: int = 100  # Current headcount
    max_count: int = 100  # Max (full strength) headcount

    @property
    def ratio(self) -> float:
        """Headcount ratio."""
        return self.current_count / self.max_count if self.max_count > 0 else 0.0

    @property
    def percentage(self) -> float:
        """Headcount percentage."""
        return self.ratio * 100

    def is_decimated(self) -> bool:
        """Whether the unit is decimated (headcount <= 10%)."""
        return self.ratio <= 0.1


@dataclass
class UnitStatus(Component):
    """Unit status component."""

    current_status: UnitState = UnitState.NORMAL
    status_duration: int = 0  # Turns remaining for the current status
    wait_turns: int = 0  # Consecutive wait turns
    charge_stacks: int = 0  # Charge stacks


@dataclass
class Movement(Component):
    """Movement component."""

    base_movement: int  # Base movement points
    current_movement: int  # Current movement points
    has_moved: bool = False

    def get_effective_movement(self, unit_count: UnitCount) -> int:
        """Get effective movement after headcount scaling."""
        # -1 movement per 20% headcount loss (min 1)
        ratio = unit_count.ratio
        penalty = max(0, int((1 - ratio) / 0.2))
        return max(1, self.base_movement - penalty)


@dataclass
class Combat(Component):
    """Combat component."""

    base_attack: int  # Base attack
    base_defense: int  # Base defense
    attack_range: int = 1
    has_attacked: bool = False

    def attack_multiplier(self, h, A_m=0.92, p=0.5550325, s=0.035):
        # h should be in [0,1]
        if h <= 0.0:
            return 0.0
        w = 1.0 / (1.0 + math.exp(-(h - 0.3) / s))
        L = A_m + (1.0 - A_m) / 0.7 * (h - 0.3)
        P = A_m * (h / 0.3) ** p
        return w * L + (1.0 - w) * P


    def get_effective_stats(
        self, unit_count: UnitCount, status: UnitStatus, terrain_coeff: float = 1.0
    ) -> tuple:
        """Get effective attack/defense with headcount, status, and terrain."""
        from ..prefabs.config import GameConfig

        # Effective stat = base × f(headcount) × status_coeff × terrain_coeff
        ratio = unit_count.ratio
        # sigmoid-like modifier
        attack_modifier = self.attack_multiplier(ratio)
        defense_modifier = 1.0
        status_modifier = GameConfig.STATE_COEFFICIENTS.get(status.current_status, 1.0)

        effective_attack = (
            self.base_attack * attack_modifier * status_modifier * terrain_coeff
        )
        effective_defense = (
            self.base_defense * defense_modifier * status_modifier * terrain_coeff
        )

        return int(effective_attack), int(effective_defense)


@dataclass
class Vision(Component):
    """Vision component."""

    range: int
    visible_tiles: Set[tuple] = field(default_factory=set)


@dataclass
class Selected(Component):
    """Selection marker component."""

    selected: bool = True


@dataclass
class AIControlled(Component):
    """AI control marker component."""

    difficulty: str = "normal"
    last_action_time: float = 0.0


@dataclass
class UnitSkills(Component):
    """Unit skills component."""

    available_skills: Set[str] = field(default_factory=set)
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)  # Skill cooldowns

    def can_use_skill(self, skill_name: str) -> bool:
        """Return whether a skill can be used now."""
        return (
            skill_name in self.available_skills
            and self.skill_cooldowns.get(skill_name, 0) <= 0
        )

    def use_skill(self, skill_name: str, cooldown: int = 0):
        """Use a skill and apply its cooldown."""
        if skill_name in self.available_skills:
            self.skill_cooldowns[skill_name] = cooldown
