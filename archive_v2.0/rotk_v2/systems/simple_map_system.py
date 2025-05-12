import pygame
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from framework_v2.ecs.system import System
from framework_v2.engine.events import EventType

from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.tile_component import TileComponent, TerrainType
from rotk_v2.components.map_component import MapComponent
from rotk_v2.components.camera_component import CameraComponent, MainCameraTagComponent
from rotk_v2.utils.map_generator import MapGenerator

class SimpleMapSystem(System):
    """简化版地图系统，负责地图的生成和管理"""
    
    def __init__(self, required_components=None, priority=0):
        super().__init__(required_components, priority)
        self.map_entity = None
        self.map_component = None
        self.tile_size = 32
        
        # 地形颜色映射
        self.terrain_colors = {
            TerrainType.PLAIN: (100, 200, 100),     # 浅绿色
            TerrainType.HILL: (150, 150, 100),      # 棕黄色
            TerrainType.MOUNTAIN: (120, 100, 80),   # 深棕色
            TerrainType.FOREST: (0, 150, 0),        # 深绿色
            TerrainType.WATER: (50, 100, 200),      # 蓝色
            TerrainType.DESERT: (240, 220, 160),    # 沙色
            TerrainType.SWAMP: (100, 130, 50),      # 暗绿色
            TerrainType.ROAD: (200, 180, 150),      # 浅棕色
            TerrainType.CITY: (200, 200, 200),      # 灰色
            TerrainType.PASS: (180, 120, 80)        # 棕色
        }
        
    def initialize(self):
        """初始化地图系统"""
        print("初始化简化版地图系统...")
        
        # 创建地图实体
        self.map_entity = self.entity_manager.create_entity()
        
        # 生成地图
        map_width = 50  # 减小地图大小以提高性能
        map_height = 40
        self.tile_size = 32
        
        # 使用地图生成器
        generator = MapGenerator(map_width, map_height)
        elevation, terrain, moisture = generator.generate_map()
        
        # 创建地图组件
        self.map_component = MapComponent(
            width=map_width,
            height=map_height,
            tile_size=self.tile_size,
            elevation_map=elevation,
            terrain_map=terrain,
            moisture_map=moisture,
            name="三国时期中国",
            description="公元200年左右的中国地图"
        )
        
        # 添加地图组件到地图实体
        self.component_manager.add_component(self.map_entity, self.map_component)
        
        # 创建所有地形块实体
        self._create_tile_entities()
        
        # 调试信息
        tile_count = len(self.map_component.tile_entities)
        print(f"创建了 {tile_count} 个地形块实体")
        
        # 发布地图创建事件
        print(f"地图创建完成，发布事件: {map_width}x{map_height}")
        self.context.event_manager.publish_immediate(
            EventType.MAP_CREATED,
            {"map_entity": self.map_entity, "width": map_width, "height": map_height}
        )
        
    def _create_tile_entities(self):
        """创建所有地形块实体"""
        for y in range(self.map_component.height):
            for x in range(self.map_component.width):
                # 创建地形块实体
                tile_entity = self.entity_manager.create_entity()
                # 获取地形信息
                terrain_type = TerrainType(self.map_component.terrain_map[y, x])
                elevation = self.map_component.elevation_map[y, x]
                # 计算世界坐标
                world_x = x * self.tile_size
                world_y = y * self.tile_size
                # 添加变换组件
                self.component_manager.add_component(tile_entity, TransformComponent(
                    x=world_x + self.tile_size // 2,
                    y=world_y + self.tile_size // 2
                ))
                # 添加渲染组件
                color = self.terrain_colors.get(terrain_type, (150, 150, 150))
                self.component_manager.add_component(tile_entity, RenderComponent(
                    color=color,
                    width=self.tile_size,
                    height=self.tile_size,
                    layer=0,
                    visible=True  # 确保可见性设置为True
                ))
                # 添加地形块组件
                tile_component = TileComponent(
                    terrain_type=terrain_type,
                    elevation=elevation,
                    grid_x=x,
                    grid_y=y
                )
                self.component_manager.add_component(tile_entity, tile_component)
                self.map_component.tile_entities[(x, y)] = tile_entity
                # 新增详细调试输出
                has_transform = self.component_manager.has_component(tile_entity, TransformComponent)
                has_render = self.component_manager.has_component(tile_entity, RenderComponent)
                print(f"Tile实体({x},{y}) ID={tile_entity}, Transform={has_transform}, Render={has_render}, Terrain={terrain_type}")
                
    def update(self, delta_time):
        """更新地图系统"""
        # 地图系统不需要每帧更新，这里可以留空
        pass
    
    def _is_valid_position(self, x: int, y: int) -> bool:
        """检查位置是否在地图范围内"""
        return 0 <= x < self.map_component.width and 0 <= y < self.map_component.height