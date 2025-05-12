import pygame
import math
from typing import Dict, Tuple, List, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import UnitComponent, UnitState
from game.components import MapComponent


class UnitAttackSystem(System):
    """攻击系统，负责处理单位间的攻击行为"""

    def __init__(self, priority: int = 15):
        """初始化攻击系统，优先级设置为15（在UnitSystem之前执行）"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("AttackSystem")
        self.attack_cooldowns = {}  # 存储单位攻击冷却时间

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("攻击系统初始化")

        # 订阅事件
        self.subscribe_events()

        self.logger.info("攻击系统初始化完成")

    def subscribe_events(self):
        """订阅事件"""
        if self.context.event_manager:
            self.context.event_manager.subscribe(
                EventType.UNIT_ATTACKED, self._handle_attack_event
            )
            self.logger.debug("订阅了攻击事件")

    def update(self, delta_time: float):
        """更新攻击系统"""
        if not self.is_enabled():
            return

        # 更新攻击冷却时间
        self._update_attack_cooldowns(delta_time)

        # 处理正在攻击状态的单位
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if unit.state == UnitState.ATTACKING:
                # 如果攻击动画或效果完成，将单位状态恢复为空闲
                if (
                    entity not in self.attack_cooldowns
                    or self.attack_cooldowns[entity] <= 0
                ):
                    unit.state = UnitState.IDLE
                    self.logger.debug(f"单位 {unit.name} 攻击完成，恢复为空闲状态")

    def _update_attack_cooldowns(self, delta_time: float):
        """更新攻击冷却时间"""
        entities_to_remove = []
        for entity, cooldown in self.attack_cooldowns.items():
            self.attack_cooldowns[entity] = cooldown - delta_time
            if self.attack_cooldowns[entity] <= 0:
                entities_to_remove.append(entity)

        # 移除已完成冷却的单位
        for entity in entities_to_remove:
            del self.attack_cooldowns[entity]

    def _handle_attack_event(self, event: EventMessage):
        """处理攻击事件"""
        attacker_entity = event.data.get("entity")
        target_entity = event.data.get("target")

        if not attacker_entity or not target_entity:
            self.logger.warning("攻击事件缺少攻击者或目标信息")
            return

        self.attack_unit(attacker_entity, target_entity)

    def attack_unit(self, attacker_entity: Entity, target_entity: Entity) -> bool:
        """单位攻击另一个单位"""
        if not (
            self.context.component_manager.has_component(attacker_entity, UnitComponent)
            and self.context.component_manager.has_component(
                target_entity, UnitComponent
            )
        ):
            return False

        attacker = self.context.get_component(attacker_entity, UnitComponent)
        target = self.context.get_component(target_entity, UnitComponent)

        # 检查攻击者是否可以攻击
        if not self.can_attack(attacker):
            self.logger.info(f"单位 {attacker.name} 无法攻击")
            return False

        # 检查目标是否存活
        if not self.is_alive(target):
            self.logger.info(f"目标单位 {target.name} 已阵亡")
            return False

        # 计算攻击距离
        distance = abs(target.position_x - attacker.position_x) + abs(
            target.position_y - attacker.position_y
        )

        # 检查攻击距离是否在攻击范围内
        if distance > attacker.range:
            self.logger.info(f"目标单位超出单位 {attacker.name} 的攻击范围")
            return False

        # 计算伤害
        damage = self.calculate_damage(attacker, target)

        # 应用伤害
        target.current_health = max(0, target.current_health - damage)

        # 更新状态
        attacker.state = UnitState.ATTACKING
        # attacker.has_acted = True

        # 设置攻击冷却时间（1秒）
        self.attack_cooldowns[attacker_entity] = 1.0

        # 发布攻击事件
        # self.context.event_manager.publish(
        #     EventMessage(
        #         EventType.UNIT_ATTACKED,
        #         {
        #             "attacker": attacker_entity,
        #             "target": target_entity,
        #             "damage": damage,
        #         },
        #     )
        # )

        self.logger.info(
            f"单位 {attacker.name} 攻击单位 {target.name}，造成 {damage} 点伤害"
        )

        # 检查目标是否阵亡
        if target.current_health <= 0:
            target.state = UnitState.DEAD
            target.is_alive = False  # 更新存活状态
            self.logger.info(f"单位 {target.name} 已阵亡")
            # 发布单位阵亡事件
            self.context.event_manager.publish(
                EventMessage(
                    EventType.UNIT_KILLED,
                    {
                        "killer": attacker_entity,
                        "target": target_entity,
                        "unit_component": target,
                    },
                )
            )

        return True

    def calculate_damage(self, attacker: UnitComponent, target: UnitComponent) -> int:
        """计算攻击伤害"""
        # 基础伤害
        base_damage = max(
            1, attacker.attack - target.defense // 2
        )  # 确保至少造成1点伤害

        # 可以在这里添加更复杂的伤害计算逻辑，如：
        # - 单位类型克制关系
        # - 随机因素
        # - 地形影响
        # - 状态效果

        return base_damage

    def is_alive(self, unit: UnitComponent) -> bool:
        """检查单位是否存活"""
        return unit.is_alive

    def can_attack(self, unit: UnitComponent) -> bool:
        """检查单位是否可以攻击"""
        return self.is_alive(unit)  # and not unit.has_acted

    def is_in_attack_range(
        self, attacker: UnitComponent, target: UnitComponent
    ) -> bool:
        """检查目标是否在攻击范围内"""
        distance = abs(target.position_x - attacker.position_x) + abs(
            target.position_y - attacker.position_y
        )
        return distance <= attacker.range
