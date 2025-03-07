import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
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


class CombatSystem(System):
    """战斗系统，处理单位之间的战斗、伤害计算和战斗效果"""

    def __init__(self):
        super().__init__([UnitStatsComponent, UnitStateComponent], priority=30)
        self.faction_system = None
        self.unit_system = None
        self.map_manager = None

        # 战斗相关常量
        self.BASE_HIT_CHANCE = 0.7  # 基础命中率
        self.CRITICAL_CHANCE = 0.1  # 暴击率
        self.CRITICAL_DAMAGE = 1.5  # 暴击伤害倍率
        self.MORALE_IMPACT = 0.3  # 士气对战斗力的影响系数
        self.SUPPLY_IMPACT = 0.2  # 补给对战斗力的影响系数
        self.TERRAIN_DEFENSE_BONUS = {  # 地形防御加成
            TerrainType.FOREST: 1.2,
            TerrainType.MOUNTAIN: 1.5,
            TerrainType.HILL: 1.3,
            TerrainType.RIVER: 1.1,
            TerrainType.PLAINS: 1.0,
            TerrainType.SWAMP: 0.9,
            TerrainType.DESERT: 0.9,
        }

        # 单位类型相克关系表 {攻击方: {防御方: 伤害倍率}}
        self.COUNTER_MATRIX = {
            UnitType.SPEAR_INFANTRY: {
                UnitType.HEAVY_CAVALRY: 1.5,
                UnitType.SCOUT_CAVALRY: 1.3,
            },
            UnitType.HEAVY_CAVALRY: {
                UnitType.SHIELD_INFANTRY: 1.4,
                UnitType.ARCHER: 1.5,
                UnitType.CROSSBOWMAN: 1.4,
            },
            UnitType.ARCHER: {
                UnitType.SPEAR_INFANTRY: 1.3,
                UnitType.SHIELD_INFANTRY: 1.2,
            },
            UnitType.CROSSBOWMAN: {
                UnitType.SHIELD_INFANTRY: 1.4,
                UnitType.HEAVY_CAVALRY: 1.2,
            },
            UnitType.SCOUT_CAVALRY: {UnitType.ARCHER: 1.3, UnitType.CROSSBOWMAN: 1.4},
            UnitType.MOUNTED_ARCHER: {
                UnitType.SPEAR_INFANTRY: 1.2,
                UnitType.SHIELD_INFANTRY: 1.1,
            },
        }

        # 追踪当前回合的战斗记录
        self.combat_records = []

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager,
        faction_system,
        unit_system,
    ) -> None:
        """初始化战斗系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            faction_system: 阵营系统
            unit_system: 单位系统
        """
        self.world = world
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.faction_system = faction_system
        self.unit_system = unit_system

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
        # if not self.are_factions_hostile(
        #     attacker_stats.faction_id, target_stats.faction_id
        # ):
        if attacker_stats.faction_id == target_stats.faction_id:
            return False

        # 检查是否在攻击范围内
        attacker_pos = self.world.get_component(attacker, UnitPositionComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)

        if not attacker_pos or not target_pos or not attacker_stats:
            return False

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

        # 计算伤害
        damage, is_critical = self._calculate_damage(attacker, target)

        # 应用伤害
        self.apply_damage(target, damage)

        # 更新补给（如果是远程单位消耗弹药）
        if attacker_supply and attacker_supply.ammo_consumption_rate > 0:
            attacker_supply.ammo_supply -= attacker_supply.ammo_consumption_rate
            if attacker_supply.ammo_supply < 0:
                attacker_supply.ammo_supply = 0

        # 计算士气影响
        self._calculate_morale_impact(attacker, target, damage, is_critical)

        # 添加战斗记录
        self.combat_records.append(
            {
                "attacker": attacker,
                "target": target,
                "damage": damage,
                "is_critical": is_critical,
            }
        )

        # 发布战斗事件
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
                    "target_remaining_health": target_stats.health,
                },
            ),
        )

        # 检查目标是否死亡
        # if target_stats.health <= 0:
        # 死亡逻辑在unit_system.apply_damage中处理
        # 这里处理额外的战斗经验奖励
        # experience = max(10, target_stats.level * 20)  # 基于目标等级的经验奖励
        # self.unit_system.add_experience(attacker, experience)

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
        morale_factor = 1.0 + (attacker_stats.morale - 50) / 100.0 * self.MORALE_IMPACT
        base_chance *= morale_factor

        # 考虑补给状态
        if attacker_supply:
            supply_factor = 1.0
            if attacker_supply.food_supply < 20:
                supply_factor = 0.7  # 粮食不足严重影响命中率
            elif attacker_supply.food_supply < 50:
                supply_factor = 0.9  # 粮食较少轻微影响命中率

            # 如果是远程单位，考虑弹药
            if attacker_supply.ammo_consumption_rate > 0:
                if attacker_supply.ammo_supply <= 0:
                    return 0.0  # 没有弹药无法攻击
                elif attacker_supply.ammo_supply < 20:
                    supply_factor *= 0.8  # 弹药不足影响命中率

            base_chance *= supply_factor

        # 考虑地形因素
        if target_pos:
            terrain_type = self.map_manager.get_terrain_at(
                self.world, target_pos.x, target_pos.y
            )
            terrain_factor = self.TERRAIN_DEFENSE_BONUS.get(terrain_type, 1.0)
            base_chance /= terrain_factor

        # 确保命中率在合理范围内
        return max(0.1, min(0.95, base_chance))

    def _calculate_damage(self, attacker: int, target: int) -> tuple:
        """计算攻击伤害

        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID

        Returns:
            tuple: (伤害值, 是否暴击)
        """
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        target_pos = self.world.get_component(target, UnitPositionComponent)

        # 基础伤害
        base_damage = attacker_stats.attack

        # 考虑防御
        defense_factor = 100 / (100 + target_stats.defense)
        damage = base_damage * defense_factor

        # 单位类型相克关系
        counter_bonus = 1.0
        if attacker_stats.unit_type in self.COUNTER_MATRIX:
            counter_bonus = self.COUNTER_MATRIX[attacker_stats.unit_type].get(
                target_stats.unit_type, 1.0
            )
        damage *= counter_bonus

        # 地形防御加成
        if target_pos:
            terrain = self.map_manager.get_terrain_at(
                self.world, target_pos.x, target_pos.y
            )
            terrain_defense = self.TERRAIN_DEFENSE_BONUS.get(terrain, 1.0)
            damage /= terrain_defense

        # 士气影响
        attacker_morale_factor = (
            1.0 + (attacker_stats.morale - 50) / 100.0 * self.MORALE_IMPACT
        )
        target_morale_factor = (
            1.0 - (target_stats.morale - 50) / 100.0 * self.MORALE_IMPACT
        )
        damage *= attacker_morale_factor * target_morale_factor

        # 随机波动(±10%)
        random_factor = random.uniform(0.9, 1.1)
        damage *= random_factor

        # 检查暴击
        is_critical = random.random() < self.CRITICAL_CHANCE
        if is_critical:
            damage *= self.CRITICAL_DAMAGE

        # 确保最小伤害
        return max(1.0, damage), is_critical

    def apply_damage(self, unit_entity: int, damage: float) -> None:
        """对单位应用伤害"""
        stats = self.world.get_component(unit_entity, UnitStatsComponent)
        if not stats:
            return
        stats.health = max(0, stats.health - damage)
        if stats.health <= 0:
            state = self.world.get_component(unit_entity, UnitStateComponent)
            if state:
                state.state = UnitState.DEAD
            self.event_manager.publish(
                "UNIT_KILLED",
                Message(
                    topic="UNIT_KILLED",
                    data_type="combat_event",
                    data={
                        "unit_entity": unit_entity,
                        "unit_name": stats.name,
                        "faction_id": stats.faction_id,
                    },
                ),
            )
            self.world.remove_entity(unit_entity)

    def _calculate_morale_impact(
        self, attacker: int, target: int, damage: float, is_critical: bool
    ) -> None:
        """计算战斗对士气的影响"""
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)

        if not attacker_stats or not target_stats or target_stats.max_health <= 0:
            return  # 防止除零错误

        # 基础士气影响
        attacker_morale_gain = 1.0
        target_morale_loss = 2.0

        # 暴击带来额外士气波动
        if is_critical:
            attacker_morale_gain += 2.0
            target_morale_loss += 3.0

        # 根据伤害比例调整士气损失，避免除零错误
        damage_ratio = damage / max(0.1, target_stats.max_health)  # 使用max防止除零
        target_morale_loss += damage_ratio * 20.0  # 最多额外损失20点士气

        # 应用士气变化
        attacker_stats.morale = min(100, attacker_stats.morale + attacker_morale_gain)
        target_stats.morale = max(0, target_stats.morale - target_morale_loss)

        # 检查是否士气崩溃
        if target_stats.morale < 20:
            # 有机会溃逃
            rout_chance = (20 - target_stats.morale) / 20.0
            if random.random() < rout_chance:
                target_state = self.world.get_component(target, UnitStateComponent)
                if target_state:
                    target_state.is_routed = True
                    target_state.state = UnitState.ROUTED

                    # 发布溃逃事件
                    self.event_manager.publish(
                        "UNIT_ROUTED",
                        Message(
                            topic="UNIT_ROUTED",
                            data_type="combat_event",
                            data={
                                "unit_entity": target,
                                "unit_name": target_stats.name,
                            },
                        ),
                    )

    def update(self, world: World, delta_time: float) -> None:
        """更新战斗系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 清空战斗记录
        self.combat_records = []

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
                    # 攻击频率可以基于单位类型等因素调整
                    if random.random() < 0.1:  # 平均每10帧攻击一次
                        self._process_attack(entity, state.target_entity)
                else:
                    # 目标已不可攻击，清除交战状态
                    state.is_engaged = False
                    state.target_entity = None
                    state.state = UnitState.IDLE
