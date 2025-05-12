import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    UnitStatsComponent,
    UnitStateComponent,
    UnitSupplyComponent,
    UnitPositionComponent,
    TerrainType,
    UnitType,
    UnitCategory,
    UnitState,
)

from rotk.configs import DAMAGE_CONFIGS


class DamageSystem(System):
    """伤害系统，负责计算和应用战斗伤害"""

    def __init__(self):
        """初始化伤害系统"""
        super().__init__([UnitStatsComponent], priority=31)
        self.unit_system = None
        self.map_manager = None
        
        # 从配置加载伤害相关常量
        self.MIN_DAMAGE = DAMAGE_CONFIGS["MIN_DAMAGE"]
        self.CRITICAL_DAMAGE_MULTIPLIER = DAMAGE_CONFIGS["CRITICAL_DAMAGE_MULTIPLIER"]
        self.CRITICAL_HIT_CHANCE = DAMAGE_CONFIGS["CRITICAL_HIT_CHANCE"]
        self.COUNTER_MATRIX = DAMAGE_CONFIGS["COUNTER_MATRIX"]
        self.TERRAIN_DEFENSE_BONUS = DAMAGE_CONFIGS["TERRAIN_DEFENSE_BONUS"]
        self.MORALE_DAMAGE_FACTOR = DAMAGE_CONFIGS["MORALE_DAMAGE_FACTOR"]
        self.FOOD_SHORTAGE_DAMAGE_PENALTY = DAMAGE_CONFIGS["FOOD_SHORTAGE_DAMAGE_PENALTY"]
        self.DAMAGE_RANDOM_FACTOR = DAMAGE_CONFIGS["DAMAGE_RANDOM_FACTOR"]

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager,
        unit_system,
    ) -> None:
        """初始化伤害系统
        
        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            unit_system: 单位系统
        """
        self.world = world
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.unit_system = unit_system

    def process_damage(self, attacker: int, target: int) -> float:
        """处理一次伤害事件
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
            
        Returns:
            float: 实际造成的伤害值
        """
        # 计算伤害值
        damage, is_critical = self._calculate_damage(attacker, target)
        
        # 应用伤害
        self.apply_damage(target, damage)
        
        # 发布伤害事件
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        
        self.event_manager.publish(
            "COMBAT_HIT",
            Message(
                topic="COMBAT_HIT",
                data_type="combat_event",
                data={
                    "attacker": attacker,
                    "target": target,
                    "attacker_name": attacker_stats.name,
                    "target_name": target_stats.name,
                    "damage": damage,
                    "is_critical": is_critical,
                    "target_health": target_stats.health,
                },
            ),
        )
        
        return damage

    def _calculate_damage(self, attacker: int, target: int) -> tuple:
        """计算伤害值
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
            
        Returns:
            tuple: (伤害值, 是否暴击)
        """
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        attacker_supply = self.world.get_component(attacker, UnitSupplyComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)

        if not all([attacker_stats, target_stats]):
            return 0, False

        # 基础伤害计算
        base_damage = attacker_stats.attack * (1.0 - target_stats.defense / 100.0)
        
        # 考虑单位类型克制关系
        counter_multiplier = self.COUNTER_MATRIX.get(attacker_stats.category, {}).get(
            target_stats.category, 1.0
        )
        base_damage *= counter_multiplier
        
        # 考虑地形防御加成
        if target_pos:
            terrain_type = self.map_manager.get_terrain_at(
                self.world, target_pos.x, target_pos.y
            )
            terrain_defense_bonus = self.TERRAIN_DEFENSE_BONUS.get(terrain_type, 0.0)
            base_damage *= (1.0 - terrain_defense_bonus)
        
        # 考虑士气和补给影响
        morale_factor = 1.0 + (attacker_stats.morale - 50) / 100.0 * self.MORALE_DAMAGE_FACTOR
        base_damage *= morale_factor
        
        if attacker_supply and attacker_supply.food_supply < 30:
            base_damage *= self.FOOD_SHORTAGE_DAMAGE_PENALTY  # 粮食不足降低伤害
        
        # 随机波动
        random_factor = self.DAMAGE_RANDOM_FACTOR["MIN"] + random.random() * (
            self.DAMAGE_RANDOM_FACTOR["MAX"] - self.DAMAGE_RANDOM_FACTOR["MIN"]
        )
        damage = base_damage * random_factor
        
        # 计算暴击
        is_critical = random.random() < self.CRITICAL_HIT_CHANCE
        if is_critical:
            damage *= self.CRITICAL_DAMAGE_MULTIPLIER
        
        # 确保最小伤害
        damage = max(self.MIN_DAMAGE, damage)
        
        return round(damage), is_critical

    def apply_damage(self, target: int, damage: float) -> None:
        """应用伤害到目标单位
        
        Args:
            target: 目标实体ID
            damage: 造成的伤害值
        """
        target_stats = self.world.get_component(target, UnitStatsComponent)
        
        if not target_stats:
            return
        
        # 应用伤害
        target_stats.health -= damage
        
        # 检查单位是否死亡
        if target_stats.health <= 0:
            target_stats.health = 0
            
            # 发布单位死亡事件
            self.event_manager.publish(
                "UNIT_KILLED",
                Message(
                    topic="UNIT_KILLED",
                    data_type="unit_event",
                    data={
                        "entity": target,
                        "unit_name": target_stats.name,
                        "faction_id": target_stats.faction_id,
                    },
                ),
            )
            
            # 清除单位状态
            target_state = self.world.get_component(target, UnitStateComponent)
            if target_state:
                target_state.state = UnitState.DEAD
                target_state.is_engaged = False
                target_state.target_entity = None

    def update(self, world: World, delta_time: float) -> None:
        """更新伤害系统
        
        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 检查单位的健康状态，处理单位的复活或持续伤害效果等
        # 在当前系统中，这部分暂时不需要实现
        pass 