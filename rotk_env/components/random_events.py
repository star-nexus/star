"""
Random event related components.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from framework import Component, SingletonComponent
from ..prefabs.config import TerrainType, UnitType


@dataclass
class DiceRoll(Component):
    """Dice roll check component."""

    dice_type: str = "1d6"  # Dice type
    threshold: int = 4  # Success threshold
    result: Optional[int] = None  # Roll result
    success: Optional[bool] = None  # Whether the check succeeded

    def roll(self) -> bool:
        """Execute the dice roll."""
        import random

        if self.dice_type == "1d6":
            self.result = random.randint(1, 6)
        self.success = self.result >= self.threshold
        return self.success


@dataclass
class TerrainEvent(Component):
    """Terrain-triggered event component."""

    terrain_type: TerrainType
    event_name: str
    trigger_condition: str  # Trigger condition description
    effect_description: str  # Effect description
    dice_threshold: int = 4  # Default threshold

    def can_trigger(self, unit_type: UnitType, action: str) -> bool:
        """Return whether the event can trigger."""
        # Determine triggers by terrain and unit type.
        terrain_triggers = {
            TerrainType.PLAIN: {"cavalry": ["move_end"]},
            TerrainType.MOUNTAIN: {"any": ["enter"]},
            TerrainType.URBAN: {"archer": ["garrison"]},
            TerrainType.WATER: {"ship": ["move_start"]},
            TerrainType.FOREST: {"any": ["enter"]},
            TerrainType.HILL: {"archer": ["attack"]},
        }

        triggers = terrain_triggers.get(self.terrain_type, {})
        return action in triggers.get("any", []) or action in triggers.get(
            unit_type.value, []
        )


@dataclass
class UnitSkillEvent(Component):
    """Unit skill event component."""

    skill_name: str
    unit_type: UnitType
    count_requirement: float  # Headcount requirement (ratio)
    success_effect: str  # Success effect
    failure_effect: str  # Failure effect
    dice_threshold: int = 4
    cooldown: int = 0  # Cooldown turns


@dataclass
class RandomEventQueue(SingletonComponent):
    """Singleton random event queue."""

    pending_events: List[Dict] = field(default_factory=list)
    processed_events: List[Dict] = field(default_factory=list)

    def add_event(self, event_type: str, entity_id: int, data: Dict):
        """Add an event to the queue."""
        event = {
            "type": event_type,
            "entity": entity_id,
            "data": data,
            "processed": False,
        }
        self.pending_events.append(event)

    def process_next_event(self) -> Optional[Dict]:
        """Process the next pending event."""
        if self.pending_events:
            event = self.pending_events.pop(0)
            event["processed"] = True
            self.processed_events.append(event)
            return event
        return None

    def clear_processed(self):
        """Clear processed events."""
        self.processed_events.clear()


@dataclass
class CombatRoll(Component):
    """Combat roll component."""

    hit_roll: Optional[int] = None  # Hit roll
    damage_roll: Optional[int] = None  # Damage roll
    crit_roll: Optional[int] = None  # Critical roll

    hit_threshold: int = 1  # Hit threshold
    crit_threshold: int = 19  # Critical threshold

    def roll_hit(self) -> bool:
        """Roll to hit."""
        import random

        self.hit_roll = random.randint(1, 20)
        return self.hit_roll >= self.hit_threshold

    def roll_crit(self) -> bool:
        """Roll a critical."""
        import random

        self.crit_roll = random.randint(1, 20)
        return self.crit_roll >= self.crit_threshold

    def apply_forest_penalty(self):
        """Apply forest hit-rate penalty."""
        # In forests, ranged hit rate -5%, approximated as +1 threshold.
        if self.hit_roll is not None:
            # Approximate 5% penalty as +1 threshold.
            self.hit_threshold = min(20, self.hit_threshold + 1)
