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
        """渲染小地图 - 修复坐标边界计算"""
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data:
            return

        # 获取小地图矩形区域
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        # 创建小地图表面
        minimap_surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
        minimap_surface.fill((0, 0, 0, minimap.background_alpha))

        # 计算世界坐标边界（确保每次渲染都是最新的）
        self._calculate_world_bounds(map_data)

        # 计算地图边界（保持向后兼容，但不再用于主要计算）
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

    def _calculate_world_bounds(self, map_data: MapData):
        """计算世界坐标边界，用于正确的坐标映射"""
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for q, r in map_data.tiles.keys():
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            min_x = min(min_x, world_x)
            max_x = max(max_x, world_x)
            min_y = min(min_y, world_y)
            max_y = max(max_y, world_y)

        # 添加一些边距以确保所有内容都能显示
        padding = 50
        self._world_bounds = {
            "min_x": min_x - padding,
            "max_x": max_x + padding,
            "min_y": min_y - padding,
            "max_y": max_y + padding,
        }

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
        """渲染小地图地形 - 修复坐标转换"""
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 使用正确的六边形坐标转换
            # 将六边形坐标转换为世界像素坐标
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

            # 计算所有tile的世界坐标边界
            if not hasattr(self, "_world_bounds"):
                self._calculate_world_bounds(map_data)

            # 将世界坐标映射到小地图坐标
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # 确保坐标在有效范围内
            if 0 <= pixel_x < minimap.width and 0 <= pixel_y < minimap.height:
                # 根据地形类型选择颜色
                terrain_colors = {
                    "plain": (144, 238, 144),  # 浅绿色
                    "forest": (34, 139, 34),  # 深绿色
                    "mountain": (139, 69, 19),  # 棕色
                    "water": (70, 130, 180),  # 钢蓝色
                    "city": (255, 215, 0),  # 金色
                    "urban": (255, 215, 0),  # 金色（与city相同）
                    "hill": (205, 133, 63),  # 秘鲁色
                }

                color = terrain_colors.get(terrain.terrain_type.value, (128, 128, 128))

                # 绘制一个小方块代表地形
                tile_size = max(2, int(minimap.scale * 12))
                pygame.draw.rect(
                    surface, color, (pixel_x, pixel_y, tile_size, tile_size)
                )

    def _render_units(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """渲染小地图单位 - 修复坐标转换"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if not pos or not unit:
                continue

            # HexPosition 使用 col/row，需要转换为 q/r 坐标
            # 在六边形网格中，通常 col=q, row=r
            world_x, world_y = self.hex_converter.hex_to_pixel(pos.col, pos.row)

            # 确保世界边界已计算
            if not hasattr(self, "_world_bounds"):
                # 如果没有计算过，使用当前已知的地图数据重新计算
                map_data = self.world.get_singleton_component(MapData)
                if map_data:
                    self._calculate_world_bounds(map_data)
                else:
                    return

            # 将世界坐标映射到小地图坐标
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # 确保坐标在有效范围内
            if 0 <= pixel_x < minimap.width and 0 <= pixel_y < minimap.height:
                # 根据阵营选择颜色
                faction_colors = {
                    "wei": (255, 0, 0),  # 红色
                    "shu": (0, 255, 0),  # 绿色
                    "wu": (0, 0, 255),  # 蓝色
                }

                color = faction_colors.get(unit.faction.value, (255, 255, 255))

                # 绘制单位点
                unit_size = max(3, int(minimap.scale * 15))
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
        """渲染小地图摄像机视口 - 修复坐标转换"""
        # 计算当前摄像机在世界坐标中看到的区域
        camera_offset = camera.get_offset()

        # 估算视口覆盖的区域（使用世界坐标）
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # 摄像机视口的四个角（世界坐标）
        viewport_corners = [
            (-camera_offset[0], -camera_offset[1]),  # 左上
            (-camera_offset[0] + screen_width, -camera_offset[1]),  # 右上
            (-camera_offset[0], -camera_offset[1] + screen_height),  # 左下
            (
                -camera_offset[0] + screen_width,
                -camera_offset[1] + screen_height,
            ),  # 右下
        ]

        # 确保世界边界已计算
        if not hasattr(self, "_world_bounds"):
            map_data = self.world.get_singleton_component(MapData)
            if map_data:
                self._calculate_world_bounds(map_data)
            else:
                return

        # 将视口corners映射到小地图坐标
        minimap_corners = []
        for world_x, world_y in viewport_corners:
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)
            minimap_corners.append((pixel_x, pixel_y))

        # 计算视口矩形（使用边界框）
        min_x = min(corner[0] for corner in minimap_corners)
        max_x = max(corner[0] for corner in minimap_corners)
        min_y = min(corner[1] for corner in minimap_corners)
        max_y = max(corner[1] for corner in minimap_corners)

        viewport_x = max(0, min_x)
        viewport_y = max(0, min_y)
        viewport_w = min(minimap.width - viewport_x, max_x - min_x)
        viewport_h = min(minimap.height - viewport_y, max_y - min_y)

        # 绘制视口框
        if viewport_w > 0 and viewport_h > 0:
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
