import pygame
import math
import random
from typing import Dict, Tuple, List, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging_tool import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import UnitComponent, UnitState, UnitType
from game.components import MapComponent


class UnitAIControlSystem(System):
    """AI控制系统，负责控制非玩家单位的自主行动

    功能包括：
    1. 自动寻找目标
    2. 决策移动路径
    3. 决定何时攻击
    """

    def __init__(self, priority: int = 10):
        """初始化AI控制系统，优先级设置为10（在UnitMovementSystem和UnitAttackSystem之前执行）"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("AIControllerSystem")
        self.ai_decision_cooldowns = {}  # 存储AI决策冷却时间
        self.ai_targets = {}  # 存储AI单位的目标 {ai_entity: target_entity}
        self.decision_interval = 1.0  # AI决策间隔（秒）

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("AI控制系统初始化")
        self.logger.info("AI控制系统初始化完成")

    def update(self, delta_time: float):
        """更新AI控制系统"""
        if not self.is_enabled():
            return

        # 更新AI决策冷却时间
        self._update_decision_cooldowns(delta_time)

        # 处理AI单位的决策
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            # 只处理非玩家控制的单位且单位存活
            if unit.owner_id != 0 and unit.is_alive:
                # 检查是否需要做出新的决策
                if (
                    entity not in self.ai_decision_cooldowns
                    or self.ai_decision_cooldowns[entity] <= 0
                ):
                    self._make_ai_decision(entity, unit)
                    # 设置决策冷却时间
                    self.ai_decision_cooldowns[entity] = self.decision_interval

    def _update_decision_cooldowns(self, delta_time: float):
        """更新AI决策冷却时间"""
        entities_to_remove = []
        for entity, cooldown in self.ai_decision_cooldowns.items():
            self.ai_decision_cooldowns[entity] = cooldown - delta_time
            if self.ai_decision_cooldowns[entity] <= 0:
                entities_to_remove.append(entity)

        # 移除已完成冷却的单位
        for entity in entities_to_remove:
            del self.ai_decision_cooldowns[entity]

    def _make_ai_decision(self, entity: Entity, unit: UnitComponent):
        """为AI单位做出决策"""
        # 如果单位正在移动或攻击，或者单位已死亡，不做新的决策
        if unit.state in [UnitState.MOVING, UnitState.ATTACKING] or not unit.is_alive:
            return

        # 1. 寻找目标
        target_entity = self._find_target(entity, unit)

        # 如果找到目标，更新目标记录
        if target_entity:
            self.ai_targets[entity] = target_entity
            target_unit = self.context.get_component(target_entity, UnitComponent)

            # 2. 检查是否在攻击范围内
            distance = self._calculate_distance(unit, target_unit)

            if distance <= unit.range:
                # 在攻击范围内，发起攻击
                self._attack_target(entity, target_entity)
                self.logger.debug(f"AI单位 {unit.name} 攻击目标 {target_unit.name}")
            else:
                # 不在攻击范围内，移动接近目标
                self._move_towards_target(entity, unit, target_unit)
                self.logger.debug(f"AI单位 {unit.name} 向目标 {target_unit.name} 移动")
        else:
            # 没有找到目标，随机移动
            self._random_movement(entity, unit)
            self.logger.debug(f"AI单位 {unit.name} 随机移动")

    def _find_target(self, entity: Entity, unit: UnitComponent) -> Optional[Entity]:
        """寻找攻击目标"""
        # 如果已有目标且目标仍然有效，继续使用当前目标
        if entity in self.ai_targets:
            current_target = self.ai_targets[entity]
            if self.context.component_manager.has_component(
                current_target, UnitComponent
            ):
                target_unit_comp = self.context.get_component(
                    current_target, UnitComponent
                )
                if (
                    target_unit_comp
                    and target_unit_comp.is_alive
                    and target_unit_comp.owner_id != unit.owner_id
                ):
                    return current_target
            # 如果当前目标无效，则清除
            del self.ai_targets[entity]

        # 寻找新目标
        potential_targets = []

        # 遍历所有单位，寻找敌方单位
        for target_entity, (target_unit,) in self.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            # 检查是否是敌方单位且存活
            if target_unit.owner_id != unit.owner_id and target_unit.is_alive:
                # 计算距离
                distance = self._calculate_distance(unit, target_unit)
                # 将目标和距离添加到潜在目标列表
                potential_targets.append((target_entity, distance))

        # 如果有潜在目标，选择最近的目标
        if potential_targets:
            # 按距离排序
            potential_targets.sort(key=lambda x: x[1])
            # 返回最近的目标
            return potential_targets[0][0]

        return None

    def _is_valid_target(self, target_entity: Entity, unit: UnitComponent) -> bool:
        """检查目标是否有效"""
        # 检查目标是否存在且有UnitComponent
        if not self.context.component_manager.has_component(
            target_entity, UnitComponent
        ):
            return False

        target_unit = self.context.get_component(target_entity, UnitComponent)

        # 检查目标是否是敌方单位且存活
        return target_unit.owner_id != unit.owner_id and target_unit.is_alive

    def _calculate_distance(self, unit1: UnitComponent, unit2: UnitComponent) -> float:
        """计算两个单位之间的曼哈顿距离"""
        return abs(unit1.position_x - unit2.position_x) + abs(
            unit1.position_y - unit2.position_y
        )

    def _attack_target(self, attacker_entity: Entity, target_entity: Entity):
        """发起攻击"""
        # 发布攻击事件
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_ATTACKED,
                {
                    "entity": attacker_entity,
                    "target": target_entity,
                },
            )
        )

    def _move_towards_target(
        self, entity: Entity, unit: UnitComponent, target_unit: UnitComponent
    ):
        """向目标移动"""
        # 计算移动方向
        dx = target_unit.position_x - unit.position_x
        dy = target_unit.position_y - unit.position_y

        # 确定移动距离（不超过单位的移动范围）
        move_distance = min(unit.base_speed, max(abs(dx), abs(dy)))

        # 计算移动目标位置
        if abs(dx) > abs(dy):
            # 水平方向移动
            target_x = unit.position_x + (move_distance if dx > 0 else -move_distance)
            target_y = unit.position_y
        else:
            # 垂直方向移动
            target_x = unit.position_x
            target_y = unit.position_y + (move_distance if dy > 0 else -move_distance)

        # 发布移动事件
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_MOVED,
                {
                    "entity": entity,
                    "target_x": target_x,
                    "target_y": target_y,
                },
            )
        )

    def _random_movement(self, entity: Entity, unit: UnitComponent):
        """随机移动"""
        # 随机选择一个方向
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        dx, dy = random.choice(directions)

        # 计算移动目标位置
        target_x = unit.position_x + dx * unit.base_speed
        target_y = unit.position_y + dy * unit.base_speed

        # 确保目标位置在地图范围内
        map_component = self._get_map_component()
        if map_component:
            target_x = max(0, min(target_x, map_component.width - 1))
            target_y = max(0, min(target_y, map_component.height - 1))

        # 发布移动事件
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_MOVED,
                {
                    "entity": entity,
                    "target_x": target_x,
                    "target_y": target_y,
                },
            )
        )

    def _get_map_component(self) -> Optional[MapComponent]:
        """获取地图组件"""
        for entity, (map_component,) in self.context.with_all(
            MapComponent
        ).iter_components(MapComponent):
            return map_component
        return None
