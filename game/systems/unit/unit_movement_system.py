import pygame
import math
from typing import Dict, Tuple, List, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import UnitMovementPathComponent
from game.components import UnitComponent, UnitState
from game.components import MapComponent
from game.components import TileComponent, TerrainType


class UnitMovementSystem(System):
    """移动系统，负责处理单位的平滑移动"""

    def __init__(self, priority: int = 15):
        """初始化移动系统，优先级设置为15（在UnitSystem之前执行）"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("MovementSystem")

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("移动系统初始化")

        # 订阅事件
        self.subscribe_events()

        self.logger.info("移动系统初始化完成")

    def _get_map_component(self) -> Optional[MapComponent]:
        """获取地图组件"""
        for entity, (map_component,) in self.context.with_all(
            MapComponent
        ).iter_components(MapComponent):
            return map_component
        return None

    def update(self, delta_time: float):
        """更新移动系统"""
        if not self.is_enabled():
            return

        # 获取地图组件
        map_component = self._get_map_component()

        for entity, (unit, path) in self.context.with_all(
            UnitComponent, UnitMovementPathComponent
        ).iter_components(UnitComponent, UnitMovementPathComponent):
            # 获取单位当前所在格子的地形影响因子
            terrain_factor = self._get_terrain_factor(
                map_component, path.current_x, path.current_y
            )

            # 更新移动路径
            if self.update_path(path, delta_time, terrain_factor):
                # 移动完成，更新单位状态
                unit.position_x = float("{:.1f}".format(path.target_x))
                unit.position_y = float("{:.1f}".format(path.target_y))
                unit.state = UnitState.IDLE
                self.logger.debug(
                    f"单位 {unit.name} 完成移动到 ({unit.position_x}, {unit.position_y})"
                )
                self.context.component_manager.remove_component(
                    entity, UnitMovementPathComponent
                )
                # 发布单位移动完成事件
                self.context.event_manager.publish(
                    EventMessage(
                        EventType.UNIT_ARRIVALED,
                        {
                            "entity": entity,
                            "target_x": unit.position_x,
                            "target_y": unit.position_y,
                        },
                    )
                )
            else:
                unit.position_x = float("{:.1f}".format(path.current_x))
                unit.position_y = float("{:.1f}".format(path.current_y))

    def subscribe_events(self):
        """订阅事件"""
        if self.context.event_manager:
            self.context.event_manager.subscribe(
                EventType.UNIT_MOVED, self._handle_unit_moved
            )
            self.logger.debug("订阅了单位移动事件")

    def update_path(self, path, delta_time, terrain_factor):
        if path.completed:
            return True

        # 应用地形影响因子
        path.terrain_factor = terrain_factor
        actual_speed = path.speed * path.terrain_factor

        # 计算本帧移动距离
        distance_this_frame = actual_speed * delta_time
        path.distance_moved += distance_this_frame

        # 如果已移动距离超过总距离，则完成移动
        if path.distance_moved >= path.total_distance:
            path.current_x = path.target_x
            path.current_y = path.target_y
            path.completed = True
            return True

        # 计算移动比例
        move_ratio = path.distance_moved / path.total_distance

        # 更新当前位置（线性插值）
        path.current_x = path.start_x + (path.target_x - path.start_x) * move_ratio
        path.current_y = path.start_y + (path.target_y - path.start_y) * move_ratio

        return False

    def start_movement(
        self,
        entity: Entity,
        target_x: float,
        target_y: float,
    ) -> bool:
        """开始单位移动"""
        # 检查单位是否存在
        if not self.context.has_component(entity, UnitComponent):
            return False
        unit = self.context.get_component(entity, UnitComponent)

        # 检查单位是否存活
        if not unit.is_alive:
            self.logger.debug(f"单位 {unit.name} 已死亡，无法移动。")
            return False

        # 计算移动距离
        start_x, start_y = unit.position_x, unit.position_y
        distance = math.sqrt((target_x - start_x) ** 2 + (target_y - start_y) ** 2)

        self.context.component_manager.add_component(
            entity,
            UnitMovementPathComponent(
                start_x=unit.position_x,
                start_y=unit.position_y,
                target_x=target_x,
                target_y=target_y,
                current_x=unit.position_x,
                current_y=unit.position_y,
                speed=unit.base_speed,
                total_distance=distance,
            ),
        )
        # 更新单位状态
        unit.state = UnitState.MOVING

        self.logger.info(
            f"单位 {unit.name} 开始移动从 ({start_x}, {start_y}) 到 ({target_x}, {target_y}), 距离: {distance:.2f}, 速度: {unit.base_speed:.2f}"
        )
        return True

    def is_unit_moving(self, entity: Entity) -> bool:
        """检查单位是否正在移动"""
        return self.context.has_component(entity, UnitMovementPathComponent)

    def adjust_path(self, entity: Entity, taget_x, target_y):
        """调整移动"""
        path = self.context.get_component(entity, UnitMovementPathComponent)
        path.target_x = taget_x
        path.target_y = target_y

    def _handle_unit_moved(self, event: EventMessage):
        """处理单位移动事件"""
        entity = event.data.get("entity")
        target_x = event.data.get("target_x")
        target_y = event.data.get("target_y")

        if not entity:
            return

        # 如果单位已经在移动，先取消当前移动
        if self.is_unit_moving(entity):
            self.adjust_path(entity, target_x, target_y)

        # 开始新的移动
        self.start_movement(entity, target_x, target_y)

    def _get_terrain_factor(
        self, map_component: MapComponent, x: float, y: float
    ) -> float:
        """获取地形对移动速度的影响因子"""
        if not map_component:
            return 1.0

        # 将浮点坐标转换为整数格子坐标
        grid_x, grid_y = int(x), int(y)

        # 检查坐标是否在地图范围内
        if (
            grid_x < 0
            or grid_x >= map_component.width
            or grid_y < 0
            or grid_y >= map_component.height
        ):
            return 1.0

        # 获取格子实体
        tile_entity = map_component.tile_entities.get((grid_x, grid_y))
        if not tile_entity:
            return 1.0

        # 获取格子组件
        tile_component = self.context.get_component(tile_entity, TileComponent)
        if not tile_component:
            return 1.0

        # 返回移动成本的倒数作为速度因子（移动成本越高，速度越慢）
        return 1.0 / max(0.1, tile_component.movement_cost)
