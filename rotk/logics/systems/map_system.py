import math
import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    MapComponent,
    PositionComponent,
    RenderableComponent,
    UnitPositionComponent,
    TerrainType,
)

from rotk.logics.managers import MapManager, CameraManager


class MapSystem(System):
    """地图系统，负责地图生成和渲染"""

    def __init__(self):
        super().__init__([MapComponent], priority=10)
        self.camera_manager = None

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        camera_manager: CameraManager = None,
    ) -> None:
        """初始化地图系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            camera_manager: 相机管理器（可选）
        """
        self.event_manager = event_manager
        self.camera_manager = camera_manager

        # 订阅地图相关事件
        self.event_manager.subscribe(
            "MAP_REGENERATED",
            lambda message: self._handle_map_regenerated(world, message),
        )

    def _handle_map_regenerated(self, world: World, message: Message) -> None:
        """处理地图重新生成事件"""
        # 此处可以添加地图重生成后的处理逻辑
        pass

    def update(self, world: World, delta_time: float) -> None:
        """更新地图系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 地图系统的更新逻辑
        pass

    def is_position_valid(self, map_comp, x, y):
        """检查位置是否在地图范围内且可通行"""
        if not map_comp:
            return False

        # 检查边界
        if x < 0 or x >= map_comp.width or y < 0 or y >= map_comp.height:
            return False

        # 检查地形是否可通行
        terrain_type = map_comp.grid[y][x]
        if terrain_type in [TerrainType.OCEAN]:  # 海洋不可通行
            return False

        return True

    def regenerate_map(self, world: World) -> None:
        """重新生成地图

        Args:
            world: 游戏世界
        """
        map_entity = world.get_entities_with_components(MapComponent)
        if not map_entity:
            return

        map_comp = world.get_component(map_entity[0], MapComponent)
        if not map_comp:
            return

        # 清空实体位置字典但保留地图实体
        map_comp.entities_positions = {}

        # 发送地图重生成事件
        self.event_manager.publish(
            "MAP_REGENERATED",
            Message(
                topic="MAP_REGENERATED",
                data_type="map_event",
                data={"map_entity": map_entity},
            ),
        )
