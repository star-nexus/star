import pygame
import numpy as np
import os
import math
from typing import Tuple, List, Dict, Optional
from framework.ecs.system import System
from framework.utils.logging_tool import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import MapComponent
from game.components import TileComponent, TerrainType
from game.components import CameraComponent
from game.utils import RenderLayer
from game.utils.hex_utils import (
    HexCoordinate,
    hex_to_pixel,
    pixel_to_hex,
    HexOrientation,
)


class MapRenderSystem(System):
    """地图渲染系统，支持六边形和方形地图渲染"""

    def __init__(self, priority: int = 30):
        """初始化地图渲染系统"""
        super().__init__(required_components=[MapComponent], priority=priority)
        self.logger = get_logger("MapRenderSystem")
        self.terrain_colors = self._init_terrain_colors()
        self.tile_cache = {}  # 缓存渲染过的格子，提高性能
        self.texture_cache = {}  # 贴图缓存
        self.use_textures = True  # 是否使用贴图渲染
        self.texture_path = os.path.join(
            "game", "prefab", "prefab_config", "tile_texture"
        )  # 贴图路径
        self.terrain_textures = {}  # 地形类型对应的贴图

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("地图渲染系统初始化")

        # 加载贴图
        self._load_terrain_textures()

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

    def _load_terrain_textures(self):
        """加载地形贴图"""
        # 贴图文件夹路径
        texture_dir = os.path.join(
            self.texture_path,
        )
        self.logger.info(f"加载地形贴图，路径: {texture_dir}")

        # 检查贴图文件夹是否存在
        if not os.path.exists(texture_dir):
            self.logger.warning(f"贴图文件夹不存在: {texture_dir}")
            self.use_textures = False
            return

        try:
            # 遍历贴图文件夹中的所有文件
            texture_files = os.listdir(texture_dir)

            # 简单的贴图映射规则（根据文件名包含的关键字映射到地形类型）
            texture_mapping = {
                "plain": TerrainType.PLAIN,
                # "hill": TerrainType.HILL,
                "mountain": TerrainType.MOUNTAIN,
                "forest": TerrainType.FOREST,
                # "grass": TerrainType.GRASSLAND,
                "river": TerrainType.RIVER,
                # "lake": TerrainType.LAKE,
                # "ocean": TerrainType.OCEAN,
                # "road": TerrainType.ROAD,
                "city": TerrainType.CITY,
                "bridge": TerrainType.BRIDGE,
                # "village": TerrainType.VILLAGE,
                # "castle": TerrainType.CASTLE,
            }

            # 为每种地形类型选择一个默认贴图
            # 由于贴图文件名不规则，这里采用一种简单的策略：使用第一个找到的贴图
            for terrain_type in TerrainType:
                # 为每种地形类型分配一个默认贴图
                self.terrain_textures[terrain_type] = None

            # 加载所有贴图文件
            for file_name in texture_files:
                if file_name.lower().endswith(".png") or file_name.lower().endswith(
                    ".jpg"
                ):
                    file_path = os.path.join(texture_dir, file_name)
                    try:
                        # 加载贴图
                        texture = pygame.image.load(file_path).convert_alpha()

                        # 根据文件名分配给对应的地形类型
                        for keyword, terrain_type in texture_mapping.items():
                            if (
                                keyword.lower() in file_name.lower()
                                and self.terrain_textures[terrain_type] is None
                            ):
                                self.terrain_textures[terrain_type] = texture
                                self.logger.msg(
                                    f"为地形类型 {terrain_type} 加载贴图: {file_name}"
                                )
                    except Exception as e:
                        self.logger.error(f"加载贴图失败: {file_path}, 错误: {e}")

            # 检查是否所有地形类型都有贴图，如果没有，使用第一个加载的贴图作为默认
            default_texture = None
            if texture_files and len(texture_files) > 0:
                try:
                    default_file = os.path.join(texture_dir, texture_files[0])
                    if default_file.lower().endswith(
                        ".png"
                    ) or default_file.lower().endswith(".jpg"):
                        default_texture = pygame.image.load(
                            default_file
                        ).convert_alpha()
                except Exception as e:
                    self.logger.error(f"加载默认贴图失败: {e}")

            # 为没有贴图的地形类型分配默认贴图
            for terrain_type in TerrainType:
                if self.terrain_textures[terrain_type] is None:
                    self.terrain_textures[terrain_type] = default_texture

            # 检查是否成功加载了贴图
            if all(texture is None for texture in self.terrain_textures.values()):
                self.logger.warning("没有成功加载任何贴图，将使用颜色渲染")
                self.use_textures = False
            else:
                self.logger.msg(
                    f"成功加载了 {sum(1 for t in self.terrain_textures.values() if t is not None)} 个地形贴图"
                )

        except Exception as e:
            self.logger.error(f"加载贴图过程中发生错误: {e}")
            self.use_textures = False

    def _calculate_hex_points(
        self, hex_size: float, orientation: HexOrientation = HexOrientation.FLAT_TOP
    ) -> List[Tuple[float, float]]:
        """计算六边形的6个顶点坐标（相对于中心点）"""
        points = []
        if orientation == HexOrientation.FLAT_TOP:
            # 平顶六边形，从0度开始
            start_angle = 0
        else:
            # 尖顶六边形，从30度开始
            start_angle = 30

        for i in range(6):
            angle_deg = 60 * i + start_angle
            angle_rad = math.radians(angle_deg)
            x = hex_size * math.cos(angle_rad)
            y = hex_size * math.sin(angle_rad)
            points.append((x, y))
        return points

    def _render_hex_tile(
        self,
        tile_component: TileComponent,
        hex_size: float,
        orientation: HexOrientation = HexOrientation.FLAT_TOP,
    ) -> pygame.Surface:
        """渲染单个六边形格子"""
        # 计算六边形的顶点
        hex_points = self._calculate_hex_points(hex_size, orientation)

        # 计算六边形的边界框
        min_x = min(point[0] for point in hex_points)
        max_x = max(point[0] for point in hex_points)
        min_y = min(point[1] for point in hex_points)
        max_y = max(point[1] for point in hex_points)

        # 创建刚好包含六边形的表面
        surface_width = int(max_x - min_x) + 2  # 添加小的边距
        surface_height = int(max_y - min_y) + 2
        tile_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)

        # 调整顶点坐标到表面坐标系（居中）
        offset_x = -min_x + 1
        offset_y = -min_y + 1
        adjusted_points = [(x + offset_x, y + offset_y) for x, y in hex_points]

        # 获取地形颜色
        terrain_color = self.get_terrain_color(tile_component.terrain_type)

        # 绘制六边形
        pygame.draw.polygon(tile_surface, terrain_color, adjusted_points)

        # 绘制边框
        border_color = (60, 60, 60)
        pygame.draw.polygon(tile_surface, border_color, adjusted_points, 1)

        return tile_surface

    def _get_visible_hex_tiles(
        self, map_component: MapComponent, camera_comp: CameraComponent
    ) -> List[Tuple[HexCoordinate, TileComponent]]:
        """获取当前相机视野内可见的六边形格子"""
        visible_tiles = []

        # 获取相机可见区域
        visible_area = self._get_visible_area(camera_comp)
        left, top, right, bottom = visible_area

        # 遍历所有六边形格子
        for hex_coord_tuple, tile_entity in map_component.hex_entities.items():
            hex_coord = HexCoordinate(*hex_coord_tuple)
            tile_component = self.context.get_component(tile_entity, TileComponent)

            if tile_component:
                # 获取六边形的像素坐标
                pixel_x, pixel_y = hex_to_pixel(
                    hex_coord, map_component.hex_size, map_component.orientation
                )

                # 检查是否在可见区域内（添加一些余量）
                margin = map_component.hex_size * 2
                if (
                    left - margin <= pixel_x <= right + margin
                    and top - margin <= pixel_y <= bottom + margin
                ):
                    visible_tiles.append((hex_coord, tile_component))

        return visible_tiles

    def update(self, delta_time: float) -> None:
        """准备地图渲染数据"""
        camera_component = self._get_camera_component()
        if not camera_component:
            self.logger.warning("未找到相机组件，无法准备地图渲染数据")
            return

        map_component = self._get_map_component()
        if not map_component:
            return

        if map_component.map_type == "hexagonal":
            # 六边形地图渲染
            self._render_hexagonal_map(map_component, camera_component)
        else:
            # 原有的方形地图渲染逻辑
            # print("渲染方形地图")
            # print("map_component:", map_component)
            self._render_square_map(map_component, camera_component)

    def _render_hexagonal_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染六边形地图"""
        # 获取可见的六边形格子
        visible_tiles = self._get_visible_hex_tiles(map_component, camera_component)

        # 计算实际绘制尺寸（考虑缩放）
        draw_size = map_component.hex_size * camera_component.zoom

        for hex_coord, tile_component in visible_tiles:
            # 获取六边形的像素坐标
            pixel_x, pixel_y = hex_to_pixel(
                hex_coord, map_component.hex_size, map_component.orientation
            )

            # 创建缓存键（包含方向信息）
            cache_key = (
                "hex",
                tile_component.terrain_type,
                int(draw_size),
                tile_component.elevation // 10,
                self.use_textures,
                map_component.orientation.value,  # 添加方向到缓存键
            )

            if cache_key not in self.tile_cache:
                self.tile_cache[cache_key] = self._render_hex_tile(
                    tile_component, draw_size, map_component.orientation
                )

            # 将世界坐标转换为屏幕坐标
            screen_x, screen_y = self._world_to_screen(
                pixel_x, pixel_y, camera_component
            )

            # 获取渲染表面的尺寸并居中
            tile_surface = self.tile_cache[cache_key]
            surface_width = tile_surface.get_width()
            surface_height = tile_surface.get_height()

            # 调整渲染位置以居中六边形
            screen_pos = (screen_x - surface_width // 2, screen_y - surface_height // 2)

            # 渲染六边形格子
            self.context.render_manager.draw_surface(
                self.tile_cache[cache_key],
                screen_pos,
                RenderLayer.MAP.value,
            )

    def _render_square_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染方形地图（原有逻辑）"""
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
            for x in range(start_x, end_y + 1):
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
                            "square",
                            tile_component.terrain_type,
                            draw_size,
                            tile_component.elevation // 10,
                            tile_component.has_road,
                            tile_component.has_river,
                            tile_component.has_bridge,
                            self.use_textures,
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

    def _render_tile_with_color(
        self, tile_component: TileComponent, tile_surface: pygame.Surface, size: int
    ) -> None:
        """使用颜色渲染格子"""
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

    def _render_hex_tile(
        self,
        tile_component: TileComponent,
        hex_size: float,
        orientation: HexOrientation = HexOrientation.FLAT_TOP,
    ) -> pygame.Surface:
        """渲染单个六边形格子"""
        # 计算六边形的顶点
        hex_points = self._calculate_hex_points(hex_size, orientation)

        # 计算六边形的边界框
        min_x = min(point[0] for point in hex_points)
        max_x = max(point[0] for point in hex_points)
        min_y = min(point[1] for point in hex_points)
        max_y = max(point[1] for point in hex_points)

        # 创建刚好包含六边形的表面
        surface_width = int(max_x - min_x) + 2  # 添加小的边距
        surface_height = int(max_y - min_y) + 2
        tile_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)

        # 调整顶点坐标到表面坐标系（居中）
        offset_x = -min_x + 1
        offset_y = -min_y + 1
        adjusted_points = [(x + offset_x, y + offset_y) for x, y in hex_points]

        # 获取地形颜色
        terrain_color = self.get_terrain_color(tile_component.terrain_type)

        # 绘制六边形
        pygame.draw.polygon(tile_surface, terrain_color, adjusted_points)

        # 绘制边框
        border_color = (60, 60, 60)
        pygame.draw.polygon(tile_surface, border_color, adjusted_points, 1)

        return tile_surface

    def _get_visible_hex_tiles(
        self, map_component: MapComponent, camera_comp: CameraComponent
    ) -> List[Tuple[HexCoordinate, TileComponent]]:
        """获取当前相机视野内可见的六边形格子"""
        visible_tiles = []

        # 获取相机可见区域
        visible_area = self._get_visible_area(camera_comp)
        left, top, right, bottom = visible_area

        # 遍历所有六边形格子
        for hex_coord_tuple, tile_entity in map_component.hex_entities.items():
            hex_coord = HexCoordinate(*hex_coord_tuple)
            tile_component = self.context.get_component(tile_entity, TileComponent)

            if tile_component:
                # 获取六边形的像素坐标
                pixel_x, pixel_y = hex_to_pixel(
                    hex_coord, map_component.hex_size, map_component.orientation
                )

                # 检查是否在可见区域内（添加一些余量）
                margin = map_component.hex_size * 2
                if (
                    left - margin <= pixel_x <= right + margin
                    and top - margin <= pixel_y <= bottom + margin
                ):
                    visible_tiles.append((hex_coord, tile_component))

        return visible_tiles

    def _render_hexagonal_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染六边形地图"""
        # 获取可见的六边形格子
        visible_tiles = self._get_visible_hex_tiles(map_component, camera_component)

        # 计算实际绘制尺寸（考虑缩放）
        draw_size = map_component.hex_size * camera_component.zoom

        for hex_coord, tile_component in visible_tiles:
            # 获取六边形的像素坐标
            pixel_x, pixel_y = hex_to_pixel(
                hex_coord, map_component.hex_size, map_component.orientation
            )

            # 创建缓存键（包含方向信息）
            cache_key = (
                "hex",
                tile_component.terrain_type,
                int(draw_size),
                tile_component.elevation // 10,
                self.use_textures,
                map_component.orientation.value,  # 添加方向到缓存键
            )

            if cache_key not in self.tile_cache:
                self.tile_cache[cache_key] = self._render_hex_tile(
                    tile_component, draw_size, map_component.orientation
                )

            # 将世界坐标转换为屏幕坐标
            screen_x, screen_y = self._world_to_screen(
                pixel_x, pixel_y, camera_component
            )

            # 获取渲染表面的尺寸并居中
            tile_surface = self.tile_cache[cache_key]
            surface_width = tile_surface.get_width()
            surface_height = tile_surface.get_height()

            # 调整渲染位置以居中六边形
            screen_pos = (screen_x - surface_width // 2, screen_y - surface_height // 2)

            # 渲染六边形格子
            self.context.render_manager.draw_surface(
                self.tile_cache[cache_key],
                screen_pos,
                RenderLayer.MAP.value,
            )

    def _render_square_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染方形地图（原有逻辑）"""
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
            for x in range(start_x, end_y + 1):
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
                            "square",
                            tile_component.terrain_type,
                            draw_size,
                            tile_component.elevation // 10,
                            tile_component.has_road,
                            tile_component.has_river,
                            tile_component.has_bridge,
                            self.use_textures,
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

    def _render_tile_with_color(
        self, tile_component: TileComponent, tile_surface: pygame.Surface, size: int
    ) -> None:
        """使用颜色渲染格子"""
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

    def _render_hex_tile(
        self,
        tile_component: TileComponent,
        hex_size: float,
        orientation: HexOrientation = HexOrientation.FLAT_TOP,
    ) -> pygame.Surface:
        """渲染单个六边形格子"""
        # 计算六边形的顶点
        hex_points = self._calculate_hex_points(hex_size, orientation)

        # 计算六边形的边界框
        min_x = min(point[0] for point in hex_points)
        max_x = max(point[0] for point in hex_points)
        min_y = min(point[1] for point in hex_points)
        max_y = max(point[1] for point in hex_points)

        # 创建刚好包含六边形的表面
        surface_width = int(max_x - min_x) + 2  # 添加小的边距
        surface_height = int(max_y - min_y) + 2
        tile_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)

        # 调整顶点坐标到表面坐标系（居中）
        offset_x = -min_x + 1
        offset_y = -min_y + 1
        adjusted_points = [(x + offset_x, y + offset_y) for x, y in hex_points]

        # 获取地形颜色
        terrain_color = self.get_terrain_color(tile_component.terrain_type)

        # 绘制六边形
        pygame.draw.polygon(tile_surface, terrain_color, adjusted_points)

        # 绘制边框
        border_color = (60, 60, 60)
        pygame.draw.polygon(tile_surface, border_color, adjusted_points, 1)

        return tile_surface

    def _render_tile(self, tile_component: TileComponent, size: int) -> pygame.Surface:
        """渲染单个格子，考虑海拔高度、道路和水系特性"""
        # 创建格子表面 - 使用比请求的尺寸略大的表面以消除缩放时的边缘缝隙Add commentMore actions
        extra_pixel = 1  # 额外添加1像素来避免边缘出现缝隙
        actual_size = size + extra_pixel
        tile_surface = pygame.Surface((actual_size, actual_size), pygame.SRCALPHA)

        # 尝试使用贴图渲染
        if self.use_textures and tile_component.terrain_type in self.terrain_textures:
            texture = self.terrain_textures[tile_component.terrain_type]
            if texture is not None:
                # 缩放贴图到格子大小
                scaled_texture = pygame.transform.scale(
                    texture, (actual_size, actual_size)
                )
                tile_surface.blit(scaled_texture, (0, 0))

                # 根据海拔调整亮度
                # if tile_component.terrain_type not in [
                #     TerrainType.RIVER,
                #     TerrainType.LAKE,
                #     TerrainType.OCEAN,
                #     TerrainType.WETLAND,
                # ]:
                #     elevation_factor = min(
                #         1.0, tile_component.elevation / 100.0
                #     )  # 归一化到0-1
                #     brightness_factor = 0.7 + (
                #         elevation_factor * 0.6
                #     )  # 0.7-1.3范围内的亮度

                #     # 创建一个调整亮度的表面
                #     brightness_surface = pygame.Surface(
                #         (actual_size, actual_size), pygame.SRCALPHA
                #     )
                #     if brightness_factor < 1.0:
                #         # 变暗
                #         brightness_surface.fill(
                #             (0, 0, 0, int((1.0 - brightness_factor) * 255))
                #         )
                #     else:
                #         # 变亮
                #         brightness_surface.fill(
                #             (255, 255, 255, int((brightness_factor - 1.0) * 100))
                #         )

                #     # 应用亮度调整
                #     tile_surface.blit(
                #         brightness_surface,
                #         (0, 0),
                #         special_flags=pygame.BLEND_RGBA_MULT
                #         if brightness_factor < 1.0
                #         else pygame.BLEND_RGBA_ADD,
                #     )
            else:
                # 如果没有贴图，使用颜色渲染
                self._render_tile_with_color(tile_component, tile_surface, size)
        else:
            # 使用颜色渲染
            self._render_tile_with_color(tile_component, tile_surface, size)

        return tile_surface

    def _get_visible_hex_tiles(
        self, map_component: MapComponent, camera_comp: CameraComponent
    ) -> List[Tuple[HexCoordinate, TileComponent]]:
        """获取当前相机视野内可见的六边形格子"""
        visible_tiles = []

        # 获取相机可见区域
        visible_area = self._get_visible_area(camera_comp)
        left, top, right, bottom = visible_area

        # 遍历所有六边形格子
        for hex_coord_tuple, tile_entity in map_component.hex_entities.items():
            hex_coord = HexCoordinate(*hex_coord_tuple)
            tile_component = self.context.get_component(tile_entity, TileComponent)

            if tile_component:
                # 获取六边形的像素坐标
                pixel_x, pixel_y = hex_to_pixel(
                    hex_coord, map_component.hex_size, map_component.orientation
                )

                # 检查是否在可见区域内（添加一些余量）
                margin = map_component.hex_size * 2
                if (
                    left - margin <= pixel_x <= right + margin
                    and top - margin <= pixel_y <= bottom + margin
                ):
                    visible_tiles.append((hex_coord, tile_component))

        return visible_tiles

    def _render_hexagonal_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染六边形地图"""
        # 获取可见的六边形格子
        visible_tiles = self._get_visible_hex_tiles(map_component, camera_component)

        # 计算实际绘制尺寸（考虑缩放）
        draw_size = map_component.hex_size * camera_component.zoom

        for hex_coord, tile_component in visible_tiles:
            # 获取六边形的像素坐标
            pixel_x, pixel_y = hex_to_pixel(
                hex_coord, map_component.hex_size, map_component.orientation
            )

            # 创建缓存键（包含方向信息）
            cache_key = (
                "hex",
                tile_component.terrain_type,
                int(draw_size),
                tile_component.elevation // 10,
                self.use_textures,
                map_component.orientation.value,  # 添加方向到缓存键
            )

            if cache_key not in self.tile_cache:
                self.tile_cache[cache_key] = self._render_hex_tile(
                    tile_component, draw_size, map_component.orientation
                )

            # 将世界坐标转换为屏幕坐标
            screen_x, screen_y = self._world_to_screen(
                pixel_x, pixel_y, camera_component
            )

            # 获取渲染表面的尺寸并居中
            tile_surface = self.tile_cache[cache_key]
            surface_width = tile_surface.get_width()
            surface_height = tile_surface.get_height()

            # 调整渲染位置以居中六边形
            screen_pos = (screen_x - surface_width // 2, screen_y - surface_height // 2)

            # 渲染六边形格子
            self.context.render_manager.draw_surface(
                self.tile_cache[cache_key],
                screen_pos,
                RenderLayer.MAP.value,
            )

    def _render_square_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染方形地图（原有逻辑）"""
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
            for x in range(start_x, end_y + 1):
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
                            "square",
                            tile_component.terrain_type,
                            draw_size,
                            tile_component.elevation // 10,
                            tile_component.has_road,
                            tile_component.has_river,
                            tile_component.has_bridge,
                            self.use_textures,
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

    def _render_tile_with_color(
        self, tile_component: TileComponent, tile_surface: pygame.Surface, size: int
    ) -> None:
        """使用颜色渲染格子"""
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

    def _render_hex_tile(
        self,
        tile_component: TileComponent,
        hex_size: float,
        orientation: HexOrientation = HexOrientation.FLAT_TOP,
    ) -> pygame.Surface:
        """渲染单个六边形格子"""
        # 计算六边形的顶点
        hex_points = self._calculate_hex_points(hex_size, orientation)

        # 计算六边形的边界框
        min_x = min(point[0] for point in hex_points)
        max_x = max(point[0] for point in hex_points)
        min_y = min(point[1] for point in hex_points)
        max_y = max(point[1] for point in hex_points)

        # 创建刚好包含六边形的表面
        surface_width = int(max_x - min_x) + 2  # 添加小的边距
        surface_height = int(max_y - min_y) + 2
        tile_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)

        # 调整顶点坐标到表面坐标系（居中）
        offset_x = -min_x + 1
        offset_y = -min_y + 1
        adjusted_points = [(x + offset_x, y + offset_y) for x, y in hex_points]

        # 获取地形颜色
        terrain_color = self.get_terrain_color(tile_component.terrain_type)

        # 绘制六边形
        pygame.draw.polygon(tile_surface, terrain_color, adjusted_points)

        # 绘制边框
        border_color = (60, 60, 60)
        pygame.draw.polygon(tile_surface, border_color, adjusted_points, 1)

        return tile_surface

    def _get_visible_hex_tiles(
        self, map_component: MapComponent, camera_comp: CameraComponent
    ) -> List[Tuple[HexCoordinate, TileComponent]]:
        """获取当前相机视野内可见的六边形格子"""
        visible_tiles = []

        # 获取相机可见区域
        visible_area = self._get_visible_area(camera_comp)
        left, top, right, bottom = visible_area

        # 遍历所有六边形格子
        for hex_coord_tuple, tile_entity in map_component.hex_entities.items():
            hex_coord = HexCoordinate(*hex_coord_tuple)
            tile_component = self.context.get_component(tile_entity, TileComponent)

            if tile_component:
                # 获取六边形的像素坐标
                pixel_x, pixel_y = hex_to_pixel(
                    hex_coord, map_component.hex_size, map_component.orientation
                )

                # 检查是否在可见区域内（添加一些余量）
                margin = map_component.hex_size * 2
                if (
                    left - margin <= pixel_x <= right + margin
                    and top - margin <= pixel_y <= bottom + margin
                ):
                    visible_tiles.append((hex_coord, tile_component))

        return visible_tiles

    def _render_hexagonal_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染六边形地图"""
        # 获取可见的六边形格子
        visible_tiles = self._get_visible_hex_tiles(map_component, camera_component)

        # 计算实际绘制尺寸（考虑缩放）
        draw_size = map_component.hex_size * camera_component.zoom

        for hex_coord, tile_component in visible_tiles:
            # 获取六边形的像素坐标
            pixel_x, pixel_y = hex_to_pixel(
                hex_coord, map_component.hex_size, map_component.orientation
            )

            # 创建缓存键（包含方向信息）
            cache_key = (
                "hex",
                tile_component.terrain_type,
                int(draw_size),
                tile_component.elevation // 10,
                self.use_textures,
                map_component.orientation.value,  # 添加方向到缓存键
            )

            if cache_key not in self.tile_cache:
                self.tile_cache[cache_key] = self._render_hex_tile(
                    tile_component, draw_size, map_component.orientation
                )

            # 将世界坐标转换为屏幕坐标
            screen_x, screen_y = self._world_to_screen(
                pixel_x, pixel_y, camera_component
            )

            # 获取渲染表面的尺寸并居中
            tile_surface = self.tile_cache[cache_key]
            surface_width = tile_surface.get_width()
            surface_height = tile_surface.get_height()

            # 调整渲染位置以居中六边形
            screen_pos = (screen_x - surface_width // 2, screen_y - surface_height // 2)

            # 渲染六边形格子
            self.context.render_manager.draw_surface(
                self.tile_cache[cache_key],
                screen_pos,
                RenderLayer.MAP.value,
            )

    def _render_square_map(
        self, map_component: MapComponent, camera_component: CameraComponent
    ):
        """渲染方形地图（原有逻辑）"""
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
            for x in range(start_x, end_y + 1):
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
                            "square",
                            tile_component.terrain_type,
                            draw_size,
                            tile_component.elevation // 10,
                            tile_component.has_road,
                            tile_component.has_river,
                            tile_component.has_bridge,
                            self.use_textures,
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
