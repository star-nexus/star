import random
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    UnitStatsComponent,
    UnitStateComponent,
    UnitPositionComponent,
    UnitState,
)

from rotk.configs import COMBAT_EFFECTS_CONFIGS


class CombatEffectsSystem(System):
    """战斗效果系统，负责处理战斗产生的各种效果，如士气变化、溃逃等"""

    def __init__(self):
        """初始化战斗效果系统"""
        super().__init__([UnitStatsComponent, UnitStateComponent], priority=32)
        self.unit_system = None
        
        # 从配置加载战斗效果相关常量
        self.MORALE_RECOVERY_RATE = COMBAT_EFFECTS_CONFIGS["MORALE_RECOVERY_RATE"]
        self.ROUTING_THRESHOLD = COMBAT_EFFECTS_CONFIGS["ROUTING_THRESHOLD"]
        self.ROUTING_CHECK_CHANCE = COMBAT_EFFECTS_CONFIGS["ROUTING_CHECK_CHANCE"]
        self.MIN_DAMAGE_MORALE_IMPACT = COMBAT_EFFECTS_CONFIGS["MIN_DAMAGE_MORALE_IMPACT"]
        self.CRITICAL_HIT_MORALE_PENALTY = COMBAT_EFFECTS_CONFIGS["CRITICAL_HIT_MORALE_PENALTY"]
        self.KILL_MORALE_BONUS = COMBAT_EFFECTS_CONFIGS["KILL_MORALE_BONUS"]
        self.ROUTING_RECOVERY_THRESHOLD = COMBAT_EFFECTS_CONFIGS["ROUTING_RECOVERY_THRESHOLD"]
        self.DAMAGE_DEALT_MORALE_FACTOR = COMBAT_EFFECTS_CONFIGS["DAMAGE_DEALT_MORALE_FACTOR"]
        self.DAMAGE_TAKEN_MORALE_FACTOR = COMBAT_EFFECTS_CONFIGS["DAMAGE_TAKEN_MORALE_FACTOR"]
        self.CRITICAL_HIT_ATTACKER_MORALE_BONUS = COMBAT_EFFECTS_CONFIGS["CRITICAL_HIT_ATTACKER_MORALE_BONUS"]
        self.LOW_HEALTH_MORALE_PENALTY = COMBAT_EFFECTS_CONFIGS["LOW_HEALTH_MORALE_PENALTY"]
        self.ALLY_DEATH_MORALE_PENALTY = COMBAT_EFFECTS_CONFIGS["ALLY_DEATH_MORALE_PENALTY"]
        self.ENEMY_DEATH_MORALE_BONUS = COMBAT_EFFECTS_CONFIGS["ENEMY_DEATH_MORALE_BONUS"]
        self.MORALE_EFFECT_RADIUS = COMBAT_EFFECTS_CONFIGS["MORALE_EFFECT_RADIUS"]

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        unit_system,
    ) -> None:
        """初始化战斗效果系统
        
        Args:
            world: 游戏世界
            event_manager: 事件管理器
            unit_system: 单位系统
        """
        self.world = world
        self.event_manager = event_manager
        self.unit_system = unit_system
        
        # 订阅相关事件
        self.event_manager.subscribe("COMBAT_HIT", lambda message: self._handle_combat_hit(world, message))
        self.event_manager.subscribe("UNIT_KILLED", lambda message: self._handle_unit_killed(world, message))

    def _handle_combat_hit(self, world: World, message: Message) -> None:
        """处理战斗命中事件
        
        Args:
            message: 事件消息，包含攻击信息
        """
        data = message.data
        attacker = data.get("attacker")
        target = data.get("target")
        damage = data.get("damage", 0)
        is_critical = data.get("is_critical", False)
        target_health = data.get("target_health", 0)
        
        if attacker is not None and target is not None:
            # 计算士气影响
            self._calculate_morale_impact(attacker, target, damage, is_critical, target_health)
            
            # 检查是否触发溃逃
            if target_health > 0:  # 只有单位还活着才检查溃逃
                self._check_routing(target, damage, is_critical)

    def _handle_unit_killed(self, world: World, message: Message) -> None:
        """处理单位死亡事件
        
        Args:
            message: 事件消息，包含死亡单位信息
        """
        data = message.data
        killed_entity = data.get("entity")
        killed_faction = data.get("faction_id")
        
        # 为周围友军降低士气
        self._apply_nearby_morale_penalty(killed_entity, killed_faction, self.ALLY_DEATH_MORALE_PENALTY, self.MORALE_EFFECT_RADIUS)
        
        # 为周围敌军提升士气
        for faction_id in range(1, 10):  # 假设有10个阵营
            if faction_id != killed_faction:
                self._apply_nearby_morale_bonus(killed_entity, faction_id, self.ENEMY_DEATH_MORALE_BONUS, self.MORALE_EFFECT_RADIUS)
        # world.remove_entity(killed_entity)

    def _calculate_morale_impact(
        self, attacker: int, target: int, damage: float, is_critical: bool, target_health: float
    ) -> None:
        """计算战斗对士气的影响
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
            damage: 造成的伤害
            is_critical: 是否暴击
            target_health: 目标剩余生命值
        """
        attacker_stats = self.world.get_component(attacker, UnitStatsComponent)
        target_stats = self.world.get_component(target, UnitStatsComponent)
        
        if not attacker_stats or not target_stats:
            return
            
        # 计算基础士气影响
        # 受到伤害降低士气，造成伤害提升士气
        attacker_morale_gain = damage / attacker_stats.max_health * self.DAMAGE_DEALT_MORALE_FACTOR
        target_morale_loss = damage / target_stats.max_health * self.DAMAGE_TAKEN_MORALE_FACTOR
        
        # 暴击额外影响
        if is_critical:
            attacker_morale_gain += self.CRITICAL_HIT_ATTACKER_MORALE_BONUS
            target_morale_loss += self.CRITICAL_HIT_MORALE_PENALTY
            
        # 如果目标生命值很低，额外降低士气
        if target_health > 0 and target_health / target_stats.max_health < 0.3:
            target_morale_loss += self.LOW_HEALTH_MORALE_PENALTY
            
        # 应用士气变化
        attacker_stats.morale = min(100, attacker_stats.morale + attacker_morale_gain)
        target_stats.morale = max(0, target_stats.morale - target_morale_loss)

    def _check_routing(self, entity: int, damage: float, is_critical: bool) -> None:
        """检查单位是否溃逃
        
        Args:
            entity: 单位实体ID
            damage: 受到的伤害
            is_critical: 是否受到暴击
        """
        stats = self.world.get_component(entity, UnitStatsComponent)
        state = self.world.get_component(entity, UnitStateComponent)
        
        if not stats or not state:
            return
            
        # 只有当单位士气低于阈值且不是溃逃状态时才检查
        if stats.morale < self.ROUTING_THRESHOLD and state.state != UnitState.ROUTING:
            # 伤害越大，越可能溃逃
            routing_chance = self.ROUTING_CHECK_CHANCE
            
            # 暴击增加溃逃几率
            if is_critical:
                routing_chance *= 1.5
                
            # 生命值低增加溃逃几率
            health_ratio = stats.health / stats.max_health
            if health_ratio < 0.3:
                routing_chance *= 1.5
                
            # 随机检查是否溃逃
            if random.random() < routing_chance:
                # 设置溃逃状态
                state.state = UnitState.ROUTING
                state.is_engaged = False
                state.target_entity = None
                
                # 发布溃逃事件
                self.event_manager.publish(
                    Message(
                        topic="UNIT_ROUTING",
                        data_type="unit_event",
                        data={
                            "entity": entity,
                            "unit_name": stats.name,
                            "faction_id": stats.faction_id,
                        },
                    ),
                )

    def _apply_nearby_morale_penalty(
        self, center_entity: int, faction_id: int, morale_loss: float, radius: float
    ) -> None:
        """对周围同一阵营的单位应用士气惩罚
        
        Args:
            center_entity: 中心单位实体ID
            faction_id: 阵营ID
            morale_loss: 士气损失值
            radius: 影响半径
        """
        center_pos = self.world.get_component(center_entity, UnitPositionComponent)
        if not center_pos:
            return
            
        # 获取所有同阵营单位
        for entity in self.world.get_entities_with_components(UnitStatsComponent, UnitPositionComponent):
            if entity == center_entity:
                continue
                
            stats = self.world.get_component(entity, UnitStatsComponent)
            pos = self.world.get_component(entity, UnitPositionComponent)
            
            # 检查阵营
            if stats.faction_id != faction_id:
                continue
                
            # 计算距离
            dx = center_pos.x - pos.x
            dy = center_pos.y - pos.y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance <= radius:
                # 根据距离计算士气损失
                distance_factor = 1.0 - (distance / radius)
                stats.morale = max(0, stats.morale - morale_loss * distance_factor)

    def _apply_nearby_morale_bonus(
        self, center_entity: int, faction_id: int, morale_gain: float, radius: float
    ) -> None:
        """对周围敌对阵营的单位应用士气提升
        
        Args:
            center_entity: 中心单位实体ID
            faction_id: 阵营ID
            morale_gain: 士气提升值
            radius: 影响半径
        """
        center_pos = self.world.get_component(center_entity, UnitPositionComponent)
        if not center_pos:
            return
            
        # 获取所有指定阵营单位
        for entity in self.world.get_entities_with_components(UnitStatsComponent, UnitPositionComponent):
            stats = self.world.get_component(entity, UnitStatsComponent)
            pos = self.world.get_component(entity, UnitPositionComponent)
            
            # 检查阵营
            if stats.faction_id != faction_id:
                continue
                
            # 计算距离
            dx = center_pos.x - pos.x
            dy = center_pos.y - pos.y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance <= radius:
                # 根据距离计算士气提升
                distance_factor = 1.0 - (distance / radius)
                stats.morale = min(100, stats.morale + morale_gain * distance_factor)

    def update(self, world: World, delta_time: float) -> None:
        """更新战斗效果系统
        
        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 恢复士气
        for entity in world.get_entities_with_components(UnitStatsComponent):
            stats = world.get_component(entity, UnitStatsComponent)
            state = world.get_component(entity, UnitStateComponent)
            
            # 如果单位不在战斗状态，慢慢恢复士气
            if not state or state.state not in [UnitState.ATTACKING, UnitState.DEFENDING]:
                # 非交战状态恢复士气
                recovery_rate = self.MORALE_RECOVERY_RATE
                
                # 如果是溃逃状态，士气恢复更慢
                if state and state.state == UnitState.ROUTING:
                    recovery_rate *= 0.5
                    
                    # 检查是否可以从溃逃状态恢复
                    if stats.morale > self.ROUTING_RECOVERY_THRESHOLD:  # 需要高于阈值一定量才恢复
                        state.state = UnitState.IDLE
                        
                        # 发布溃逃恢复事件
                        self.event_manager.publish(
                            Message(
                                topic="UNIT_RECOVERED_FROM_ROUTING",
                                data_type="unit_event",
                                data={
                                    "entity": entity,
                                    "unit_name": stats.name,
                                    "faction_id": stats.faction_id,
                                },
                            ),
                        )
                
                stats.morale = min(100, stats.morale + recovery_rate * delta_time)
                
        # 处理溃逃单位移动行为 (在这里简单实现，实际应该通过移动系统处理)
        for entity in world.get_entities_with_components(UnitStateComponent, UnitPositionComponent):
            state = world.get_component(entity, UnitStateComponent)
            
            if state.state == UnitState.ROUTING:
                # 为溃逃单位产生随机移动方向
                # 这里只是示例，实际应该生成一个远离敌人的逃跑向量
                # 并通过移动系统实现溃逃行为
                pass 