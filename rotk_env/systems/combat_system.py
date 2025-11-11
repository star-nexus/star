"""
Combat System - Handles unit combat (according to rulebook v1.2)
"""

import random
import math
from typing import Tuple, Optional, Dict, Any
from framework import System, World
from framework.engine.events import EBS
from ..components import (
    HexPosition,
    Combat,
    UnitCount,
    UnitStatus,
    Unit,
    Player,
    MapData,
    Terrain,
    Tile,
    GameStats,
    GameState,
    ActionPoints,
    CombatRoll,
    RandomEventQueue,
    BattleLog,
)
from ..prefabs.config import (
    GameConfig,
    TerrainType,
    UnitType,
    UnitState,
    ActionType,
    Faction,
)
from ..utils.hex_utils import HexMath
from ..utils.env_events import BattleEvent, UnitDeathEvent


class CombatSystem(System):
    """Combat system - implemented per rulebook v1.2"""

    def __init__(self):
        super().__init__(priority=300)

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        """Subscribe to events"""
        pass

    def update(self, delta_time: float) -> None:
        """Update combat system"""
        pass

    def execute_attack(
        self, attacker_entity: int, target_entity: int
    ) -> Optional[Dict[str, Any]]:
        """Execute an attack and return detailed combat result (for LLM layer)"""
        # Basic validation (LLM layer is responsible; keep final guard here)
        valid, reason, context = self._validate_attack(attacker_entity, target_entity)
        if not valid:
            return {
                "success": False,
                "error": reason or "invalid_attack",
                "message": "Attack validation failed",
                "details": context or {},
            }

        # Check action points (LLM layer is responsible; final guard here)
        action_points = self.world.get_component(attacker_entity, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.ATTACK):
            return {
                "success": False,
                "error": "insufficient_action_points",
                "message": "Insufficient action points for attack",
                "details": {
                    "attacker_entity": attacker_entity,
                    "current_ap": action_points.current_ap if action_points else None,
                    "required_ap": 1,
                    "suggestion": "Wait for action points to recover before attacking",
                },
            }

        # Snapshot pre-battle state
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_count = self.world.get_component(attacker_entity, UnitCount)
        attacker_status = self.world.get_component(attacker_entity, UnitStatus)
        attacker_unit = self.world.get_component(attacker_entity, Unit)

        target_count = self.world.get_component(target_entity, UnitCount)
        target_status = self.world.get_component(target_entity, UnitStatus)
        target_unit = self.world.get_component(target_entity, Unit)

        # 记录战斗前状态
        pre_battle_state = {
            "attacker_count": attacker_count.current_count,
            "target_count": target_count.current_count,
            "attacker_ap": action_points.current_ap,
        }

        # Create combat roll component
        combat_roll = CombatRoll()
        self.world.add_component(attacker_entity, combat_roll)

        # Determine animation type based on attack type
        attack_type = (
            "ranged" if attacker_unit.unit_type == UnitType.ARCHER else "melee"
        )

        # Trigger attack animation
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_attack_animation(
                attacker_entity, target_entity, attack_type
            )

        # Calculate terrain bonuses
        attacker_terrain_bonus = self._get_terrain_attack_bonus(
            (attacker_pos.col, attacker_pos.row), attacker_unit.faction
        )
        target_terrain_defense = self._get_terrain_defense_bonus(
            (target_pos.col, target_pos.row), target_unit.faction
        )

        # 1) Hit check
        hit_success = self._roll_hit(combat_roll, attacker_pos, target_pos)

        battle_result = {
            "battle_type": attack_type,
            "hit_success": hit_success,
            "is_critical": False,
            "damage_dealt": 0,
            "casualties_inflicted": 0,
            "target_destroyed": False,
            "attacker_casualties": 0,  # 简化版本，暂时不实现反击
            "terrain_effects": {
                "attacker_terrain_bonus": attacker_terrain_bonus,
                "target_terrain_defense": target_terrain_defense,
            },
            "dice_rolls": {
                "hit_roll": (
                    combat_roll.hit_roll if hasattr(combat_roll, "hit_roll") else None
                ),
                "damage_roll": None,
                "crit_roll": None,
            },
            "combat_log": [],
        }

        if not hit_success:
            # Miss handling
            attacker_faction = attacker_unit.faction.value
            target_faction = target_unit.faction.value
            miss_message = f"{attacker_faction} forces missed {target_faction}!"
            print(f"❌ {miss_message}")

            battle_result["combat_log"].append(miss_message)
            self._create_miss_display(target_entity)
            self._record_miss_to_systems(attacker_entity, target_entity)
            action_points.consume_ap(ActionType.ATTACK)
            return {
                "success": True,
                "battle_result": battle_result,
            }

        # 2) Calculate base damage
        damage = self._calculate_damage(
            attacker_entity,
            target_entity,
            attacker_count,
            target_count,
            attacker_status,
            target_status,
        )

        battle_result["dice_rolls"]["damage_roll"] = damage

        # 3) Critical check
        is_crit = self._roll_crit(combat_roll)
        battle_result["is_critical"] = is_crit

        if is_crit:
            damage = int(damage * 1.5)
            battle_result["dice_rolls"]["crit_roll"] = True
            self._create_crit_display(target_entity)
            battle_result["combat_log"].append("Critical hit! Damage ×1.5!")

        battle_result["damage_dealt"] = damage

        # 4) Apply damage
        old_count = target_count.current_count
        self._apply_damage(target_entity, damage)
        new_count = target_count.current_count

        casualties = old_count - new_count
        battle_result["casualties_inflicted"] = casualties
        battle_result["target_destroyed"] = new_count <= 0

        # Create attack VFX
        if animation_system:
            from ..utils.hex_utils import HexConverter

            hex_converter = HexConverter(
                GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
            )
            world_x, world_y = hex_converter.hex_to_pixel(
                target_pos.col, target_pos.row
            )

            # Choose effect based on attack type and critical
            if is_crit:
                effect_type = "explosion"
            elif attack_type == "ranged":
                effect_type = "impact"
            else:
                effect_type = "slash"

            animation_system.create_attack_effect((world_x, world_y), effect_type)

        # Console output and combat log
        attacker_faction = attacker_unit.faction.value
        target_faction = target_unit.faction.value

        if is_crit:
            combat_message = f"{attacker_faction} forces critical hit on {target_faction}! damage:{damage}, count:{old_count}->{new_count}"
            print(f"💥 {combat_message}")
        else:
            combat_message = f"{attacker_faction} forces attacked {target_faction}! damage:{damage}, count:{old_count}->{new_count}"
            print(f"⚔️ {combat_message}")

        battle_result["combat_log"].append(combat_message)

        # 5) Consume action points
        action_points.consume_ap(ActionType.ATTACK)
        # attacker_combat.has_attacked = True  # 移除单次攻击限制，允许多次攻击

        # 6) Handle special effects
        self._handle_combat_effects(attacker_entity, target_entity)

        # 7) Record statistics and events
        result = "kill" if target_count.current_count <= 0 else "damage"
        self._record_combat_to_systems(attacker_entity, target_entity, damage, result)

        # Publish combat event
        EBS.publish(BattleEvent(attacker_entity, target_entity, damage))

        # 8) Check unit death
        if target_count.current_count <= 0:
            self._handle_unit_death(target_entity, attacker_entity)
            battle_result["combat_log"].append(f"{target_faction} unit destroyed!")

        # 9) Populate detailed combat result
        battle_result.update(
            {
                "pre_battle_state": pre_battle_state,
                "post_battle_state": {
                    "attacker_count": attacker_count.current_count,
                    "target_count": target_count.current_count,
                    "attacker_ap": action_points.current_ap,
                },
                "action_points_consumed": pre_battle_state["attacker_ap"]
                - action_points.current_ap,
            }
        )

        return {
            "success": True,
            "battle_result": battle_result,
        }

    def attack(self, attacker_entity: int, target_entity: int) -> bool:
        """Execute attack (full rules implementation)"""
        # Basic validation
        valid, _, _ = self._validate_attack(attacker_entity, target_entity)
        if not valid:
            return False

        # Check action points
        action_points = self.world.get_component(attacker_entity, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.ATTACK):
            return False

        # Get components
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_count = self.world.get_component(attacker_entity, UnitCount)
        attacker_status = self.world.get_component(attacker_entity, UnitStatus)
        attacker_unit = self.world.get_component(attacker_entity, Unit)

        target_count = self.world.get_component(target_entity, UnitCount)
        target_status = self.world.get_component(target_entity, UnitStatus)
        target_unit = self.world.get_component(target_entity, Unit)

        # Create combat roll component
        combat_roll = CombatRoll()
        self.world.add_component(attacker_entity, combat_roll)

        # Determine animation type based on attack type
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        attack_type = (
            "ranged" if attacker_unit.unit_type == UnitType.ARCHER else "melee"
        )

        # Trigger attack animation
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_attack_animation(
                attacker_entity, target_entity, attack_type
            )

        # 1) Hit check
        if not self._roll_hit(combat_roll, attacker_pos, target_pos):
            # Console output for miss
            attacker_faction = attacker_unit.faction.value
            target_faction = target_unit.faction.value
            print(f"❌ {attacker_faction} forces missed {target_faction}!")

            self._create_miss_display(target_entity)
            # Record miss to BattleLog
            self._record_miss_to_systems(attacker_entity, target_entity)
            action_points.consume_ap(ActionType.ATTACK)
            return False

        # 2) Calculate base damage
        damage = self._calculate_damage(
            attacker_entity,
            target_entity,
            attacker_count,
            target_count,
            attacker_status,
            target_status,
        )

        # 3) Critical check
        is_crit = False
        if self._roll_crit(combat_roll):
            damage = int(damage * 1.5)
            is_crit = True
            self._create_crit_display(target_entity)

        # 4) Apply damage
        old_count = target_count.current_count
        self._apply_damage(target_entity, damage)
        new_count = target_count.current_count

        # Create attack VFX
        if animation_system:
            from ..utils.hex_utils import HexConverter

            hex_converter = HexConverter(
                GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
            )
            world_x, world_y = hex_converter.hex_to_pixel(
                target_pos.col, target_pos.row
            )

            # Choose effect based on attack type and critical
            if is_crit:
                effect_type = "explosion"
            elif attack_type == "ranged":
                effect_type = "impact"
            else:
                effect_type = "slash"

            animation_system.create_attack_effect((world_x, world_y), effect_type)

        # Console output
        attacker_faction = attacker_unit.faction.value
        target_faction = target_unit.faction.value
        if is_crit:
            print(
                f"💥 {attacker_faction} forces critical hit on {target_faction}! damage:{damage}, count:{old_count}->{new_count}"
            )
        else:
            print(
                f"⚔️ {attacker_faction} forces attacked {target_faction}! damage:{damage}, count:{old_count}->{new_count}"
            )

        # 5) Consume action points
        action_points.consume_ap(ActionType.ATTACK)
        # attacker_combat.has_attacked = True  # 移除单次攻击限制，允许多次攻击

        # 6) Handle special effects
        self._handle_combat_effects(attacker_entity, target_entity)

        # 7) Record statistics and events
        result = "kill" if target_count.current_count <= 0 else "damage"
        self._record_combat_to_systems(attacker_entity, target_entity, damage, result)

        # Publish combat event
        EBS.publish(BattleEvent(attacker_entity, target_entity, damage))

        # 8) Check unit death
        if target_count.current_count <= 0:
            self._handle_unit_death(target_entity, attacker_entity)

        return True

    def _validate_attack(
        self, attacker_entity: int, target_entity: int
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate whether an attack is valid"""
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_count = self.world.get_component(attacker_entity, UnitCount)
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        components = {
            "attacker_pos": attacker_pos,
            "target_pos": target_pos,
            "attacker_combat": attacker_combat,
            "attacker_count": attacker_count,
            "attacker_unit": attacker_unit,
            "target_unit": target_unit,
        }

        missing = [name for name, comp in components.items() if comp is None]
        if missing:
            return (
                False,
                "missing_components",
                {
                    "missing": missing,
                    "attacker_entity": attacker_entity,
                    "target_entity": target_entity,
                    "suggestion": "Ensure both attacker and target units exist and are initialized correctly",
                },
            )



        # Disabled single-attack-per-turn check - allow multiple attacks (if AP allows)
        # if attacker_combat.has_attacked:
        #     return False

        # Check attack range
        distance = HexMath.hex_distance(
            (attacker_pos.col, attacker_pos.row), (target_pos.col, target_pos.row)
        )
        if distance > attacker_combat.attack_range:
            return (
                False,
                "target_out_of_range",
                {
                    "attacker_entity": attacker_entity,
                    "target_entity": target_entity,
                    "distance": distance,
                    "attack_range": attacker_combat.attack_range,
                    "suggestion": "Move closer to the target before attacking",
                },
            )

        # Ensure target is enemy
        if attacker_unit.faction == target_unit.faction:
            return (
                False,
                "friendly_fire",
                {
                    "attacker_entity": attacker_entity,
                    "target_entity": target_entity,
                    "attacker_faction": attacker_unit.faction.value,
                    "target_faction": target_unit.faction.value,
                    "suggestion": "Select an enemy unit instead of a friendly unit",
                },
            )

        return True, None, None

    def _roll_hit(
        self,
        combat_roll: CombatRoll,
        attacker_pos: HexPosition,
        target_pos: HexPosition,
    ) -> bool:
        """Roll to hit (1D20 ≥ 2)"""
        # Check terrain effects (forest -20% hit rate)
        target_terrain = self._get_terrain_at_position((target_pos.col, target_pos.row))
        if target_terrain == TerrainType.FOREST:
            combat_roll.apply_forest_penalty()

        return combat_roll.roll_hit()

    def _roll_crit(self, combat_roll: CombatRoll) -> bool:
        """Roll for critical (1D6 ≥ 6)"""
        return combat_roll.roll_crit()

    def _calculate_damage(
        self,
        attacker_entity: int,
        target_entity: int,
        attacker_count: UnitCount,
        target_count: UnitCount,
        attacker_status: UnitStatus,
        target_status: UnitStatus,
    ) -> int:
        """Calculate damage (dynamic attack/defense formula)"""
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        target_combat = self.world.get_component(target_entity, Combat)
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)

        # Get terrain coefficients
        attacker_terrain_coeff = self._get_terrain_coefficient(
            (attacker_pos.col, attacker_pos.row), attacker_unit.unit_type
        )
        target_terrain_coeff = self._get_terrain_coefficient(
            (target_pos.col, target_pos.row), target_unit.unit_type
        )

        # Compute effective attack/defense
        effective_attack, _ = attacker_combat.get_effective_stats(
            attacker_count, attacker_status, attacker_terrain_coeff
        )
        _, effective_defense = target_combat.get_effective_stats(
            target_count, target_status, target_terrain_coeff
        )

        # Apply attack bonuses (terrain + territory)
        terrain_attack_bonus = self._get_terrain_attack_bonus(
            (attacker_pos.col, attacker_pos.row), attacker_unit.faction
        )
        effective_attack += terrain_attack_bonus

        # Apply special defense rules
        effective_defense = self._apply_defense_bonuses(
            target_entity, effective_defense
        )

        # Base damage calculation
        base_damage = max(1, effective_attack - int(effective_defense * 0.5))

        # Count impact: final damage × (N_att / N_def)^0.5 (simplified placeholder)
        count_ratio = (
            1.0  # (attacker_count.current_count / target_count.current_count) ** 0.5
        )
        damage = int(base_damage * count_ratio)

        # Apply special modifiers (charge, skills, etc.)
        damage = self._apply_special_modifiers(attacker_entity, damage)

        return max(1, damage)

    def _apply_defense_bonuses(self, target_entity: int, base_defense: int) -> int:
        """Apply defense bonuses"""
        target_unit = self.world.get_component(target_entity, Unit)
        target_pos = self.world.get_component(target_entity, HexPosition)

        defense = base_defense

        # Infantry shield wall: +1 defense when attacked by ranged (simplified)
        if target_unit.unit_type == UnitType.INFANTRY:
            # 这里需要判断攻击者是否为远程，简化处理
            defense += 1

        # Terrain defense modifier
        terrain_defense = self._get_terrain_defense_bonus(
            (target_pos.col, target_pos.row), target_unit.faction
        )
        defense += terrain_defense

        return defense

    def _apply_special_modifiers(self, attacker_entity: int, base_damage: int) -> int:
        """Apply special damage modifiers"""
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        attacker_status = self.world.get_component(attacker_entity, UnitStatus)

        damage = base_damage

        # Cavalry charge: first-attack damage ×1.5 when charging
        if (
            attacker_unit.unit_type == UnitType.CAVALRY
            and attacker_status.charge_stacks > 0
        ):
            damage = int(damage * 1.5)
            # Clear charge status
            attacker_status.charge_stacks = 0

        return damage

    def _apply_damage(self, target_entity: int, damage: int):
        """Apply damage to unit count"""
        target_count = self.world.get_component(target_entity, UnitCount)

        # Convert damage to casualties (simplified: 1 damage = 1 casualty)
        casualties = min(damage, target_count.current_count)
        target_count.current_count -= casualties

        # Create damage number display
        self._create_damage_display(target_entity, casualties)

    def _handle_combat_effects(self, attacker_entity: int, target_entity: int):
        """Handle post-combat effects"""
        # 更新状态为战斗状态
        for entity in [attacker_entity, target_entity]:
            status = self.world.get_component(entity, UnitStatus)
            if status:
                status.current_status = UnitState.NORMAL
                status.status_duration = 0

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """Get terrain type at position"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_terrain_coefficient(
        self, position: Tuple[int, int], unit_type: UnitType
    ) -> float:
        """Get terrain coefficient"""
        terrain_type = self._get_terrain_at_position(position)
        terrain_coeff = GameConfig.TERRAIN_COEFFICIENTS.get(terrain_type)

        if not terrain_coeff:
            return 1.0

        if unit_type == UnitType.INFANTRY:
            return terrain_coeff.infantry
        elif unit_type == UnitType.CAVALRY:
            return terrain_coeff.cavalry
        elif unit_type == UnitType.ARCHER:
            return terrain_coeff.archer

        return 1.0

    def _get_terrain_attack_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> float:
        """Get terrain attack bonus (base terrain + territory control)"""
        # 1) Base terrain attack bonus (from terrain type)
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        base_attack_bonus = terrain_effect.attack_bonus if terrain_effect else 0.0

        # 2) Territory control bonus (if territory system exists)
        territory_bonus = 0.0
        territory_system = self._get_territory_system()
        if territory_system:
            territory_bonus = (
                territory_system.get_territory_attack_bonus(position, faction) / 10.0
            )

        return base_attack_bonus + territory_bonus

    def _get_terrain_defense_bonus(
        self, position: Tuple[int, int], faction: Faction = None
    ) -> float:
        """Get terrain defense bonus (base terrain + territory control)"""
        # 1) Base terrain defense bonus (from terrain type)
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        base_defense_bonus = terrain_effect.defense_bonus if terrain_effect else 0.0

        # 2) Territory control bonus (if system exists and faction provided)
        territory_bonus = 0.0
        if faction:
            territory_system = self._get_territory_system()
            if territory_system:
                # Assume territory system provides defense bonus; otherwise use base only
                if hasattr(territory_system, "get_territory_defense_bonus"):
                    territory_bonus = (
                        territory_system.get_territory_defense_bonus(position, faction)
                        / 10.0
                    )

        return base_defense_bonus + territory_bonus

    def _handle_unit_death(self, entity: int, killer_entity: int = None):
        """Handle unit death"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # Console output for death
        pos = self.world.get_component(entity, HexPosition)
        pos_str = f"@({pos.col},{pos.row})" if pos else ""
        if killer_entity:
            killer_unit = self.world.get_component(killer_entity, Unit)
            killer_faction = killer_unit.faction.value if killer_unit else "unknown"
            print(
                f"💀 {unit.faction.value} unit {pos_str} was killed by {killer_faction}!"
            )
        else:
            print(f"💀 {unit.faction.value} unit {pos_str} died!")

        # Record death to statistics system
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_death_action(entity, killer_entity)

        # Update statistics
        stats = self.world.get_singleton_component(GameStats)
        if stats and unit.faction in stats.faction_stats:
            stats.faction_stats[unit.faction]["losses"] += 1

        # Remove from player's unit list
        for player_entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(player_entity, Player)
            if player and player.faction == unit.faction:
                player.units.discard(entity)
                break

        # Clear tile occupation
        position = self.world.get_component(entity, HexPosition)
        if position:
            map_data = self.world.get_singleton_component(MapData)
            if map_data:
                tile_entity = map_data.tiles.get((position.col, position.row))
                if tile_entity:
                    tile = self.world.get_component(tile_entity, Tile)
                    if tile and tile.occupied_by == entity:
                        tile.occupied_by = None

                # Publish unit death event
        EBS.publish(UnitDeathEvent(entity, unit.faction))

        # Destroy entity
        self.world.destroy_entity(entity)

    def _record_combat_stats(
        self, attacker_entity: int, target_entity: int, damage: int
    ):
        """Record combat stats (fallback path)"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        if not attacker_unit or not target_unit:
            return

        # Initialize stats bucket if missing
        for faction in [attacker_unit.faction, target_unit.faction]:
            if faction not in stats.faction_stats:
                stats.faction_stats[faction] = {
                    "kills": 0,
                    "losses": 0,
                    "damage_dealt": 0,
                    "damage_taken": 0,
                }

        # Record damage
        stats.faction_stats[attacker_unit.faction]["damage_dealt"] += damage
        stats.faction_stats[target_unit.faction]["damage_taken"] += damage

        # Record battle history
        battle_record = {
            "turn": self.world.get_singleton_component(GameState).turn_number,
            "attacker": attacker_unit.faction.value,
            "target": target_unit.faction.value,
            "damage": damage,
        }
        stats.battle_history.append(battle_record)

    def _record_combat_to_systems(
        self, attacker_entity: int, target_entity: int, damage: int, result: str
    ):
        """Record combat to various systems (statistics, BattleLog, etc.)"""
        # First try statistics system
        statistics_system = self._get_statistics_system()
        if statistics_system:
            try:
                statistics_system.record_combat_action(
                    attacker_entity, target_entity, damage, result
                )
            except Exception as e:
                print(f"Failed to record combat in statistics system: {e}")
                # Fallback to local stats if statistics system fails
                self._record_combat_stats(attacker_entity, target_entity, damage)
        else:
            # If no statistics system, use fallback path
            self._record_combat_stats(attacker_entity, target_entity, damage)

    def _get_statistics_system(self):
        """Get statistics system"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _record_miss_to_systems(self, attacker_entity: int, target_entity: int):
        """Record a miss to systems"""
        # Add miss record directly to BattleLog
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            attacker_unit = self.world.get_component(attacker_entity, Unit)
            target_unit = self.world.get_component(target_entity, Unit)

            if attacker_unit and target_unit:
                message = f"{attacker_unit.faction.value} attack on {target_unit.faction.value} missed"
                battle_log.add_entry(
                    message, "combat", attacker_unit.faction.value, (128, 128, 128)
                )

    def _create_damage_display(self, target_entity: int, damage: int):
        """Create damage number display"""
        target_pos = self.world.get_component(target_entity, HexPosition)
        if not target_pos:
            return

        animation_system = self._get_animation_system()
        if not animation_system:
            return

        from ..utils.hex_utils import HexConverter

        hex_converter = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION)
        world_x, world_y = hex_converter.hex_to_pixel(target_pos.col, target_pos.row)
        world_y -= 30

        animation_system.create_damage_number(damage, (world_x, world_y))

    def _create_miss_display(self, target_entity: int):
        """Create miss indicator display"""
        target_pos = self.world.get_component(target_entity, HexPosition)
        if not target_pos:
            return

        animation_system = self._get_animation_system()
        if not animation_system:
            return

        from ..utils.hex_utils import HexConverter

        hex_converter = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION)
        world_x, world_y = hex_converter.hex_to_pixel(target_pos.col, target_pos.row)
        world_y -= 30

        animation_system.create_miss_indicator((world_x, world_y))

    def _create_crit_display(self, target_entity: int):
        """Create critical indicator display"""
        target_pos = self.world.get_component(target_entity, HexPosition)
        if not target_pos:
            return

        animation_system = self._get_animation_system()
        if not animation_system:
            return

        from ..utils.hex_utils import HexConverter

        hex_converter = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION)
        world_x, world_y = hex_converter.hex_to_pixel(target_pos.col, target_pos.row)
        world_y -= 50

        animation_system.create_crit_indicator((world_x, world_y))

    def _get_animation_system(self):
        """Get animation system"""
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def _get_territory_system(self):
        """Get territory system"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None
