"""
小地图系统
"""

import pygame
from typing import Tuple, Optional
from framework import System, World, RMS, EBS, MouseButtonDownEvent
from ..components import (
    MiniMap,
    MapData,
    Camera,
    Terrain,
    HexPosition,
    Unit,
)
from ..prefabs.config import GameConfig, HexOrientation
from ..utils.hex_utils import HexConverter


class MiniMapSystem(System):
    """小地图系统 - 处理小地图的渲染和交互"""

    def __init__(self):
        super().__init__(priority=5)  # 在主渲染之前
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

    def initialize(self, world: World) -> None:
        """初始化系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件"""
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def update(self, delta_time: float) -> None:
        """更新小地图"""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible:
            return

        self._render_minimap(minimap)

    def _render_minimap(self, minimap: MiniMap):
        """渲染小地图"""
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data:
            return

        # 获取小地图矩形区域
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        # 创建小地图表面
        minimap_surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
        minimap_surface.fill((0, 0, 0, minimap.background_alpha))

        # 计算地图边界
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        # 渲染地形（如果启用）
        if minimap.show_terrain:
            self._render_terrain(
                minimap_surface, minimap, map_data, min_q, min_r, map_width, map_height
            )

        # 渲染单位（如果启用）
        if minimap.show_units:
            self._render_units(
                minimap_surface, minimap, min_q, min_r, map_width, map_height
            )

        # 渲染摄像机视口（如果启用）
        if minimap.show_camera_viewport and camera:
            self._render_camera_viewport(
                minimap_surface, minimap, camera, min_q, min_r, map_width, map_height
            )

        # 渲染边框
        pygame.draw.rect(
            minimap_surface,
            minimap.border_color,
            (0, 0, rect_w, rect_h),
            minimap.border_width,
        )

        # 绘制到主屏幕
        RMS.draw(minimap_surface, (rect_x, rect_y))

    def _get_screen_rect(self, minimap: MiniMap) -> Tuple[int, int, int, int]:
        """获取小地图在屏幕上的矩形区域"""
        x, y = minimap.position
        # 移动小地图在屏幕右上角
        rect_x = GameConfig.WINDOW_WIDTH - minimap.width - x
        return (rect_x, y, minimap.width, minimap.height)

    def _render_terrain(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        map_data: MapData,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """渲染小地图地形"""
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 计算在小地图中的位置
            rel_x = (q - min_q) / map_width
            rel_y = (r - min_r) / map_height

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # 根据地形类型选择颜色
            terrain_colors = {
                "plain": (144, 238, 144),  # 浅绿色
                "forest": (34, 139, 34),  # 深绿色
                "mountain": (139, 69, 19),  # 棕色
                "water": (70, 130, 180),  # 钢蓝色
                "city": (255, 215, 0),  # 金色
                "hill": (205, 133, 63),  # 秘鲁色
            }

            color = terrain_colors.get(terrain.terrain_type.value, (128, 128, 128))

            # 绘制一个小方块代表地形
            tile_size = max(1, int(minimap.scale * 10))
            pygame.draw.rect(surface, color, (pixel_x, pixel_y, tile_size, tile_size))

    def _render_units(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """渲染小地图单位"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if not pos or not unit:
                continue

            # 计算在小地图中的位置
            rel_x = (pos.col - min_q) / map_width
            rel_y = (pos.row - min_r) / map_height

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # 根据阵营选择颜色
            faction_colors = {
                "wei": (255, 0, 0),  # 红色
                "shu": (0, 255, 0),  # 绿色
                "wu": (0, 0, 255),  # 蓝色
            }

            color = faction_colors.get(unit.faction.value, (255, 255, 255))

            # 绘制单位点
            unit_size = max(2, int(minimap.scale * 15))
            pygame.draw.circle(surface, color, (pixel_x, pixel_y), unit_size)

    def _render_camera_viewport(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        camera: Camera,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """渲染小地图摄像机视口"""
        # 计算当前摄像机在世界坐标中看到的区域
        camera_offset = camera.get_offset()

        # 估算视口覆盖的hex范围（简化计算）
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        hex_size = GameConfig.HEX_SIZE

        # 将屏幕中心转换为hex坐标
        center_world_x = -camera_offset[0] + screen_width // 2
        center_world_y = -camera_offset[1] + screen_height // 2
        center_q, center_r = self.hex_converter.pixel_to_hex(
            center_world_x, center_world_y
        )

        # 估算视口大小（hex单位）
        viewport_hex_width = screen_width // (hex_size * 1.5)
        viewport_hex_height = screen_height // (hex_size * 0.866)

        # 计算视口在小地图中的位置和大小
        viewport_rel_x = (center_q - viewport_hex_width // 2 - min_q) / map_width
        viewport_rel_y = (center_r - viewport_hex_height // 2 - min_r) / map_height
        viewport_rel_w = viewport_hex_width / map_width
        viewport_rel_h = viewport_hex_height / map_height

        viewport_x = int(viewport_rel_x * minimap.width)
        viewport_y = int(viewport_rel_y * minimap.height)
        viewport_w = int(viewport_rel_w * minimap.width)
        viewport_h = int(viewport_rel_h * minimap.height)

        # 绘制视口框
        pygame.draw.rect(
            surface,
            (255, 255, 255),
            (viewport_x, viewport_y, viewport_w, viewport_h),
            2,
        )

    def handle_click(self, mouse_pos: Tuple[int, int]) -> bool:
        """处理小地图点击，返回是否点击了小地图"""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible or not minimap.clickable:
            return False

        # 检查是否点击了小地图区域
        if not self._is_point_inside(minimap, mouse_pos):
            return False

        # 转换为小地图内的相对坐标
        rel_pos = self._screen_to_minimap(minimap, mouse_pos)
        if not rel_pos:
            return False

        # 将相对坐标转换为世界坐标
        world_pos = self._minimap_to_world_pos(rel_pos)
        if world_pos:
            # 移动摄像机到目标位置
            self._move_camera_to_position(world_pos)

        return True

    def _is_point_inside(self, minimap: MiniMap, screen_pos: Tuple[int, int]) -> bool:
        """检查屏幕坐标是否在小地图范围内"""
        x, y = screen_pos
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)
        return rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + rect_h

    def _screen_to_minimap(
        self, minimap: MiniMap, screen_pos: Tuple[int, int]
    ) -> Optional[Tuple[float, float]]:
        """将屏幕坐标转换为小地图内的相对坐标(0-1范围)"""
        if not self._is_point_inside(minimap, screen_pos):
            return None

        x, y = screen_pos
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        rel_x = (x - rect_x) / rect_w
        rel_y = (y - rect_y) / rect_h

        return (rel_x, rel_y)

    def _minimap_to_world_pos(
        self, rel_pos: Tuple[float, float]
    ) -> Optional[Tuple[int, int]]:
        """将小地图相对坐标转换为世界hex坐标"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        # 计算地图边界
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        # 转换为hex坐标
        rel_x, rel_y = rel_pos
        target_q = min_q + rel_x * (max_q - min_q)
        target_r = min_r + rel_y * (max_r - min_r)

        return (int(target_q), int(target_r))

    def _move_camera_to_position(self, hex_pos: Tuple[int, int]):
        """移动摄像机到指定hex坐标"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        q, r = hex_pos

        # 将hex坐标转换为世界像素坐标
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

        # 设置摄像机偏移，使目标位置居中显示
        camera_x = GameConfig.WINDOW_WIDTH // 2 - world_x
        camera_y = GameConfig.WINDOW_HEIGHT // 2 - world_y

        camera.set_offset(camera_x, camera_y)

    def _handle_mouse_click(self, event: MouseButtonDownEvent):
        """处理小地图点击事件"""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible:
            return

        # 只处理左键点击
        if event.button != 1:
            return

        # 检查点击是否在小地图区域内
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        mouse_x, mouse_y = event.pos
        if not (
            rect_x <= mouse_x <= rect_x + rect_w
            and rect_y <= mouse_y <= rect_y + rect_h
        ):
            return

        # 将屏幕坐标转换为小地图内的相对坐标
        relative_x = mouse_x - rect_x
        relative_y = mouse_y - rect_y

        # 将相对坐标转换为地图坐标
        hex_pos = self._screen_to_hex(relative_x, relative_y, minimap)
        if hex_pos:
            # 移动摄像机到点击位置
            self._move_camera_to_position(hex_pos)

        # 只处理左键点击
        if event.button != 1:
            return

        # 检查点击是否在小地图区域内
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        mouse_x, mouse_y = event.pos
        if not (
            rect_x <= mouse_x <= rect_x + rect_w
            and rect_y <= mouse_y <= rect_y + rect_h
        ):
            return

        # 将屏幕坐标转换为小地图内的相对坐标
        relative_x = mouse_x - rect_x
        relative_y = mouse_y - rect_y

        # 将相对坐标转换为地图坐标
        hex_pos = self._screen_to_hex(relative_x, relative_y, minimap)
        if hex_pos:
            # 移动摄像机到点击位置
            self._move_camera_to_position(hex_pos)

    def _screen_to_hex(
        self, screen_x: int, screen_y: int, minimap: MiniMap
    ) -> Optional[Tuple[int, int]]:
        """将小地图屏幕坐标转换为六边形地图坐标"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        # 计算地图边界
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        # 获取小地图矩形
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        # 计算在地图上的相对位置（0到1）
        norm_x = screen_x / rect_w
        norm_y = screen_y / rect_h

        # 转换为六边形坐标
        hex_q = int(min_q + norm_x * map_width)
        hex_r = int(min_r + norm_y * map_height)

        # 确保坐标在有效范围内
        if (hex_q, hex_r) in map_data.tiles:
            return (hex_q, hex_r)

        return None
