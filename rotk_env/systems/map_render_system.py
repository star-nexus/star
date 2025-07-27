"""
地图渲染系统 - 负责地图、地形和战争迷雾的渲染
"""

import pygame
import os
import random
from typing import Tuple, Set, List, Dict, Optional
from framework import System, RMS
from ..components import (
    MapData,
    Terrain,
    GameState,
    FogOfWar,
    HexPosition,
    Unit,
    Camera,
    UIState,
)
from ..prefabs.config import GameConfig, TerrainType, HexOrientation
from ..utils.hex_utils import HexConverter


class MapRenderSystem(System):
    """地图渲染系统"""

    def __init__(self):
        super().__init__(priority=1)  # 最低优先级，最先渲染（底层）
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.terrain_textures: Dict[TerrainType, List[pygame.Surface]] = {}
        self.tile_texture_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.texture_loaded = False

    def initialize(self, world) -> None:
        """初始化地图渲染系统"""
        self.world = world
        self._load_terrain_textures()

    def _load_terrain_textures(self) -> None:
        """加载地形贴图"""
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
                            # 缩放贴图到合适的大小
                            hex_size = int(GameConfig.HEX_SIZE * 10)
                            # texture = self.load_seamless_hex_texture(
                            #     texture_path, hex_size
                            # )
                            texture = pygame.transform.scale(
                                texture, (hex_size, hex_size)
                            )
                            self.terrain_textures[terrain_type].append(texture)
                        except pygame.error as e:
                            print(f"警告：无法加载贴图 {texture_path}: {e}")

        # 检查加载结果
        loaded_count = sum(len(textures) for textures in self.terrain_textures.values())
        if loaded_count > 0:
            self.texture_loaded = True
            print(f"成功加载 {loaded_count} 个地形贴图")
        else:
            print("警告：未加载任何地形贴图，将使用颜色渲染")

    def load_seamless_hex_texture(self, texture_path, hex_size):
        """加载六边形纹理并创建无缝贴合版本"""
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

        # 创建精确尺寸的表面 - 贴图 是 flat top,所以选择 R 位 width
        final_texture = pygame.Surface((hex_width, hex_width), pygame.SRCALPHA)
        final_texture.fill((0, 0, 0, 0))  # 透明背景

        # 复制不透明部分到新表面
        final_texture.blit(mask_surface, (0, 0), (min_x, min_y, hex_width, hex_height))

        # 计算缩放比例（保持六边形比例）
        scale_factor = min(hex_size / hex_width, hex_size / hex_height)
        new_width = int(hex_width * scale_factor)
        new_height = int(hex_height * scale_factor)
        # 等比例

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
        """订阅事件（地图渲染系统不需要订阅事件）"""
        pass

    def set_hex_orientation(self, orientation: HexOrientation) -> None:
        """设置六边形方向"""
        if self.hex_converter.orientation != orientation:
            self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)
            # 清除贴图缓存，因为六边形形状改变了
            self.tile_texture_cache.clear()
            print(f"六边形方向已切换为: {orientation.value}")

    def toggle_hex_orientation(self) -> None:
        """切换六边形方向"""
        current = self.hex_converter.orientation
        new_orientation = (
            HexOrientation.FLAT_TOP
            if current == HexOrientation.POINTY_TOP
            else HexOrientation.POINTY_TOP
        )
        self.set_hex_orientation(new_orientation)

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

            # 尝试获取地形贴图
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture and self.texture_loaded:
                # 使用贴图渲染
                self._render_hex_with_texture(texture, screen_x, screen_y, zoom)
            else:
                # 使用颜色渲染（后备方案）
                self._render_hex_with_color(
                    terrain.terrain_type, q, r, camera_offset, zoom
                )

    def _render_hex_with_texture(
        self, texture: pygame.Surface, center_x: float, center_y: float, zoom: float
    ):
        """使用贴图渲染六边形"""
        # 缩放贴图
        scaled_size = int(GameConfig.HEX_SIZE * 2 * zoom)
        if scaled_size <= 0:
            return

        scaled_texture = pygame.transform.scale(texture, (scaled_size, scaled_size))

        # 计算贴图位置（居中）
        texture_x = center_x - scaled_size // 2
        texture_y = center_y - scaled_size // 2

        # 绘制贴图
        RMS.draw(scaled_texture, (texture_x, texture_y))

    def _render_hex_with_color(
        self,
        terrain_type: TerrainType,
        q: int,
        r: int,
        camera_offset: List[float],
        zoom: float,
    ):
        """使用颜色渲染六边形（后备方案）"""
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

    def _render_fog_of_war(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染战争迷雾 - 三种状态：未探索(黑色)、已探索但非视野(半透明黑色)、当前视野(绿色轮廓)"""
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
        visible_tiles = fog_of_war.faction_vision.get(view_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(view_faction, set())

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
                # RMS.polygon(GameConfig.FOG_EXPLORED_COLOR, screen_corners)
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
                pass

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
