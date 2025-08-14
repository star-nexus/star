"""
地图渲染系统
Map rendering system
"""

import pygame
import os
import random
import math
from typing import Tuple, Set, List, Dict, Optional
from framework import System, RMS
from ..components import (
    MapData,
    Terrain,
    TerritoryControl,
    GameState,
    FogOfWar,
    HexPosition,
    Unit,
    Camera,
    UIState,
)
from ..prefabs.config import GameConfig, TerrainType, HexOrientation, Faction
from ..utils.hex_utils import HexConverter


class MapRenderSystem(System):
    """整合高性能与完整功能的地图渲染系统"""

    def __init__(self):
        super().__init__(priority=1)  # 最低优先级，最先渲染（底层）
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

        # 地形贴图相关
        self.terrain_textures: Dict[TerrainType, List[pygame.Surface]] = {}
        self.tile_texture_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.texture_loaded = False

        # 性能优化缓存
        self.visible_tiles_cache: Set[Tuple[int, int]] = set()
        self.last_camera_pos = (0, 0)
        self.last_zoom = 1.0
        self.cache_tolerance = 50  # 摄像机移动容差

        # 战争迷雾优化
        self.fog_surface = None
        self.fog_dirty = True
        self.last_fog_hash = 0

        # 性能统计
        self.frame_count = 0
        self.render_calls_saved = 0

        print("[整合版] 地图渲染系统初始化 - 高性能+完整功能")

    def initialize(self, world) -> None:
        """初始化地图渲染系统"""
        self.world = world
        self._load_terrain_textures()

    def _load_terrain_textures(self) -> None:
        """加载地形贴图 - 保留v0的完整实现"""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "terrain"
        )

        if not os.path.exists(assets_path):
            print(f"警告：地形贴图目录不存在: {assets_path}")
            return

        # 初始化所有地形类型的贴图列表
        for terrain_type in TerrainType:
            self.terrain_textures[terrain_type] = []

        # 遍历所有地形类型目录
        for terrain_type in TerrainType:
            terrain_dir = os.path.join(assets_path, terrain_type.value)

            if os.path.exists(terrain_dir):
                # 加载该地形类型的所有贴图
                for filename in os.listdir(terrain_dir):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                        texture_path = os.path.join(terrain_dir, filename)
                        try:
                            texture = pygame.image.load(texture_path).convert_alpha()
                            # 预缩放贴图到标准大小，避免实时缩放
                            hex_size = GameConfig.HEX_SIZE * 2
                            texture = pygame.transform.scale(
                                texture, (hex_size, hex_size)
                            )
                            self.terrain_textures[terrain_type].append(texture)
                        except pygame.error as e:
                            print(f"警告：无法加载贴图 {texture_path}: {e}")

        loaded_count = sum(len(textures) for textures in self.terrain_textures.values())
        if loaded_count > 0:
            self.texture_loaded = True
            print(f"[整合版] 成功加载 {loaded_count} 个地形贴图")
        else:
            print("警告：未加载任何地形贴图，将使用颜色渲染")

    def load_seamless_hex_texture(self, texture_path, hex_size):
        """加载六边形纹理并创建无缝贴合版本 - 保留v0的高级功能"""
        # 加载原始纹理
        texture = pygame.image.load(texture_path).convert_alpha()

        # 创建掩模表面（用于提取不透明部分）
        mask_surface = pygame.Surface(texture.get_size(), pygame.SRCALPHA)
        mask_surface.fill((0, 0, 0, 0))  # 完全透明

        # 遍历每个像素，只复制不透明像素
        for x in range(texture.get_width()):
            for y in range(texture.get_height()):
                r, g, b, a = texture.get_at((x, y))
                if a > 0:  # 只处理不透明像素
                    mask_surface.set_at((x, y), (r, g, b, a))

        # 计算实际六边形边界
        min_x, min_y = mask_surface.get_width(), mask_surface.get_height()
        max_x, max_y = 0, 0

        # 找到不透明像素的边界
        for x in range(mask_surface.get_width()):
            for y in range(mask_surface.get_height()):
                if mask_surface.get_at((x, y))[3] > 0:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        # 计算六边形实际尺寸
        hex_width = max_x - min_x + 1
        hex_height = max_y - min_y + 1

        # 创建精确尺寸的表面 - 贴图是 flat top,所以选择 width
        final_texture = pygame.Surface((hex_width, hex_width), pygame.SRCALPHA)
        final_texture.fill((0, 0, 0, 0))  # 透明背景

        # 复制不透明部分到新表面
        final_texture.blit(mask_surface, (0, 0), (min_x, min_y, hex_width, hex_height))

        # 计算缩放比例（保持六边形比例）
        scale_factor = min(hex_size / hex_width, hex_size / hex_height)
        new_width = int(hex_width * scale_factor)
        new_height = int(hex_height * scale_factor)

        # 高质量缩放
        final_texture = pygame.transform.smoothscale(
            final_texture, (new_width, new_height)
        )

        return final_texture

    def _get_terrain_texture(
        self, terrain_type: TerrainType, tile_key: Tuple[int, int]
    ) -> Optional[pygame.Surface]:
        """获取地形贴图，如果有多个贴图则为每个tile固定选择一个"""
        if not self.texture_loaded or terrain_type not in self.terrain_textures:
            return None

        textures = self.terrain_textures[terrain_type]
        if not textures:
            return None

        # 如果该tile已经有缓存的贴图，直接返回
        if tile_key in self.tile_texture_cache:
            return self.tile_texture_cache[tile_key]

        # 使用tile坐标作为种子，确保每个tile的贴图选择是固定的
        random.seed(tile_key[0] * 10007 + tile_key[1] * 10009)
        selected_texture = random.choice(textures)

        # 缓存选择的贴图
        self.tile_texture_cache[tile_key] = selected_texture

        # 恢复随机种子
        random.seed()

        return selected_texture

    def subscribe_events(self):
        """订阅事件"""
        pass

    def set_hex_orientation(self, orientation: HexOrientation) -> None:
        """设置六边形方向 - 保留v0的完整功能"""
        if self.hex_converter.orientation != orientation:
            self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)
            # 清除贴图缓存，因为六边形形状改变了
            self.tile_texture_cache.clear()
            print(f"六边形方向已切换为: {orientation.value}")

    def toggle_hex_orientation(self) -> None:
        """切换六边形方向 - 保留v0的完整功能"""
        current = self.hex_converter.orientation
        new_orientation = (
            HexOrientation.FLAT_TOP
            if current == HexOrientation.POINTY_TOP
            else HexOrientation.POINTY_TOP
        )
        self.set_hex_orientation(new_orientation)

    def update(self, delta_time: float) -> None:
        """更新地图渲染 - 整合高性能可见区域优化与完整功能"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        self.frame_count += 1
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # **核心优化：智能可见区域计算**
        visible_tiles = self._get_visible_tiles_smart(camera_offset, zoom)

        # **分层渲染：地图 -> 领土边界 -> 战争迷雾 -> 坐标显示**
        self._render_map_optimized(visible_tiles, camera_offset, zoom)
        self._render_territory_boundaries_optimized(visible_tiles, camera_offset, zoom)
        self._render_fog_of_war_optimized(visible_tiles, camera_offset, zoom)
        self._render_coordinates_optimized(visible_tiles, camera_offset, zoom)

        # 性能统计
        if self.frame_count % 300 == 0:
            map_data = self.world.get_singleton_component(MapData)
            total_tiles = len(map_data.tiles) if map_data else 0
            tiles_saved = total_tiles - len(visible_tiles)
            print(
                f"[整合版] 帧数: {self.frame_count}, 可见格子: {len(visible_tiles)}/{total_tiles}, 节省: {tiles_saved}"
            )

    def _get_visible_tiles_smart(
        self, camera_offset: List[float], zoom: float
    ) -> Set[Tuple[int, int]]:
        """智能可见区域计算 - 使用缓存优化"""
        current_camera_pos = (camera_offset[0], camera_offset[1])

        # 检查是否可以使用缓存
        if (
            abs(current_camera_pos[0] - self.last_camera_pos[0]) < self.cache_tolerance
            and abs(current_camera_pos[1] - self.last_camera_pos[1])
            < self.cache_tolerance
            and abs(zoom - self.last_zoom) < 0.05
        ):
            return self.visible_tiles_cache

        # 重新计算可见区域
        visible_tiles = set()

        # 计算屏幕边界对应的世界坐标
        margin = GameConfig.HEX_SIZE * 2
        screen_bounds = {
            "left": (-camera_offset[0] - margin) / zoom,
            "right": (GameConfig.WINDOW_WIDTH - camera_offset[0] + margin) / zoom,
            "top": (-camera_offset[1] - margin) / zoom,
            "bottom": (GameConfig.WINDOW_HEIGHT - camera_offset[1] + margin) / zoom,
        }

        # 估算六边形坐标范围
        center_q = int(-camera_offset[0] / zoom / (GameConfig.HEX_SIZE * 1.5))
        center_r = int(-camera_offset[1] / zoom / (GameConfig.HEX_SIZE * 0.866))

        search_radius = max(
            int(GameConfig.WINDOW_WIDTH / zoom / GameConfig.HEX_SIZE) + 3,
            int(GameConfig.WINDOW_HEIGHT / zoom / GameConfig.HEX_SIZE) + 3,
        )

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return visible_tiles

        # 在估算范围内查找可见格子
        for q in range(center_q - search_radius, center_q + search_radius + 1):
            for r in range(center_r - search_radius, center_r + search_radius + 1):
                if (q, r) not in map_data.tiles:
                    continue

                # 检查这个格子是否在屏幕内
                world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

                if (
                    screen_bounds["left"] <= world_x <= screen_bounds["right"]
                    and screen_bounds["top"] <= world_y <= screen_bounds["bottom"]
                ):
                    visible_tiles.add((q, r))

        # 更新缓存
        self.visible_tiles_cache = visible_tiles
        self.last_camera_pos = current_camera_pos
        self.last_zoom = zoom

        return visible_tiles

    def _render_map_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float,
    ):
        """优化的地图渲染 - 只渲染可见格子，保留完整功能"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 只渲染可见的格子
        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if not tile_entity:
                continue

            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 尝试获取地形贴图
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture and self.texture_loaded:
                # 使用贴图渲染
                self._render_hex_with_texture(texture, screen_x, screen_y, zoom)

                # 如果是城市地形，添加特殊标记
                if terrain.terrain_type == TerrainType.CITY:
                    self._render_city_marker(q, r, camera_offset, zoom)
            else:
                # 使用颜色渲染（后备方案）
                self._render_hex_with_color(
                    terrain.terrain_type, q, r, camera_offset, zoom
                )

    def _render_hex_with_texture(
        self, texture: pygame.Surface, center_x: float, center_y: float, zoom: float
    ):
        """使用贴图渲染六边形 - 保留v0完整实现"""
        # 智能缩放：接近1.0时避免缩放
        if abs(zoom - 1.0) < 0.05:
            # 直接使用原尺寸
            texture_rect = texture.get_rect(center=(int(center_x), int(center_y)))
            RMS.draw(texture, texture_rect.topleft)
        else:
            # 需要缩放
            scaled_size = int(GameConfig.HEX_SIZE * 2 * zoom)
            if scaled_size <= 0:
                return

            scaled_texture = pygame.transform.scale(texture, (scaled_size, scaled_size))
            texture_x = center_x - scaled_size // 2
            texture_y = center_y - scaled_size // 2
            RMS.draw(scaled_texture, (texture_x, texture_y))

    def _render_hex_with_color(
        self,
        terrain_type: TerrainType,
        q: int,
        r: int,
        camera_offset: List[float],
        zoom: float,
    ):
        """使用颜色渲染六边形（后备方案） - 保留v0完整实现"""
        # 获取地形颜色
        terrain_color = GameConfig.TERRAIN_COLORS.get(terrain_type, (128, 128, 128))

        # 绘制六边形地块（应用缩放）
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
            for x, y in corners
        ]

        RMS.polygon(terrain_color, screen_corners)
        RMS.polygon((0, 0, 0), screen_corners, 1)

        # 如果是城市地形，添加特殊标记
        if terrain_type == TerrainType.CITY:
            self._render_city_marker(q, r, camera_offset, zoom)

    def _render_fog_of_war_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """优化的战争迷雾渲染 - 只处理可见格子，保留完整功能"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)

        if not game_state or not fog_of_war or not ui_state:
            return

        # 上帝视角模式：不渲染战争迷雾
        if ui_state.god_mode:
            return

        # 确定当前查看的阵营
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # 获取查看阵营的视野
        visible_faction_tiles = fog_of_war.faction_vision.get(view_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(view_faction, set())

        # 创建已探索但非视野区域的半透明迷雾层
        explored_fog_surface = pygame.Surface(
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
        )

        # **核心优化：只处理屏幕可见的格子**
        for q, r in visible_tiles:
            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            if (q, r) in visible_faction_tiles:
                # 当前视野区域：不绘制迷雾
                continue
            elif (q, r) in explored_tiles:
                # 已探索但非视野区域：绘制半透明黑色遮罩
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
            else:
                # 未探索区域：绘制完全黑色
                pygame.draw.polygon(
                    explored_fog_surface,
                    GameConfig.FOG_UNEXPLORED_COLOR,
                    screen_corners,
                )

        # 应用迷雾遮罩
        RMS.draw(explored_fog_surface, (0, 0))

        # 绘制视野区域的外边界绿色轮廓
        # self._render_vision_boundary_optimized(
        #     visible_faction_tiles, camera_offset, zoom
        # )

    def _render_vision_boundary_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """优化的视野边界渲染 - 基于单位位置绘制视野圆圈"""
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

            # 计算单位中心的屏幕坐标
            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = (center_world_x * zoom) + camera_offset[0]
            center_screen_y = (center_world_y * zoom) + camera_offset[1]

            # 屏幕边界检查（优化：只检查可能可见的单位）
            margin = 200 * zoom
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

            # 绘制单个视野圆圈
            circle_radius = int(vision_range * GameConfig.HEX_SIZE * 1.5 * zoom)
            RMS.circle(
                GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                (int(center_screen_x), int(center_screen_y)),
                circle_radius,
                2,
            )

    def _render_territory_boundaries_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """优化的领土边界渲染 - 只处理可见格子，保留完整功能"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 遍历可见的地图块，渲染领土控制信息
        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if not tile_entity:
                continue

            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control or not territory_control.controlling_faction:
                continue

            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 获取阵营颜色
            faction_color = self._get_faction_color(
                territory_control.controlling_faction
            )
            if not faction_color:
                continue

            # 渲染六边形边界
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            # 根据控制强度和工事等级调整边界样式
            border_width = self._get_border_width(territory_control)
            border_color = self._get_border_color(territory_control, faction_color)

            # 绘制领土边界
            RMS.polygon(border_color, screen_corners, border_width)

            # 如果有工事，添加特殊标记
            if territory_control.fortification_level > 0:
                self._render_fortification_marker(
                    screen_x, screen_y, territory_control, zoom
                )

    def _get_faction_color(self, faction: Faction) -> Optional[Tuple[int, int, int]]:
        """获取阵营颜色"""
        faction_colors = {
            Faction.WEI: (0, 100, 255),  # 蓝色
            Faction.SHU: (255, 50, 50),  # 红色
            Faction.WU: (50, 255, 50),  # 绿色
        }
        return faction_colors.get(faction)

    def _get_border_width(self, territory_control: TerritoryControl) -> int:
        """根据控制强度和工事等级确定边界宽度"""
        base_width = 2

        # 基于占领进度调整
        if territory_control.capture_progress >= 0.8:
            base_width += 1
        elif territory_control.capture_progress <= 0.3:
            base_width = max(1, base_width - 1)

        # 工事等级影响
        base_width += territory_control.fortification_level

        return min(base_width, 5)  # 最大宽度限制

    def _get_border_color(
        self, territory_control: TerritoryControl, faction_color: Tuple[int, int, int]
    ) -> Tuple[int, int, int]:
        """根据控制状态调整边界颜色"""
        r, g, b = faction_color

        # 根据占领进度调整亮度
        intensity = max(0.5, territory_control.capture_progress)  # 至少50%亮度

        # 调整颜色亮度
        r = int(r * (0.5 + 0.5 * intensity))
        g = int(g * (0.5 + 0.5 * intensity))
        b = int(b * (0.5 + 0.5 * intensity))

        return (min(255, r), min(255, g), min(255, b))

    def _render_fortification_marker(
        self,
        center_x: float,
        center_y: float,
        territory_control: TerritoryControl,
        zoom: float,
    ):
        """渲染工事标记 - 根据等级在六边形内嵌镶不同颜色边框"""
        if territory_control.fortification_level <= 0:
            return

        # 根据工事等级选择边框颜色
        fortification_colors = {
            1: (184, 115, 51),  # 铜色 (copper)
            2: (192, 192, 192),  # 银色 (silver)
            3: (255, 215, 0),  # 金色 (gold)
        }

        level = min(territory_control.fortification_level, 3)  # 最大3级
        border_color = fortification_colors.get(level, fortification_colors[1])

        # 使用hex_converter获取标准的六边形角点，确保与地图格子完全对应
        # 使用稍小的尺寸作为内嵌边框，但保持flat-top形状
        hex_size_scaled = GameConfig.HEX_SIZE * zoom * 0.9  # 内嵌90%大小，更紧贴

        # 直接使用hex_converter的方法来获取正确的flat-top六边形顶点
        # 先计算对应的q,r坐标（这里用0,0作为相对坐标）
        corners = self.hex_converter.get_hex_corners(0, 0)

        # 调整尺寸并应用到实际中心位置
        hex_points = []
        scale_factor = 0.9  # 内嵌90%大小

        for corner_x, corner_y in corners:
            # 缩放并移动到实际中心位置
            scaled_x = corner_x * scale_factor * zoom + center_x
            scaled_y = corner_y * scale_factor * zoom + center_y
            hex_points.append((int(scaled_x), int(scaled_y)))

        # 绘制工事边框 - 根据等级调整线宽，更明显
        border_width = max(
            3, int(4 * zoom * level)
        )  # 基础线宽从2增加到3，乘数从3增加到4

        # 绘制六边形工事边框
        RMS.polygon(border_color, hex_points, border_width)

    def _render_city_marker(
        self, q: int, r: int, camera_offset: List[float], zoom: float
    ):
        """渲染城市标记"""
        # 计算城市中心位置
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        center_x = (world_x * zoom) + camera_offset[0]
        center_y = (world_y * zoom) + camera_offset[1]

        # 城市标记大小
        marker_size = int(12 * zoom)
        city_color = (211, 211, 211)  # 浅灰色，表示城市建筑

        # 绘制城市标记（圆形）
        RMS.circle(
            city_color,
            (int(center_x), int(center_y)),
            marker_size,
        )
        RMS.circle(
            (0, 0, 0), (int(center_x), int(center_y)), marker_size, 2  # 黑色边框
        )

    def _render_coordinates_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """渲染坐标显示 - 只在可见格子上显示坐标"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.show_coordinates:
            return

        # 计算字体大小，根据缩放调整
        font_size = max(10, int(12 * zoom))

        # 避免在缩放过小时显示坐标（文字会太小看不清）
        if zoom < 0.3:
            return

        # 遍历可见的地图块，绘制坐标
        for q, r in visible_tiles:
            # 计算六边形中心的屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            center_x = (world_x * zoom) + camera_offset[0]
            center_y = (world_y * zoom) + camera_offset[1]

            # 创建坐标文本
            coord_text = f"({q},{r})"

            # 渲染坐标文本
            self._render_coordinate_text(coord_text, center_x, center_y, font_size)

    def _render_coordinate_text(self, text: str, x: float, y: float, font_size: int):
        """渲染坐标文本"""
        # 创建字体（如果没有字体库则使用默认字体）
        try:
            font = pygame.font.Font(None, font_size)
        except:
            font = pygame.font.SysFont("arial", font_size)

        # 渲染文本
        text_color = (255, 255, 255)  # 白色文字
        outline_color = (0, 0, 0)  # 黑色描边

        # 创建文本表面
        text_surface = font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=(int(x), int(y)))

        # 绘制描边（在四个方向绘制黑色文本）
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            outline_surface = font.render(text, True, outline_color)
            outline_rect = text_rect.copy()
            outline_rect.move_ip(dx, dy)
            RMS.draw(outline_surface, outline_rect.topleft)

        # 绘制主文本
        RMS.draw(text_surface, text_rect.topleft)
