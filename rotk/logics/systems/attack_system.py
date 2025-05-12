import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    MapComponent,
    UnitStatsComponent,
    UnitMovementComponent,
    UnitSupplyComponent,
    UnitStateComponent,
    UnitPositionComponent,
    TerrainType,
    UnitType,
    UnitCategory,
    UnitState,
)

from rotk.configs import ATTACK_CONFIGS


class AttackSystem(System):
    """攻击系统，负责处理单位间的攻击判定和命中计算"""

    def __init__(self):
        """初始化攻击系统"""
        super().__init__([UnitStatsComponent, UnitStateComponent], priority=30)
        self.unit_system = None
        self.map_manager = None
        self.damage_system = None

        # 从配置加载攻击相关常量
        self.BASE_HIT_CHANCE = ATTACK_CONFIGS["BASE_HIT_CHANCE"]
        self.TERRAIN_HIT_MODIFIERS = ATTACK_CONFIGS["TERRAIN_HIT_MODIFIERS"]
        self.FOOD_SHORTAGE_HIT_PENALTY = ATTACK_CONFIGS["FOOD_SHORTAGE_HIT_PENALTY"]
        self.AMMO_SHORTAGE_HIT_PENALTY = ATTACK_CONFIGS["AMMO_SHORTAGE_HIT_PENALTY"]
        self.MORALE_HIT_FACTOR = ATTACK_CONFIGS["MORALE_HIT_FACTOR"]
        self.AUTO_ATTACK_CHANCE = ATTACK_CONFIGS["AUTO_ATTACK_CHANCE"]
        
        # 追踪当前回合的攻击记录
        self.attack_records = []

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager,
        unit_system,
        damage_system,
    ) -> None:
        """初始化攻击系统
        
        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            unit_system: 单位系统
            damage_system: 伤害系统
        """
        self.world = world
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.unit_system = unit_system
        self.damage_system = damage_system

        # 订阅相关事件
        self.event_manager.subscribe("ATTACK_COMMAND", self._handle_attack_command)

    def _handle_attack_command(self, message: Message) -> None:
        """处理攻击命令事件
        
        Args:
            message: 事件消息，包含攻击方和目标信息
        """
        data = message.data
        attacker = data.get("attacker")
        target = data.get("target")

        if attacker is not None and target is not None:
            self.initiate_combat(attacker, target)

    def initiate_combat(self, attacker: int, target: int) -> None:
        """发起战斗
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
        """
        # 检查双方是否还存在且可以战斗
        if not self._can_engage_combat(attacker, target):
            return

        # 设置战斗状态
        attacker_state = self.world.get_component(attacker, UnitStateComponent)
        attacker_state.state = UnitState.ATTACKING
        attacker_state.target_entity = target
        attacker_state.is_engaged = True

        target_state = self.world.get_component(target, UnitStateComponent)
        target_state.state = UnitState.DEFENDING
        target_state.target_entity = attacker
        target_state.is_engaged = True

        # 处理攻击
        self._process_attack(attacker, target)

        # 如果是远程攻击，则不设置目标为交战状态
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        if attacker_stats and attacker_stats.attack_range > 1.0:
            target_state.is_engaged = False
            attacker_state.is_engaged = False

    def _can_engage_combat(self, attacker: int, target: int) -> bool:
        """检查两个单位是否可以进行战斗
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
            
        Returns:
            bool: 是否可以战斗
        """
        # 检查双方是否都存在
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)

        if not attacker_stats or not target_stats:
            return False

        # 检查双方是否都还活着
        if attacker_stats.health <= 0 or target_stats.health <= 0:
            return False

        # 检查是否敌对阵营
        if attacker_stats.faction_id == target_stats.faction_id:
            return False

        # 检查是否在攻击范围内
        attacker_pos = self.world.get_component(attacker, UnitPositionComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)
        
        if not attacker_pos or not target_pos:
            return False

        # 计算距离
        dx = attacker_pos.x - target_pos.x
        dy = attacker_pos.y - target_pos.y
        distance = math.sqrt(dx * dx + dy * dy)

        # 检查是否在攻击范围内
        return distance <= attacker_stats.attack_range

    def _process_attack(self, attacker: int, target: int) -> None:
        """处理攻击过程
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
        """
        # 获取相关组件
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        attacker_supply = self.world.get_component(attacker, UnitSupplyComponent)
        attacker_pos = self.world.get_component(attacker, UnitPositionComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)

        if not all([attacker_stats, target_stats, attacker_pos, target_pos]):
            return

        # 计算命中率
        hit_chance = self._calculate_hit_chance(attacker, target)

        # 判断是否命中
        if random.random() > hit_chance:
            # 未命中
            self.event_manager.publish(
                "COMBAT_MISS",
                Message(
                    topic="COMBAT_MISS",
                    data_type="combat_event",
                    data={
                        "attacker": attacker,
                        "target": target,
                        "attacker_name": attacker_stats.name,
                        "target_name": target_stats.name,
                    },
                ),
            )
            return

        # 命中后，调用伤害系统处理伤害
        self.damage_system.process_damage(attacker, target)

        # 更新补给（如果是远程单位消耗弹药）
        if attacker_supply and attacker_supply.ammo_consumption_rate > 0:
            attacker_supply.ammo_supply -= attacker_supply.ammo_consumption_rate
            if attacker_supply.ammo_supply < 0:
                attacker_supply.ammo_supply = 0

        # 添加攻击记录
        self.attack_records.append(
            {
                "attacker": attacker,
                "target": target,
                "hit": True,
            }
        )

    def _calculate_hit_chance(self, attacker: int, target: int) -> float:
        """计算攻击命中率
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
            
        Returns:
            float: 命中率(0.0-1.0)
        """
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        attacker_supply = self.world.get_component(attacker, UnitSupplyComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)

        base_chance = self.BASE_HIT_CHANCE

        # 考虑攻击方的战斗力和士气
        morale_factor = 1.0 + (attacker_stats.morale - 50) / 100.0 * self.MORALE_HIT_FACTOR
        base_chance *= morale_factor

        # 考虑补给状态
        if attacker_supply:
            supply_factor = 1.0
            if attacker_supply.food_supply < 20:
                supply_factor = 1.0 - self.FOOD_SHORTAGE_HIT_PENALTY["SEVERE"]
            elif attacker_supply.food_supply < 50:
                supply_factor = 1.0 - self.FOOD_SHORTAGE_HIT_PENALTY["MODERATE"]

            # 如果是远程单位，考虑弹药
            if attacker_supply.ammo_consumption_rate > 0:
                if attacker_supply.ammo_supply <= 0:
                    return 0.0  # 没有弹药无法攻击
                elif attacker_supply.ammo_supply < 20:
                    supply_factor *= 1.0 - self.AMMO_SHORTAGE_HIT_PENALTY["SEVERE"]

            base_chance *= supply_factor

        # 考虑地形因素
        if target_pos:
            terrain_type = self.map_manager.get_terrain_at(
                self.world, target_pos.x, target_pos.y
            )
            
            # 从配置获取地形对命中率的修正
            terrain_modifier = self.TERRAIN_HIT_MODIFIERS.get(terrain_type, 0.0)
            base_chance += terrain_modifier
            
            # 获取地形防御加成
            terrain_defense_modifier = self.map_manager.get_defense_bonus(terrain_type)
            base_chance /= (1.0 + terrain_defense_modifier)  # 防御加成降低命中率

        # 确保命中率在合理范围内
        return max(0.1, min(0.95, base_chance))

    def update(self, world: World, delta_time: float) -> None:
        """更新攻击系统
        
        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 清空攻击记录
        self.attack_records = []

        # 处理自动战斗(对于处于交战状态的单位)
        engaged_entities = []

        # 找出所有处于交战状态的单位
        for entity in world.get_entities_with_components(UnitStateComponent):
            state = world.get_component(entity, UnitStateComponent)
            if state.is_engaged and state.target_entity is not None:
                engaged_entities.append(entity)

        # 处理战斗
        for entity in engaged_entities:
            state = world.get_component(entity, UnitStateComponent)
            if state.state == UnitState.ATTACKING and state.target_entity:
                # 检查是否可以继续攻击
                if self._can_engage_combat(entity, state.target_entity):
                    # 自动攻击(概率触发，避免每帧都攻击)
                    if random.random() < self.AUTO_ATTACK_CHANCE:
                        self._process_attack(entity, state.target_entity)
                else:
                    # 目标已不可攻击，清除交战状态
                    state.is_engaged = False
                    state.target_entity = None
                    state.state = UnitState.IDLE 