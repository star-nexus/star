"""
Random Event System - Handles terrain events and skill events (according to rulebook v1.2)
"""

import random
from typing import Dict, Any, Optional
from framework import System, World
from ..components import (
    HexPosition,
    Unit,
    UnitCount,
    UnitStatus,
    UnitSkills,
    DiceRoll,
    TerrainEvent,
    UnitSkillEvent,
    RandomEventQueue,
    MapData,
    Terrain,
)
from ..prefabs.config import GameConfig, TerrainType, UnitType, UnitState


class RandomEventSystem(System):
    """Random event system"""

    def __init__(self):
        super().__init__(priority=400)

    def initialize(self, world: World) -> None:
        self.world = world

        # Ensure random event queue exists
        if not self.world.get_singleton_component(RandomEventQueue):
            self.world.add_singleton_component(RandomEventQueue())

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Process event queue"""
        event_queue = self.world.get_singleton_component(RandomEventQueue)
        if not event_queue:
            return

        # Process all pending events
        while True:
            event = event_queue.process_next_event()
            if not event:
                break

            self._handle_event(event)

    def trigger_terrain_event(self, entity: int, action: str) -> bool:
        """Trigger terrain event"""
        position = self.world.get_component(entity, HexPosition)
        unit = self.world.get_component(entity, Unit)

        if not position or not unit:
            return False

        terrain_type = self._get_terrain_at_position((position.col, position.row))
        event_result = self._check_terrain_event(terrain_type, unit.unit_type, action)

        if event_result:
            # Add to event queue
            event_queue = self.world.get_singleton_component(RandomEventQueue)
            if event_queue:
                event_queue.add_event("terrain", entity, event_result)
            return True

        return False

    def trigger_skill_event(self, entity: int, skill_name: str) -> bool:
        """Trigger skill event"""
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)
        unit_skills = self.world.get_component(entity, UnitSkills)

        if not all([unit, unit_count, unit_skills]):
            return False

        # Check if skill is available
        if not unit_skills.can_use_skill(skill_name):
            return False

        # Check unit count requirements and execute dice roll
        skill_result = self._check_skill_requirements(
            unit.unit_type, unit_count, skill_name
        )

        if skill_result is not None:
            # Add to event queue
            event_queue = self.world.get_singleton_component(RandomEventQueue)
            if event_queue:
                event_queue.add_event("skill", entity, skill_result)
            return True

        return False

    def _check_terrain_event(
        self, terrain_type: TerrainType, unit_type: UnitType, action: str
    ) -> Optional[Dict]:
        """Check terrain event"""
        # Terrain event definitions (according to rulebook v1.2)
        terrain_events = {
            TerrainType.PLAIN: {
                "name": "Dust Cloud",
                "trigger": {"cavalry": ["move_end"]},
                "threshold": 5,
                "success": "Unit gains 'Hidden' status for 1 turn",
                "failure": "No effect",
            },
            TerrainType.MOUNTAIN: {
                "name": "Rockfall",
                "trigger": {"any": ["enter"]},
                "threshold": 6,
                "success": "Unit takes 2 true damage",
                "failure": "No effect",
            },
            TerrainType.URBAN: {
                "name": "City Defense",
                "trigger": {"archer": ["garrison"]},
                "threshold": 4,
                "success": "Next shot deals +50% damage",
                "failure": "Equipment malfunction, no bonus",
            },
            TerrainType.FOREST: {
                "name": "Lost Path",
                "trigger": {"any": ["enter"]},
                "threshold": 6,
                "success": "Unit moves 1 extra tile in random direction",
                "failure": "No effect",
            },
            TerrainType.HILL: {
                "name": "Highland Winds",
                "trigger": {"archer": ["attack"]},
                "threshold": 4,
                "success": "Archer range increased by 1",
                "failure": "Archer range decreased by 1",
            },
        }

        event_data = terrain_events.get(terrain_type)
        if not event_data:
            return None

        # Check trigger conditions
        triggers = event_data["trigger"]
        unit_triggers = triggers.get(unit_type.value, [])
        any_triggers = triggers.get("any", [])

        if action not in unit_triggers and action not in any_triggers:
            return None

        # Execute dice roll
        dice_roll = random.randint(1, 6)
        success = dice_roll >= event_data["threshold"]

        return {
            "name": event_data["name"],
            "dice_roll": dice_roll,
            "threshold": event_data["threshold"],
            "success": success,
            "effect": event_data["success"] if success else event_data["failure"],
        }

    def _check_skill_requirements(
        self, unit_type: UnitType, unit_count: UnitCount, skill_name: str
    ) -> Optional[Dict]:
        """Check skill requirements and execute judgment"""
        # Skill definitions (according to rulebook v1.2)
        skill_definitions = {
            UnitType.INFANTRY: {
                "Shield Wall: Reflect": {
                    "count_req": 0.5,
                    "threshold": 5,
                    "success": "Ranged damage reduced by 25%",
                    "failure": "Basic shield wall bonus only",
                },
                "Dense Formation": {
                    "count_req": 0.3,
                    "threshold": 4,
                    "success": "Self and adjacent friendly infantry defense +30%",
                    "failure": "Self defense +15% only",
                },
            },
            UnitType.CAVALRY: {
                "Charge: Critical Strike": {
                    "count_req": 0.4,
                    "threshold": 5,
                    "success": "Charge damage increased by 30% per stack",
                    "failure": "Maintain original 20% per stack",
                },
                "Raid: Trample": {
                    "count_req": 0.4,
                    "threshold": 4,
                    "success": "Deals normal collision damage",
                    "failure": "No damage dealt to this tile",
                },
            },
            UnitType.ARCHER: {
                "Snipe: Critical": {
                    "count_req": 0.7,
                    "threshold": 4,
                    "success": "First shot deals 1.5× critical damage",
                    "failure": "Normal damage",
                },
                "Suppression: Chaos": {
                    "count_req": 0.5,
                    "threshold": 5,
                    "success": "Area targets enter chaos for 1 turn",
                    "failure": "Damage only",
                },
            },
        }

        unit_skills = skill_definitions.get(unit_type, {})
        skill_data = unit_skills.get(skill_name)

        if not skill_data:
            return None

        # Check unit count requirements
        if unit_count.ratio < skill_data["count_req"]:
            return None

        # Execute dice roll
        dice_roll = random.randint(1, 6)
        success = dice_roll >= skill_data["threshold"]

        return {
            "skill_name": skill_name,
            "dice_roll": dice_roll,
            "threshold": skill_data["threshold"],
            "success": success,
            "effect": skill_data["success"] if success else skill_data["failure"],
        }

    def _handle_event(self, event: Dict[str, Any]):
        """Handle event"""
        event_type = event["type"]
        entity = event["entity"]
        data = event["data"]

        if event_type == "terrain":
            self._apply_terrain_effect(entity, data)
        elif event_type == "skill":
            self._apply_skill_effect(entity, data)

    def _apply_terrain_effect(self, entity: int, data: Dict[str, Any]):
        """Apply terrain event effect"""
        effect = data["effect"]

        if "Hidden" in effect:
            # Gain hidden status
            unit_status = self.world.get_component(entity, UnitStatus)
            if unit_status:
                unit_status.current_status = UnitState.HIDDEN
                unit_status.status_duration = 1

        elif "true damage" in effect:
            # Deal true damage
            unit_count = self.world.get_component(entity, UnitCount)
            if unit_count:
                damage = 2  # 2 points true damage
                unit_count.current_count = max(0, unit_count.current_count - damage)

        elif "shot damage" in effect:
            # Next shot damage bonus (requires temporary effect component)
            pass

        elif "extra move" in effect:
            # Move 1 extra tile in random direction (requires movement system coordination)
            pass

    def _apply_skill_effect(self, entity: int, data: Dict[str, Any]):
        """Apply skill effect"""
        skill_name = data["skill_name"]
        effect = data["effect"]
        success = data["success"]

        # Set skill cooldown
        unit_skills = self.world.get_component(entity, UnitSkills)
        if unit_skills:
            cooldown = 3 if success else 1  # Success cooldown 3 turns, failure 1 turn
            unit_skills.use_skill(skill_name, cooldown)

        # Apply effects
        if "chaos" in effect and success:
            # Find targets and apply chaos status (requires target selection logic)
            pass

        elif "critical" in effect and success:
            # Next attack guaranteed critical (requires temporary effect component)
            pass

        elif "charge damage" in effect:
            unit_status = self.world.get_component(entity, UnitStatus)
            if unit_status:
                # Update charge effect
                if success:
                    unit_status.charge_stacks = min(3, unit_status.charge_stacks + 1)

    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """Get terrain type at position"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN
