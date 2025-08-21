"""
战斗系统 - 处理单位战斗（按规则手册v1.2）
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
    """战斗系统 - 按规则手册v1.2实现"""

    def __init__(self):
        super().__init__(priority=300)

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新战斗系统"""
        pass

    def execute_attack(
        self, attacker_entity: int, target_entity: int
    ) -> Optional[Dict[str, Any]]:
        """执行攻击并返回详细战斗结果 - 供LLM接口层调用"""
        # 基础验证（由LLM接口层负责，这里只做最后的保护性检查）
        if not self._validate_attack(attacker_entity, target_entity):
            return None

        # 检查行动力（由LLM接口层负责，这里只做最后的保护性检查）
        action_points = self.world.get_component(attacker_entity, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.ATTACK):
            return None

        # 获取战斗前状态
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

        # 创建战斗投掷组件
        combat_roll = CombatRoll()
        self.world.add_component(attacker_entity, combat_roll)

        # 根据攻击类型确定动画类型
        attack_type = (
            "ranged" if attacker_unit.unit_type == UnitType.ARCHER else "melee"
        )

        # 触发攻击动画
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_attack_animation(
                attacker_entity, target_entity, attack_type
            )

        # 计算地形加成
        attacker_terrain_bonus = self._get_terrain_attack_bonus(
            (attacker_pos.col, attacker_pos.row), attacker_unit.faction
        )
        target_terrain_defense = self._get_terrain_defense_bonus(
            (target_pos.col, target_pos.row), target_unit.faction
        )

        # 1. 命中判定
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
            # 未命中处理
            attacker_faction = attacker_unit.faction.value
            target_faction = target_unit.faction.value
            miss_message = f"{attacker_faction}军攻击{target_faction}军未命中!"
            print(f"❌ {miss_message}")

            battle_result["combat_log"].append(miss_message)
            self._create_miss_display(target_entity)
            self._record_miss_to_systems(attacker_entity, target_entity)
            action_points.consume_ap(ActionType.ATTACK)

            return battle_result

        # 2. 计算基础伤害
        damage = self._calculate_damage(
            attacker_entity,
            target_entity,
            attacker_count,
            target_count,
            attacker_status,
            target_status,
        )

        battle_result["dice_rolls"]["damage_roll"] = damage  # 简化，实际是计算结果

        # 3. 暴击判定
        is_crit = self._roll_crit(combat_roll)
        battle_result["is_critical"] = is_crit

        if is_crit:
            damage = int(damage * 1.5)
            battle_result["dice_rolls"]["crit_roll"] = True
            self._create_crit_display(target_entity)
            battle_result["combat_log"].append("暴击！伤害加倍！")

        battle_result["damage_dealt"] = damage

        # 4. 应用伤害
        old_count = target_count.current_count
        self._apply_damage(target_entity, damage)
        new_count = target_count.current_count

        casualties = old_count - new_count
        battle_result["casualties_inflicted"] = casualties
        battle_result["target_destroyed"] = new_count <= 0

        # 创建攻击特效
        if animation_system:
            from ..utils.hex_utils import HexConverter

            hex_converter = HexConverter(
                GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
            )
            world_x, world_y = hex_converter.hex_to_pixel(
                target_pos.col, target_pos.row
            )

            # 根据攻击类型和暴击选择特效
            if is_crit:
                effect_type = "explosion"
            elif attack_type == "ranged":
                effect_type = "impact"
            else:
                effect_type = "slash"

            animation_system.create_attack_effect((world_x, world_y), effect_type)

        # 添加控制台输出和战斗日志
        attacker_faction = attacker_unit.faction.value
        target_faction = target_unit.faction.value

        if is_crit:
            combat_message = f"{attacker_faction}军暴击{target_faction}军! 伤害:{damage}, 人数:{old_count}->{new_count}"
            print(f"💥 {combat_message}")
        else:
            combat_message = f"{attacker_faction}军攻击{target_faction}军! 伤害:{damage}, 人数:{old_count}->{new_count}"
            print(f"⚔️ {combat_message}")

        battle_result["combat_log"].append(combat_message)

        # 5. 消耗行动力
        action_points.consume_ap(ActionType.ATTACK)
        # attacker_combat.has_attacked = True  # 移除单次攻击限制，允许多次攻击

        # 6. 处理特殊效果
        self._handle_combat_effects(attacker_entity, target_entity)

        # 7. 记录统计和事件
        result = "kill" if target_count.current_count <= 0 else "damage"
        self._record_combat_to_systems(attacker_entity, target_entity, damage, result)

        # 发送战斗事件
        EBS.publish(BattleEvent(attacker_entity, target_entity, damage))

        # 8. 检查单位死亡
        if target_count.current_count <= 0:
            self._handle_unit_death(target_entity, attacker_entity)
            battle_result["combat_log"].append(f"{target_faction}军单位被摧毁！")

        # 9. 填充详细战斗结果
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

        return battle_result

    def attack(self, attacker_entity: int, target_entity: int) -> bool:
        """执行攻击（完整规则实现）"""
        # 基础验证
        if not self._validate_attack(attacker_entity, target_entity):
            return False

        # 检查行动力
        action_points = self.world.get_component(attacker_entity, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.ATTACK):
            return False

        # 获取组件
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_count = self.world.get_component(attacker_entity, UnitCount)
        attacker_status = self.world.get_component(attacker_entity, UnitStatus)
        attacker_unit = self.world.get_component(attacker_entity, Unit)

        target_count = self.world.get_component(target_entity, UnitCount)
        target_status = self.world.get_component(target_entity, UnitStatus)
        target_unit = self.world.get_component(target_entity, Unit)

        # 创建战斗投掷组件
        combat_roll = CombatRoll()
        self.world.add_component(attacker_entity, combat_roll)

        # 根据攻击类型确定动画类型
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        attack_type = (
            "ranged" if attacker_unit.unit_type == UnitType.ARCHER else "melee"
        )

        # 触发攻击动画
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_attack_animation(
                attacker_entity, target_entity, attack_type
            )

        # 1. 命中判定
        if not self._roll_hit(combat_roll, attacker_pos, target_pos):
            # 添加未命中的控制台输出
            attacker_faction = attacker_unit.faction.value
            target_faction = target_unit.faction.value
            print(f"❌ {attacker_faction}军攻击{target_faction}军未命中!")

            self._create_miss_display(target_entity)
            # 记录未命中到BattleLog
            self._record_miss_to_systems(attacker_entity, target_entity)
            action_points.consume_ap(ActionType.ATTACK)
            return False

        # 2. 计算基础伤害
        damage = self._calculate_damage(
            attacker_entity,
            target_entity,
            attacker_count,
            target_count,
            attacker_status,
            target_status,
        )

        # 3. 暴击判定
        is_crit = False
        if self._roll_crit(combat_roll):
            damage = int(damage * 1.5)
            is_crit = True
            self._create_crit_display(target_entity)

        # 4. 应用伤害
        old_count = target_count.current_count
        self._apply_damage(target_entity, damage)
        new_count = target_count.current_count

        # 创建攻击特效
        if animation_system:
            from ..utils.hex_utils import HexConverter

            hex_converter = HexConverter(
                GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
            )
            world_x, world_y = hex_converter.hex_to_pixel(
                target_pos.col, target_pos.row
            )

            # 根据攻击类型和暴击选择特效
            if is_crit:
                effect_type = "explosion"
            elif attack_type == "ranged":
                effect_type = "impact"
            else:
                effect_type = "slash"

            animation_system.create_attack_effect((world_x, world_y), effect_type)

        # 添加控制台输出
        attacker_faction = attacker_unit.faction.value
        target_faction = target_unit.faction.value
        if is_crit:
            print(
                f"💥 {attacker_faction}军暴击{target_faction}军! 伤害:{damage}, 人数:{old_count}->{new_count}"
            )
        else:
            print(
                f"⚔️ {attacker_faction}军攻击{target_faction}军! 伤害:{damage}, 人数:{old_count}->{new_count}"
            )

        # 5. 消耗行动力
        action_points.consume_ap(ActionType.ATTACK)
        # attacker_combat.has_attacked = True  # 移除单次攻击限制，允许多次攻击

        # 6. 处理特殊效果
        self._handle_combat_effects(attacker_entity, target_entity)

        # 7. 记录统计和事件
        result = "kill" if target_count.current_count <= 0 else "damage"
        self._record_combat_to_systems(attacker_entity, target_entity, damage, result)

        # 发送战斗事件
        EBS.publish(BattleEvent(attacker_entity, target_entity, damage))

        # 8. 检查单位死亡
        if target_count.current_count <= 0:
            self._handle_unit_death(target_entity, attacker_entity)

        return True

    def _validate_attack(self, attacker_entity: int, target_entity: int) -> bool:
        """验证攻击是否有效"""
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_count = self.world.get_component(attacker_entity, UnitCount)
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        if not all(
            [
                attacker_pos,
                target_pos,
                attacker_combat,
                attacker_count,
                attacker_unit,
                target_unit,
            ]
        ):
            return False

        # 检查人数要求（N ≤ 10%无法主动攻击）
        if attacker_count.ratio <= 0.1:
            return False

        # 注释掉攻击次数限制检查 - 允许多次攻击（只要有足够的行动点）
        # if attacker_combat.has_attacked:
        #     return False

        # 检查攻击范围
        distance = HexMath.hex_distance(
            (attacker_pos.col, attacker_pos.row), (target_pos.col, target_pos.row)
        )
        if distance > attacker_combat.attack_range:
            return False

        # 检查是否是敌方单位
        if attacker_unit.faction == target_unit.faction:
            return False

        return True

    def _roll_hit(
        self,
        combat_roll: CombatRoll,
        attacker_pos: HexPosition,
        target_pos: HexPosition,
    ) -> bool:
        """投掷命中（1D6 ≥ 2）"""
        # 检查地形影响（森林-20%命中率）
        target_terrain = self._get_terrain_at_position((target_pos.col, target_pos.row))
        if target_terrain == TerrainType.FOREST:
            combat_roll.apply_forest_penalty()

        return combat_roll.roll_hit()

    def _roll_crit(self, combat_roll: CombatRoll) -> bool:
        """投掷暴击（1D6 ≥ 6）"""
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
        """计算伤害（按动态攻防公式）"""
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        target_combat = self.world.get_component(target_entity, Combat)
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)

        # 获取地形系数
        attacker_terrain_coeff = self._get_terrain_coefficient(
            (attacker_pos.col, attacker_pos.row), attacker_unit.unit_type
        )
        target_terrain_coeff = self._get_terrain_coefficient(
            (target_pos.col, target_pos.row), target_unit.unit_type
        )

        # 计算有效攻防
        effective_attack, _ = attacker_combat.get_effective_stats(
            attacker_count, attacker_status, attacker_terrain_coeff
        )
        _, effective_defense = target_combat.get_effective_stats(
            target_count, target_status, target_terrain_coeff
        )

        # 应用攻击加成（地形+领土）
        terrain_attack_bonus = self._get_terrain_attack_bonus(
            (attacker_pos.col, attacker_pos.row), attacker_unit.faction
        )
        effective_attack += terrain_attack_bonus

        # 应用防御特殊规则
        effective_defense = self._apply_defense_bonuses(
            target_entity, effective_defense
        )

        # 基础伤害计算
        base_damage = max(1, effective_attack - int(effective_defense * 0.5))

        # 人数影响：最终伤害再乘 (N攻 / N守)^0.5
        count_ratio = (
            1.0  # (attacker_count.current_count / target_count.current_count) ** 0.5
        )
        damage = int(base_damage * count_ratio)

        # 应用特殊修正（冲锋、技能等）
        damage = self._apply_special_modifiers(attacker_entity, damage)

        return max(1, damage)

    def _apply_defense_bonuses(self, target_entity: int, base_defense: int) -> int:
        """应用防御加成"""
        target_unit = self.world.get_component(target_entity, Unit)
        target_pos = self.world.get_component(target_entity, HexPosition)

        defense = base_defense

        # 步兵盾墙：被远程攻击时防御再+1
        if target_unit.unit_type == UnitType.INFANTRY:
            # 这里需要判断攻击者是否为远程，简化处理
            defense += 1

        # 地形防御修正
        terrain_defense = self._get_terrain_defense_bonus(
            (target_pos.col, target_pos.row), target_unit.faction
        )
        defense += terrain_defense

        return defense

    def _apply_special_modifiers(self, attacker_entity: int, base_damage: int) -> int:
        """应用特殊修正"""
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        attacker_status = self.world.get_component(attacker_entity, UnitStatus)

        damage = base_damage

        # 骑兵冲锋：首回合攻击伤害×1.5
        if (
            attacker_unit.unit_type == UnitType.CAVALRY
            and attacker_status.charge_stacks > 0
        ):
            damage = int(damage * 1.5)
            # 清除冲锋状态
            attacker_status.charge_stacks = 0

        return damage

    def _apply_damage(self, target_entity: int, damage: int):
        """应用伤害到单位人数"""
        target_count = self.world.get_component(target_entity, UnitCount)

        # 伤害转换为人数损失（简化：1点伤害 = 1人损失）
        casualties = min(damage, target_count.current_count)
        target_count.current_count -= casualties

        # 创建伤害显示
        self._create_damage_display(target_entity, casualties)

    def _handle_combat_effects(self, attacker_entity: int, target_entity: int):
        """处理战斗后效果"""
        # 更新状态为战斗状态
        for entity in [attacker_entity, target_entity]:
            status = self.world.get_component(entity, UnitStatus)
            if status:
                status.current_status = UnitState.NORMAL
                status.status_duration = 0

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """获取位置的地形类型"""
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
        """获取地形系数"""
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
        """获取地形攻击加成 - 包含基础地形加成和领土控制加成"""
        # 1. 基础地形攻击加成（来自地形类型）
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        base_attack_bonus = terrain_effect.attack_bonus if terrain_effect else 0.0

        # 2. 领土控制加成（如果存在领土系统）
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
        """获取地形防御加成 - 包含基础地形加成和领土控制加成"""
        # 1. 基础地形防御加成（来自地形类型）
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        base_defense_bonus = terrain_effect.defense_bonus if terrain_effect else 0.0

        # 2. 领土控制加成（如果存在领土系统且提供了阵营信息）
        territory_bonus = 0.0
        if faction:
            territory_system = self._get_territory_system()
            if territory_system:
                # 假设领土系统也有防御加成方法，如果没有则只使用基础加成
                if hasattr(territory_system, "get_territory_defense_bonus"):
                    territory_bonus = (
                        territory_system.get_territory_defense_bonus(position, faction)
                        / 10.0
                    )

        return base_defense_bonus + territory_bonus

    def _handle_unit_death(self, entity: int, killer_entity: int = None):
        """处理单位死亡"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # 添加死亡控制台输出
        pos = self.world.get_component(entity, HexPosition)
        pos_str = f"@({pos.col},{pos.row})" if pos else ""
        if killer_entity:
            killer_unit = self.world.get_component(killer_entity, Unit)
            killer_faction = killer_unit.faction.value if killer_unit else "未知"
            print(f"💀 {unit.faction.value}军单位{pos_str}被{killer_faction}军击杀!")
        else:
            print(f"💀 {unit.faction.value}军单位{pos_str}死亡!")

        # 记录死亡到统计系统
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_death_action(entity, killer_entity)

        # 更新统计
        stats = self.world.get_singleton_component(GameStats)
        if stats and unit.faction in stats.faction_stats:
            stats.faction_stats[unit.faction]["losses"] += 1

        # 从玩家的单位列表中移除
        for player_entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(player_entity, Player)
            if player and player.faction == unit.faction:
                player.units.discard(entity)
                break

        # 清除地块占用
        position = self.world.get_component(entity, HexPosition)
        if position:
            map_data = self.world.get_singleton_component(MapData)
            if map_data:
                tile_entity = map_data.tiles.get((position.col, position.row))
                if tile_entity:
                    tile = self.world.get_component(tile_entity, Tile)
                    if tile and tile.occupied_by == entity:
                        tile.occupied_by = None

                # 发送死亡事件
        EBS.publish(UnitDeathEvent(entity, unit.faction))

        # 删除实体
        self.world.destroy_entity(entity)

    def _record_combat_stats(
        self, attacker_entity: int, target_entity: int, damage: int
    ):
        """记录战斗统计"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        if not attacker_unit or not target_unit:
            return

        # 初始化统计数据
        for faction in [attacker_unit.faction, target_unit.faction]:
            if faction not in stats.faction_stats:
                stats.faction_stats[faction] = {
                    "kills": 0,
                    "losses": 0,
                    "damage_dealt": 0,
                    "damage_taken": 0,
                }

        # 记录伤害
        stats.faction_stats[attacker_unit.faction]["damage_dealt"] += damage
        stats.faction_stats[target_unit.faction]["damage_taken"] += damage

        # 记录战斗历史
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
        """将战斗记录到各个系统（统计系统、BattleLog等）"""
        # 首先调用统计系统记录战斗
        statistics_system = self._get_statistics_system()
        if statistics_system:
            try:
                statistics_system.record_combat_action(
                    attacker_entity, target_entity, damage, result
                )
            except Exception as e:
                print(f"统计系统记录战斗失败: {e}")
                # 如果统计系统失败，使用备用方法
                self._record_combat_stats(attacker_entity, target_entity, damage)
        else:
            # 如果没有统计系统，使用备用方法
            self._record_combat_stats(attacker_entity, target_entity, damage)

    def _get_statistics_system(self):
        """获取统计系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _record_miss_to_systems(self, attacker_entity: int, target_entity: int):
        """记录未命中到系统"""
        # 直接向BattleLog添加未命中记录
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            attacker_unit = self.world.get_component(attacker_entity, Unit)
            target_unit = self.world.get_component(target_entity, Unit)

            if attacker_unit and target_unit:
                message = f"{attacker_unit.faction.value}对{target_unit.faction.value}的攻击未命中"
                battle_log.add_entry(
                    message, "combat", attacker_unit.faction.value, (128, 128, 128)
                )

    def _create_damage_display(self, target_entity: int, damage: int):
        """创建伤害数字显示"""
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
        """创建未命中显示"""
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
        """创建暴击显示"""
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
        """获取动画系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def _get_territory_system(self):
        """获取领土系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None
