import numpy as np
import pygame
from framework.ecs.system import System
from framework.utils.logging import get_logger
from game.components import MapComponent
from game.components import TileComponent, TerrainType
from game.utils.hex_utils import HexCoordinate, pixel_to_hex


class MapSystem(System):
    """地图系统，负责地图的生成和管理"""

    def __init__(self, priority: int = 10):
        """初始化地图系统"""
        super().__init__(required_components=[MapComponent], priority=priority)
        self.logger = get_logger("MapSystem")

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("地图系统初始化")

    def set_map_entity(self, map_entity):
        """设置地图实体引用"""
        self.map_entity = map_entity
        if self.map_entity:
            self.map_component = self.context.get_component(
                self.map_entity, MapComponent
            )
            self.logger.info(
                f"地图系统设置地图实体: {self.map_entity}, 尺寸: {self.map_component.width}x{self.map_component.height}, 类型: {self.map_component.map_type}"
            )
        return self.map_entity

    def get_map_entity(self):
        """获取地图实体"""
        return self.map_entity

    def get_tile_at(self, x, y):
        """获取指定位置的格子实体"""
        if self.map_component.map_type == "hexagonal":
            # 六边形地图：将像素坐标转换为六边形坐标
            hex_coord = pixel_to_hex(
                x, y, self.map_component.hex_size, self.map_component.orientation
            )
            hex_tuple = hex_coord.to_tuple()
            return self.map_component.hex_entities.get(hex_tuple)
        else:
            # 方形地图：使用原有逻辑
            if (x, y) in self.map_component.tile_entities:
                return self.map_component.tile_entities[(x, y)]
        return None

    def get_hex_tile_at(self, hex_coord: HexCoordinate):
        """获取指定六边形坐标的格子实体"""
        if self.map_component.map_type == "hexagonal":
            hex_tuple = hex_coord.to_tuple()
            return self.map_component.hex_entities.get(hex_tuple)
        return None

    def update(self, delta_time: float) -> None:
        """更新系统逻辑（每帧调用）"""
        # 地图系统大部分逻辑在生成时完成，每帧更新主要处理可能的动态变化
        # 例如地形变化、可见性更新等
        pass
