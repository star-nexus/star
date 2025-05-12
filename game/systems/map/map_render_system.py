import pygame
import numpy as np
from typing import Tuple, List, Dict, Optional
from framework.ecs.system import System
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import MapComponent
from game.components import TileComponent, TerrainType
from game.components import CameraComponent
from game.utils import RenderLayer
# from game.systems.fog_of_war_system import FogOfWarSystem


class MapRenderSystem(System):
    """地图渲染系统，负责渲染地图和地图上的实体"""

    def __init__(self, priority: int = 30):
        """初始化地图渲染系统"""
        super().__init__(required_components=[MapComponent], priority=priority)
        self.logger = get_logger("MapRenderSystem")
        self.terrain_colors = self._init_terrain_colors()
        self.tile_cache = {}  # 缓存渲染过的格子，提高性能

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("地图渲染系统初始化")

        # 订阅相机相关事件
        if self.context.event_manager:
            self.logger.debug("订阅了组件事件")

    def _init_terrain_colors(self) -> Dict[TerrainType, Tuple[int, int, int]]:
        """初始化地形类型对应的颜色"""
        return {
            # 基本地形
            TerrainType.PLAIN: (180, 210, 120),  # 平原: 浅绿色
            TerrainType.HILL: (160, 126, 84),  # 丘陵: 棕色
            TerrainType.MOUNTAIN: (120, 120, 120),  # 山地: 灰色
            TerrainType.PLATEAU: (160, 140, 110),  # 高原: 浅棕色
            TerrainType.BASIN: (190, 170, 120),  # 盆地: 土黄色
            # 植被类型
            TerrainType.FOREST: (34, 139, 34),  # 森林: 深绿色
            TerrainType.GRASSLAND: (124, 252, 0),  # 草地: 亮绿色
            # 水系
            TerrainType.RIVER: (64, 164, 223),  # 河流: 浅蓝色
            TerrainType.LAKE: (30, 144, 255),  # 湖泊: 道奇蓝
            TerrainType.OCEAN: (0, 90, 160),  # 海洋: 深蓝色
            TerrainType.WETLAND: (107, 142, 35),  # 湿地: 暗绿色
            # 特殊地形
            TerrainType.ROAD: (210, 180, 140),  # 道路: 褐色
            TerrainType.BRIDGE: (165, 42, 42),  # 桥梁: 棕红色
            TerrainType.CITY: (220, 20, 60),  # 城市: 红色
            TerrainType.VILLAGE: (255, 99, 71),  # 村庄: 珊瑚红
            TerrainType.CASTLE: (139, 69, 19),  # 城堡: 棕褐色
            TerrainType.PASS: (169, 169, 169),  # 关隘: 深灰色
        }

    def get_terrain_color(self, terrain_type: TerrainType) -> Tuple[int, int, int]:
        """获取地形类型对应的颜色"""
        return self.terrain_colors.get(terrain_type, (200, 200, 200))  # 默认为灰色

    def _render_tile(self, tile_component: TileComponent, size: int) -> pygame.Surface:
        """渲染单个格子，考虑海拔高度、道路和水系特性"""
        # 创建格子表面 - 使用比请求的尺寸略大的表面以消除缩放时的边缘缝隙
        extra_pixel = 1  # 额外添加1像素来避免边缘出现缝隙
        actual_size = size + extra_pixel
        tile_surface = pygame.Surface((actual_size, actual_size), pygame.SRCALPHA)

        # 获取基本地形颜色
        terrain_color = self.get_terrain_color(tile_component.terrain_type)

        # 根据海拔调整颜色亮度，创建等高线效果
        elevation_factor = min(1.0, tile_component.elevation / 100.0)  # 归一化到0-1
        if tile_component.terrain_type not in [
            TerrainType.RIVER,
            TerrainType.LAKE,
            TerrainType.OCEAN,
            TerrainType.WETLAND,
        ]:
            # 对非水系地形应用海拔亮度调整
            brightness_factor = 0.7 + (elevation_factor * 0.6)  # 0.7-1.3范围内的亮度
            terrain_color = self._adjust_color_brightness(
                terrain_color, brightness_factor
            )

        # 填充基本地形颜色
        tile_surface.fill(terrain_color)

        # 为道路和桥梁绘制特殊标记
        if tile_component.has_road or tile_component.terrain_type == TerrainType.ROAD:
            self._draw_road(tile_surface, size)

        if tile_component.has_river or tile_component.terrain_type == TerrainType.RIVER:
            self._draw_river(tile_surface, size)

        if (
            tile_component.has_bridge
            or tile_component.terrain_type == TerrainType.BRIDGE
        ):
            self._draw_bridge(tile_surface, size)

        # 为城市、村庄等添加标记
        if tile_component.terrain_type in [
            TerrainType.CITY,
            TerrainType.VILLAGE,
            TerrainType.CASTLE,
        ]:
            self._draw_settlement(tile_surface, size, tile_component.terrain_type)

        # 为特定海拔值添加等高线标记
        if tile_component.elevation % 10 == 0 and tile_component.elevation > 0:
            self._draw_contour_line(tile_surface, size)

        return tile_surface

    def _adjust_color_brightness(
        self, color: Tuple[int, int, int], factor: float
    ) -> Tuple[int, int, int]:
        """调整颜色亮度"""
        r, g, b = color
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return (r, g, b)

    def _draw_road(self, surface: pygame.Surface, size: int) -> None:
        """在格子上绘制道路"""
        road_color = (139, 69, 19)  # 棕色道路
        road_width = max(2, int(size * 0.2))
        mid_point = size // 2

        # 绘制十字形道路
        pygame.draw.line(
            surface, road_color, (0, mid_point), (size, mid_point), road_width
        )

    def _draw_river(self, surface: pygame.Surface, size: int) -> None:
        """在格子上绘制河流"""
        river_color = (30, 144, 255, 180)  # 半透明蓝色
        river_width = max(2, int(size * 0.3))

        # 绘制弯曲的河流（简化为对角线）
        pygame.draw.line(surface, river_color, (0, 0), (size, size), river_width)

    def _draw_bridge(self, surface: pygame.Surface, size: int) -> None:
        """在格子上绘制桥梁"""
        bridge_color = (139, 69, 19)  # 棕色桥
        river_color = (30, 144, 255, 180)  # 半透明蓝色

        # 先画河
        self._draw_river(surface, size)

        # 再画桥（垂直于河流方向）
        bridge_width = max(1, int(size * 0.15))
        pygame.draw.line(surface, bridge_color, (size, 0), (0, size), bridge_width)

    def _draw_settlement(
        self, surface: pygame.Surface, size: int, terrain_type: TerrainType
    ) -> None:
        """绘制居住点标记（城市、村庄、城堡）"""
        center = size // 2
        radius = max(3, int(size * 0.3))

        if terrain_type == TerrainType.CITY:
            # 城市绘制为大方形
            rect_size = radius * 2
            pygame.draw.rect(
                surface,
                (220, 20, 60),  # 亮红色
                pygame.Rect(center - radius, center - radius, rect_size, rect_size),
            )
        elif terrain_type == TerrainType.VILLAGE:
            # 村庄绘制为小圆形
            small_radius = radius // 2
            pygame.draw.circle(
                surface,
                (255, 99, 71),
                (center, center),
                small_radius,  # 珊瑚红
            )
        elif terrain_type == TerrainType.CASTLE:
            # 城堡绘制为星形（简化为十字加方块）
            cross_width = max(2, int(size * 0.1))
            pygame.draw.rect(
                surface,
                (139, 69, 19),  # 棕褐色
                pygame.Rect(center - radius // 2, center - radius // 2, radius, radius),
            )
            pygame.draw.line(
                surface,
                (0, 0, 0),
                (center, center - radius),
                (center, center + radius),
                cross_width,
            )
            pygame.draw.line(
                surface,
                (0, 0, 0),
                (center - radius, center),
                (center + radius, center),
                cross_width,
            )

    def _draw_contour_line(self, surface: pygame.Surface, size: int) -> None:
        """绘制等高线标记"""
        contour_color = (80, 80, 80, 100)  # 半透明深灰色
        contour_width = 1

        # 沿着边缘绘制等高线
        pygame.draw.rect(
            surface, contour_color, pygame.Rect(0, 0, size, size), contour_width
        )

    def _get_camera_component(self) -> Optional[CameraComponent]:
        """获取相机组件，不直接引用相机系统"""
        # 如果还没有存储相机实体ID，尝试查找一个
        camera_entity = self.context.with_all(CameraComponent).first()
        if not camera_entity:
            return None
        self.logger.debug(f"找到相机实体: {camera_entity}")

        # 从实体中获取相机组件
        camera_component = self.context.get_component(camera_entity, CameraComponent)
        return camera_component

    def _get_map_component(self) -> Optional[MapComponent]:
        """获取地图组件，不直接引用地图系统"""
        # 如果还没有存储地图实体ID，尝试查找一个
        map_entity = self.context.with_all(MapComponent).first()
        if not map_entity:
            return None
        self.logger.debug(f"找到地图实体: {map_entity}")
        # 从实体中获取地图组件
        map_component = self.context.get_component(map_entity, MapComponent)
        return map_component

    def _world_to_screen(
        self, world_x: float, world_y: float, camera_comp: CameraComponent
    ) -> Tuple[int, int]:
        """将世界坐标转换为屏幕坐标"""
        # 计算相对于相机的偏移
        screen_x = int(
            (world_x - camera_comp.x) * camera_comp.zoom + camera_comp.width / 2
        )
        screen_y = int(
            (world_y - camera_comp.y) * camera_comp.zoom + camera_comp.height / 2
        )
        return screen_x, screen_y

    def _get_visible_area(
        self, camera_comp: CameraComponent
    ) -> Tuple[float, float, float, float]:
        """获取当前相机可见区域的世界坐标"""
        # 避免除零错误并处理负值
        zoom = max(camera_comp.zoom, 0.0001)
        half_width = abs(camera_comp.width) / (2 * zoom)
        half_height = abs(camera_comp.height) / (2 * zoom)

        left = camera_comp.x - half_width
        top = camera_comp.y - half_height
        right = camera_comp.x + half_width
        bottom = camera_comp.y + half_height

        # 确保边界顺序合理
        min_x, max_x = sorted([left, right])
        min_y, max_y = sorted([top, bottom])

        return min_x, min_y, max_x, max_y

    def update(self, delta_time: float) -> None:
        """准备地图渲染数据，包括等高线、道路和水系"""

        camera_component = self._get_camera_component()
        if not camera_component:
            self.logger.warning("未找到相机组件，无法准备地图渲染数据")
            return

        map_component = self._get_map_component()
        if not map_component:
            return

        # 使用相机组件获取可见区域
        visible_area = self._get_visible_area(camera_component)
        left, top, right, bottom = visible_area

        # 计算可见的格子范围（添加额外的余量确保完全覆盖）
        tile_size = map_component.tile_size
        start_x = max(0, int(left / tile_size) - 1)
        start_y = max(0, int(top / tile_size) - 1)
        end_x = min(map_component.width - 1, int(right / tile_size) + 1)
        end_y = min(map_component.height - 1, int(bottom / tile_size) + 1)

        # 计算实际绘制尺寸（考虑缩放）
        draw_size = int(tile_size * camera_component.zoom)

        # 准备地图渲染数据
        for y in range(start_y, end_y + 1):
            for x in range(start_x, end_x + 1):
                if (x, y) in map_component.tile_entities:
                    tile_entity = map_component.tile_entities[(x, y)]
                    tile_component = self.context.get_component(
                        tile_entity, TileComponent
                    )

                    if tile_component:
                        # 世界坐标
                        world_x = x * tile_size
                        world_y = y * tile_size

                        # 创建更复杂的缓存键，包含地形所有特征
                        cache_key = (
                            tile_component.terrain_type,
                            draw_size,
                            tile_component.elevation // 10,  # 相同10级的高度共享缓存
                            tile_component.has_road,
                            tile_component.has_river,
                            tile_component.has_bridge,
                        )

                        if cache_key not in self.tile_cache:
                            self.tile_cache[cache_key] = self._render_tile(
                                tile_component, draw_size
                            )

                        # 将世界坐标转换为屏幕坐标
                        screen_pos = self._world_to_screen(
                            world_x, world_y, camera_component
                        )

                        # 渲染地图格子
                        self.context.render_manager.draw_surface(
                            self.tile_cache[cache_key],
                            screen_pos,
                            RenderLayer.MAP.value,
                        )
