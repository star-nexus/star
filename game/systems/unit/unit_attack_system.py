import pygame
import math
from typing import Dict, Tuple, List, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import UnitComponent, UnitState, TerrainType
from game.components import MapComponent, TileComponent
from game.components.unit.unit_effect_component import UnitEffectComponent


class UnitAttackSystem(System):
    """攻击系统，负责处理单位间的攻击行为"""

    def __init__(self, priority: int = 15):
        """初始化攻击系统，优先级设置为15（在UnitSystem之前执行）"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("AttackSystem")
        self.attack_cooldowns = {}  # 存储单位攻击冷却时间
        self.auto_attack_timer = 0.0  # 自动攻击计时器

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("攻击系统初始化")

        # 订阅事件
        self.subscribe_events()

        self.logger.info("攻击系统初始化完成")

    def subscribe_events(self):
        """订阅事件"""
        # if self.context.event_manager:
            # self.context.event_manager.subscribe(
            #     EventType.UNIT_ATTACK, self._handle_attack_event
            # )
            # self.logger.debug("订阅了攻击事件")

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

        # 自动攻击逻辑
        self.auto_attack_timer += delta_time
        if self.auto_attack_timer >= 2.0:  # 每2秒检测一次
            self._check_auto_attack()
            self.auto_attack_timer = 0.0  # 重置计时器

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
        # distance = abs(target.position_x - attacker.position_x) + abs(
        #     target.position_y - attacker.position_y
        # )

        # # 检查攻击距离是否在攻击范围内
        # if distance > attacker.range:
        #     self.logger.info(f"目标单位超出单位 {attacker.name} 的攻击范围")
        #     return False

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
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_ATTACKED,
                {
                    "attacker": attacker_entity,
                    "target": target_entity,
                    "damage": damage,
                },
            )
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
        # 使用更完整的伤害计算方法
        attacker_entity = None
        target_entity = None

        # 查找攻击者和目标的实体
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if unit == attacker:
                attacker_entity = entity
            elif unit == target:
                target_entity = entity

            if attacker_entity and target_entity:
                break

        if attacker_entity and target_entity:
            return self._calculate_damage(
                attacker_entity, target_entity, attacker, target
            )
        else:
            # 基础伤害计算（如果找不到实体）
            return max(1, attacker.attack - target.defense // 2)  # 确保至少造成1点伤害

    def _calculate_damage(
        self,
        attacker_entity: Entity,
        defender_entity: Entity,
        attacker: UnitComponent,
        defender: UnitComponent,
    ) -> int:
        """计算攻击伤害

        Args:
            attacker_entity: 攻击者实体
            defender_entity: 防御者实体
            attacker: 攻击者组件
            defender: 防御者组件

        Returns:
            造成的伤害值
        """
        # 基础伤害
        base_damage = attacker.attack

        # 应用地形效果加成
        base_damage = self._apply_terrain_effects_to_damage(
            attacker_entity, defender_entity, base_damage
        )

        # 考虑防御力
        damage = max(1, base_damage - defender.defense)

        # 随机波动（±10%）
        import random

        damage = int(damage * (0.9 + 0.2 * random.random()))

        return max(1, damage)  # 确保至少造成1点伤害

    def _apply_terrain_effects_to_damage(
        self, attacker_entity: Entity, defender_entity: Entity, base_damage: float
    ) -> float:
        """应用地形效果到攻击伤害

        Args:
            attacker_entity: 攻击者实体
            defender_entity: 防御者实体
            base_damage: 基础伤害值

        Returns:
            修正后的伤害值
        """
        modified_damage = base_damage

        # 检查攻击者是否有效果组件
        if self.context.component_manager.has_component(
            attacker_entity, UnitEffectComponent
        ):
            effect_component = self.context.component_manager.get_component(
                attacker_entity, UnitEffectComponent
            )

            # 应用攻击加成效果
            for effect_id in effect_component.active_effects:
                effect_data = effect_component.effect_data.get(effect_id, {})

                # 山地效果：对非山地地形攻击加成
                if "attack_bonus" in effect_data:
                    # 检查防御者所在地形
                    defender_terrain = self._get_unit_terrain(defender_entity)
                    if defender_terrain != TerrainType.MOUNTAIN:
                        modified_damage *= effect_data["attack_bonus"]

                # 城市占领效果：攻击力提高
                if (
                    "attack_bonus" in effect_data
                    and "occupied_by_faction" in effect_data
                ):
                    if (
                        effect_data["occupied_by_faction"]
                        == self.context.component_manager.get_component(
                            attacker_entity, UnitComponent
                        ).faction
                    ):
                        modified_damage *= effect_data["attack_bonus"]

        return modified_damage

    def _get_unit_terrain(self, unit_entity: Entity) -> Optional[TerrainType]:
        """获取单位所在的地形类型

        Args:
            unit_entity: 单位实体

        Returns:
            地形类型，如果无法确定则返回None
        """
        unit = self.context.component_manager.get_component(unit_entity, UnitComponent)
        if not unit:
            return None

        # 获取地图组件
        map_entity = None
        for entity, (map_comp,) in self.context.with_all(MapComponent).iter_components(
            MapComponent
        ):
            map_entity = entity
            break

        if not map_entity:
            return None

        map_component = self.context.component_manager.get_component(
            map_entity, MapComponent
        )
        if not map_component:
            return None

        # 将世界坐标转换为格子坐标
        tile_x = int(unit.position_x / map_component.tile_size)
        tile_y = int(unit.position_y / map_component.tile_size)

        # 确保坐标在地图范围内
        if 0 <= tile_x < map_component.width and 0 <= tile_y < map_component.height:
            tile_entity = map_component.tile_entities.get((tile_x, tile_y))
            if tile_entity:
                tile_component = self.context.component_manager.get_component(
                    tile_entity, TileComponent
                )
                if tile_component:
                    return tile_component.terrain_type

        return None

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
        # distance = abs(target.position_x - attacker.position_x) + abs(
        #     target.position_y - attacker.position_y
        # )
        # dx = target.position_x - attacker.position_x
        # dy = target.position_y - attacker.position_y
        # distance = math.sqrt(dx*dx + dy*dy)
        distance = math.hypot(attacker.position_x - target.position_x, attacker.position_y - target.position_y)

        # print(f"单位类型: {attacker.unit_type}, 攻击范围: {attacker.range}，距离: {distance}")
        return int(distance+1) <= attacker.range

    def _check_auto_attack(self):
        """检测并执行自动攻击"""
        # 获取所有存活的单位
        units_data = []
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if unit.is_alive and unit.state != UnitState.ATTACKING:
                units_data.append((entity, unit))

        # 检查每个单位是否可以攻击其他阵营的单位
        for attacker_entity, attacker_unit in units_data:
            # 跳过正在冷却的单位
            if (
                attacker_entity in self.attack_cooldowns
                and self.attack_cooldowns[attacker_entity] > 0
            ):
                continue

            # 查找攻击范围内的敌对单位
            for target_entity, target_unit in units_data:
                # 跳过同一单位或同一阵营的单位
                if (
                    attacker_entity == target_entity
                    or attacker_unit.faction == target_unit.faction
                ):
                    continue

                # 检查是否在攻击范围内
                if self.is_in_attack_range(attacker_unit, target_unit):
                    self.logger.info(
                        f"单位 {attacker_unit.name} 自动攻击范围内的敌对单位 {target_unit.name}"
                    )
                    self.attack_unit(attacker_entity, target_entity)
                    break  # 每次只攻击一个目标
