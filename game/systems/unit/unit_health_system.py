from typing import Dict, List, Tuple, Any

from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger

from game.components import UnitComponent, UnitState, UnitType
from game.components.unit.unit_effect_component import UnitEffectComponent

from framework.engine.events import EventMessage, EventType


class UnitHealthSystem(System):
    """单位生命值系统，负责处理单位的生命值自动变化

    根据单位的效果组件中的效果数据，自动扣除或恢复生命值
    """

    def __init__(self, priority: int = 20):
        super().__init__(
            required_components=[UnitComponent, UnitEffectComponent],
            priority=priority,
        )
        self.logger = get_logger("UnitHealthSystem")
        # 添加计时器，控制生命值和体力值变化的频率
        self.health_timer = 0.0
        self.health_update_interval = 100  # 每秒更新一次

    def initialize(self, context):
        self.logger.info("单位生命值系统初始化")
        self.context = context
        # 重置计时器
        self.health_timer = 0.0

    def update(self, delta_time):
        """更新所有单位的生命值

        检查单位的效果组件中的效果，根据效果数据自动扣除或恢复生命值
        每秒只执行一次生命值和体力值的变化
        """
        # 更新计时器
        self.health_timer += delta_time

        # 只有当计时器达到或超过更新间隔时才处理生命值和体力值变化
        if self.health_timer >= self.health_update_interval:
            self.logger.debug(
                f"执行生命值和体力值更新，间隔：{self.health_timer:.2f}秒"
            )

            for unit_entity, (unit_component, unit_effect) in self.context.with_all(
                UnitComponent, UnitEffectComponent
            ).iter_components(UnitComponent, UnitEffectComponent):
                # 跳过已死亡的单位
                if not unit_component.is_alive:
                    continue

                # 处理生命值变化效果
                self._process_health_effects(unit_entity, unit_component, unit_effect)

                # 处理体力恢复效果
                self._process_stamina_effects(unit_entity, unit_component, unit_effect)

                # 检查单位生命值是否归零
                if unit_component.current_health <= 0:
                    self._handle_unit_death(unit_entity, unit_component)

            # 重置计时器（减去间隔时间，而不是直接设为0，以保持精确的时间间隔）
            self.health_timer -= self.health_update_interval

    def _process_health_effects(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
    ):
        """处理生命值变化效果

        Args:
            unit_entity: 单位实体
            unit_component: 单位组件
            unit_effect: 单位效果组件
        """
        health_change = 0

        # 检查水域效果（减少生命值）
        if unit_effect.has_effect("terrain_water"):
            effect_data = unit_effect.get_effect_data("terrain_water")
            if effect_data and "health_reduction" in effect_data:
                health_change += effect_data["health_reduction"]

        # 检查其他可能影响生命值的效果
        # 这里可以添加更多效果的处理

        # 应用生命值变化
        if health_change != 0:
            old_health = unit_component.current_health
            unit_component.current_health = max(
                0,
                min(
                    unit_component.max_health,
                    unit_component.current_health + health_change,
                ),
            )
            self.logger.debug(
                f"单位 {unit_component.name}(ID:{unit_entity}) 生命值变化: "
                f"{old_health} -> {unit_component.current_health} (变化: {health_change})"
            )

    def _process_stamina_effects(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
    ):
        """处理体力恢复效果

        Args:
            unit_entity: 单位实体
            unit_component: 单位组件
            unit_effect: 单位效果组件
        """
        stamina_change = 0

        # 检查水边效果（恢复体力）
        if unit_effect.has_effect("terrain_waterside"):
            effect_data = unit_effect.get_effect_data("terrain_waterside")
            if effect_data and "stamina_recovery" in effect_data:
                stamina_change += effect_data["stamina_recovery"]

        # 应用体力变化（这里使用movement_left作为体力值）
        if stamina_change != 0:
            old_movement = unit_component.movement_left
            unit_component.movement_left = max(
                0,
                min(
                    unit_component.movement,
                    unit_component.movement_left + stamina_change,
                ),
            )
            self.logger.debug(
                f"单位 {unit_component.name}(ID:{unit_entity}) 体力变化: "
                f"{old_movement} -> {unit_component.movement_left} (变化: {stamina_change})"
            )

    def _handle_unit_death(self, unit_entity: Entity, unit_component: UnitComponent):
        """处理单位死亡

        Args:
            unit_entity: 单位实体
            unit_component: 单位组件
        """
        # 标记单位为死亡状态
        unit_component.state = UnitState.DEAD
        unit_component.is_alive = False
        unit_component.current_health = 0
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_KILLED,
                {
                    "killer": None,
                    "target": unit_entity,
                    # "unit_component": unit_component,
                },
            )
        )
        self.logger.info(f"单位 {unit_component.name}(ID:{unit_entity}) 死亡")

        # 这里可以触发单位死亡事件
        # self.context.event_manager.emit(EventType.UNIT_DIED, {"entity": unit_entity})
