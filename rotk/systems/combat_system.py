"""
战斗系统 - 处理单位战斗
"""

import random
from typing import Tuple
from framework_v2 import System, World
from framework_v2.engine.events import EBS
from ..components import (
    HexPosition,
    Combat,
    Health,
    Unit,
    Player,
    MapData,
    Terrain,
    Tile,
    GameStats,
    GameState,
)
from ..prefabs.config import GameConfig, TerrainType
from ..utils.hex_utils import HexMath
from ..events import BattleEvent, UnitDeathEvent


class CombatSystem(System):
    """战斗系统 - 处理单位战斗"""

    def __init__(self):
        super().__init__(required_components={HexPosition, Combat, Health, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        """订阅事件"""
        # 目前没有需要订阅的事件
        pass

    def update(self, delta_time: float) -> None:
        """更新战斗系统"""
        # 目前没有需要在每帧更新的逻辑
        pass

    def attack(self, attacker_entity: int, target_entity: int) -> bool:
        """执行攻击"""
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_unit = self.world.get_component(attacker_entity, Unit)

        target_pos = self.world.get_component(target_entity, HexPosition)
        target_health = self.world.get_component(target_entity, Health)
        target_unit = self.world.get_component(target_entity, Unit)

        if not all(
            [
                attacker_pos,
                attacker_combat,
                attacker_unit,
                target_pos,
                target_health,
                target_unit,
            ]
        ):
            return False

        # 检查是否已经攻击过
        if attacker_combat.has_attacked:
            return False

        # 检查攻击范围
        distance = HexMath.hex_distance(
            (attacker_pos.col, attacker_pos.row), (target_pos.col, target_pos.row)
        )
        if distance > attacker_combat.attack_range:
            return False

        # 检查是否是敌方单位
        if attacker_unit.faction == target_unit.faction:
            return False

        # 计算伤害
        damage = self._calculate_damage(attacker_entity, target_entity)

        # 应用伤害
        target_health.current = max(0, target_health.current - damage)
        attacker_combat.has_attacked = True

        # 记录战斗统计
        self._record_battle_stats(attacker_entity, target_entity, damage)

        # 发送战斗事件
        EBS.publish(BattleEvent(attacker_entity, target_entity, damage))

        # 检查单位是否死亡
        if target_health.current <= 0:
            self._handle_unit_death(target_entity)

        return True

    def _calculate_damage(self, attacker_entity: int, target_entity: int) -> int:
        """计算伤害值"""
        attacker_combat = self.world.get_component(attacker_entity, Combat)
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)

        base_attack = attacker_combat.attack

        # 获取攻击者地形加成
        attacker_terrain_bonus = self._get_terrain_bonus(
            (attacker_pos.col, attacker_pos.row), "attack"
        )

        # 获取防御者地形加成
        target_terrain_bonus = self._get_terrain_bonus(
            (target_pos.col, target_pos.row), "defense"
        )

        # 计算最终伤害
        attack_value = base_attack * (1 + attacker_terrain_bonus)
        defense_value = self.world.get_component(target_entity, Combat).defense * (
            1 + target_terrain_bonus
        )

        damage = max(1, int(attack_value - defense_value * 0.5))

        # 添加随机性
        damage = int(damage * random.uniform(0.8, 1.2))

        return damage

    def _get_terrain_bonus(self, position: Tuple[int, int], bonus_type: str) -> float:
        """获取地形加成"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0.0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0.0

        terrain = self.world.get_component(tile_entity, Terrain)
        if not terrain:
            return 0.0

        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain.terrain_type)
        if not terrain_effect:
            return 0.0

        if bonus_type == "attack":
            return terrain_effect.attack_bonus
        elif bonus_type == "defense":
            return terrain_effect.defense_bonus

        return 0.0

    def _record_battle_stats(
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
        if attacker_unit.faction not in stats.faction_stats:
            stats.faction_stats[attacker_unit.faction] = {
                "kills": 0,
                "losses": 0,
                "damage_dealt": 0,
                "damage_taken": 0,
            }

        if target_unit.faction not in stats.faction_stats:
            stats.faction_stats[target_unit.faction] = {
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

    def _handle_unit_death(self, entity: int):
        """处理单位死亡"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

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

        # 删除实体
        self.world.destroy_entity(entity)

        # 发送单位死亡事件
        EBS.publish(UnitDeathEvent(entity, unit.faction))
