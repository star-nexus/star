"""
地图渲染系统 - 负责地图、地形和战争迷雾的渲染
"""

import pygame
from typing import Tuple, Set, List
from framework_v2 import System, RMS
from ..components import (
    MapData,
    Terrain,
    GameState,
    FogOfWar,
    HexPosition,
    Unit,
    Camera,
)
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter


class MapRenderSystem(System):
    """地图渲染系统"""

    def __init__(self):
        super().__init__(priority=1)  # 最低优先级，最先渲染（底层）
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE)

    def initialize(self, world) -> None:
        """初始化地图渲染系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件（地图渲染系统不需要订阅事件）"""
        pass

    def update(self, delta_time: float) -> None:
        """更新地图渲染"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # 计算摄像机偏移
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # 渲染地图和战争迷雾
        self._render_map(camera_offset, zoom)
        self._render_fog_of_war(camera_offset, zoom)

    def _render_map(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染地图"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 遍历所有地图块
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 计算屏幕位置（应用缩放）
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 检查是否在屏幕范围内（考虑缩放）
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
                or screen_y < -hex_size_scaled
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
            ):
                continue

            # 获取地形颜色
            terrain_color = GameConfig.TERRAIN_COLORS.get(
                terrain.terrain_type, (128, 128, 128)
            )

            # 绘制六边形地块（应用缩放）
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            RMS.polygon(terrain_color, screen_corners)
            RMS.polygon((0, 0, 0), screen_corners, 1)

    def _render_fog_of_war(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染战争迷雾 - 三种状态：未探索(黑色)、已探索但非视野(半透明黑色)、当前视野(绿色轮廓)"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if not game_state or not fog_of_war or not game_state.current_player:
            return

        # 获取当前玩家的视野
        current_faction = game_state.current_player
        visible_tiles = fog_of_war.faction_vision.get(current_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(current_faction, set())

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 创建已探索但非视野区域的半透明迷雾层
        explored_fog_surface = pygame.Surface(
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
        )

        # 第一步：绘制未探索和已探索但非视野区域
        for (q, r), tile_entity in map_data.tiles.items():
            # 计算屏幕位置（应用缩放）
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 检查是否在屏幕范围内（考虑缩放）
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled * 2
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled * 2
                or screen_y < -hex_size_scaled * 2
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled * 2
            ):
                continue

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            if (q, r) in visible_tiles:
                # 当前视野区域：暂时跳过，稍后处理边界
                continue
            elif (q, r) in explored_tiles:
                # 已探索但非视野区域：绘制半透明黑色遮罩
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
            else:
                # 未探索区域：绘制完全黑色
                RMS.polygon(GameConfig.FOG_EXPLORED_COLOR, screen_corners)

        # 应用已探索区域的半透明遮罩
        RMS.draw(explored_fog_surface, (0, 0))

        # 第二步：绘制视野区域的外边界绿色轮廓
        self._render_vision_boundary(visible_tiles, camera_offset, zoom)

    def _render_vision_boundary(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """绘制以单位为中心的单个视野圆圈"""
        if not visible_tiles:
            return

        # 获取当前玩家的所有单位
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return

        current_faction = game_state.current_player

        # 为每个己方单位绘制一个视野圆圈
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position or unit.faction != current_faction:
                continue

            # 计算单位中心的屏幕坐标（应用缩放）
            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = (center_world_x * zoom) + camera_offset[0]
            center_screen_y = (center_world_y * zoom) + camera_offset[1]

            # 检查单位是否在屏幕范围内（考虑缩放）
            margin = 100 * zoom
            if (
                center_screen_x < -margin
                or center_screen_x > GameConfig.WINDOW_WIDTH + margin
                or center_screen_y < -margin
                or center_screen_y > GameConfig.WINDOW_HEIGHT + margin
            ):
                continue

            unit_stats = GameConfig.UNIT_STATS.get(unit.unit_type)
            if not unit_stats:
                continue

            vision_range = unit_stats.vision_range

            # 绘制单个视野圆圈（最大视野范围，应用缩放）
            circle_radius = int(vision_range * GameConfig.HEX_SIZE * 1.5 * zoom)

            # 绘制视野圆圈轮廓
            RMS.circle(
                GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                (int(center_screen_x), int(center_screen_y)),
                circle_radius,
                2,
            )
