"""
真正优化的地图渲染系统 - 解决根本性能问题
Truly optimized map rendering system - solving fundamental performance issues
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
    """真正优化的地图渲染系统"""

    def __init__(self):
        super().__init__(priority=1)
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        
        # 地形贴图相关
        self.terrain_textures: Dict[TerrainType, List[pygame.Surface]] = {}
        self.tile_texture_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.texture_loaded = False
        
        # 多级缓存系统
        self.zoom_caches: Dict[float, pygame.Surface] = {}  # 不同缩放级别的缓存
        self.current_zoom_level = 1.0
        self.zoom_tolerance = 0.1  # 缩放容差
        
        # 可见区域优化
        self.visible_tiles_cache: Set[Tuple[int, int]] = set()
        self.last_camera_pos = (0, 0)
        self.last_zoom = 1.0
        
        # 战争迷雾优化
        self.fog_surface = None
        self.fog_dirty = True
        self.last_fog_hash = 0
        
        # 性能统计
        self.frame_count = 0
        self.render_calls_saved = 0
        
        print("[真正优化版] 地图渲染系统初始化")

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
                for filename in os.listdir(terrain_dir):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                        texture_path = os.path.join(terrain_dir, filename)
                        try:
                            texture = pygame.image.load(texture_path).convert_alpha()
                            # 只加载一个合适大小的版本
                            hex_size = GameConfig.HEX_SIZE * 2
                            texture = pygame.transform.scale(texture, (hex_size, hex_size))
                            self.terrain_textures[terrain_type].append(texture)
                        except pygame.error as e:
                            print(f"警告：无法加载贴图 {texture_path}: {e}")

        loaded_count = sum(len(textures) for textures in self.terrain_textures.values())
        if loaded_count > 0:
            self.texture_loaded = True
            print(f"[真正优化版] 成功加载 {loaded_count} 个地形贴图")
        else:
            print("警告：未加载任何地形贴图，将使用颜色渲染")

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新地图渲染 - 真正优化版"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        self.frame_count += 1
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # **关键优化1：只渲染屏幕可见区域**
        visible_tiles = self._get_visible_tiles(camera_offset, zoom)
        
        # **关键优化2：直接渲染，避免复杂缓存**
        self._render_visible_tiles_direct(visible_tiles, camera_offset, zoom)
        
        # **关键优化3：优化的迷雾渲染**
        self._render_fog_efficient(visible_tiles, camera_offset, zoom)
        
        # **关键优化4：简化的边界渲染**
        self._render_boundaries_simple(visible_tiles, camera_offset, zoom)

        # 性能统计
        if self.frame_count % 300 == 0:
            tiles_saved = 2500 - len(visible_tiles)
            print(f"[真正优化版] 帧数: {self.frame_count}, 可见格子: {len(visible_tiles)}/2500, 节省: {tiles_saved}")

    def _get_visible_tiles(self, camera_offset: List[float], zoom: float) -> Set[Tuple[int, int]]:
        """计算屏幕可见的地图格子 - 核心优化"""
        visible_tiles = set()
        
        # 计算屏幕边界对应的世界坐标
        screen_bounds = {
            'left': -camera_offset[0] / zoom,
            'right': (GameConfig.WINDOW_WIDTH - camera_offset[0]) / zoom,
            'top': -camera_offset[1] / zoom,
            'bottom': (GameConfig.WINDOW_HEIGHT - camera_offset[1]) / zoom
        }
        
        # 扩大边界以确保完整覆盖
        margin = GameConfig.HEX_SIZE * 2
        screen_bounds['left'] -= margin
        screen_bounds['right'] += margin
        screen_bounds['top'] -= margin
        screen_bounds['bottom'] += margin
        
        # 只检查可能可见的区域范围
        # 从像素坐标大致估算六边形坐标范围
        center_q = int(-camera_offset[0] / zoom / (GameConfig.HEX_SIZE * 1.5))
        center_r = int(-camera_offset[1] / zoom / (GameConfig.HEX_SIZE * 0.866))
        
        # 检查范围（比全地图小得多）
        search_radius = max(
            int(GameConfig.WINDOW_WIDTH / zoom / GameConfig.HEX_SIZE) + 2,
            int(GameConfig.WINDOW_HEIGHT / zoom / GameConfig.HEX_SIZE) + 2
        )
        
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return visible_tiles
            
        # 只在估算范围内查找可见格子
        for q in range(center_q - search_radius, center_q + search_radius + 1):
            for r in range(center_r - search_radius, center_r + search_radius + 1):
                if (q, r) not in map_data.tiles:
                    continue
                    
                # 检查这个格子是否在屏幕内
                world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
                
                if (screen_bounds['left'] <= world_x <= screen_bounds['right'] and
                    screen_bounds['top'] <= world_y <= screen_bounds['bottom']):
                    visible_tiles.add((q, r))
        
        return visible_tiles

    def _render_visible_tiles_direct(self, visible_tiles: Set[Tuple[int, int]], 
                                   camera_offset: List[float], zoom: float):
        """直接渲染可见格子 - 避免复杂缓存操作"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return
            
        # 只渲染可见的格子（通常只有几十个而不是2500个）
        for (q, r) in visible_tiles:
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

            # 渲染地形
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))
            if texture and self.texture_loaded:
                # 使用预缩放的贴图避免实时缩放
                if abs(zoom - 1.0) < 0.1:
                    # 接近1.0缩放，直接使用
                    texture_rect = texture.get_rect(center=(int(screen_x), int(screen_y)))
                    RMS.draw(texture, texture_rect.topleft)
                else:
                    # 需要缩放，但只缩放小贴图
                    scaled_size = int(GameConfig.HEX_SIZE * 2 * zoom)
                    if scaled_size > 10:  # 避免过小贴图
                        scaled_texture = pygame.transform.scale(texture, (scaled_size, scaled_size))
                        texture_rect = scaled_texture.get_rect(center=(int(screen_x), int(screen_y)))
                        RMS.draw(scaled_texture, texture_rect.topleft)
            else:
                # 颜色渲染后备方案
                self._render_hex_color(terrain.terrain_type, q, r, screen_x, screen_y, zoom)

    def _render_hex_color(self, terrain_type: TerrainType, q: int, r: int, 
                         screen_x: float, screen_y: float, zoom: float):
        """渲染六边形颜色"""
        color = GameConfig.TERRAIN_COLORS.get(terrain_type, (128, 128, 128))
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + screen_x, (y * zoom) + screen_y) 
            for x, y in corners
        ]
        RMS.polygon(color, screen_corners)
        # 简化边框
        RMS.polygon((50, 50, 50), screen_corners, 1)

    def _render_fog_efficient(self, visible_tiles: Set[Tuple[int, int]], 
                            camera_offset: List[float], zoom: float):
        """高效的战争迷雾渲染 - 只处理可见格子"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)

        if not game_state or not fog_of_war or not ui_state or ui_state.god_mode:
            return

        view_faction = (
            ui_state.view_faction if ui_state.view_faction 
            else game_state.current_player
        )

        visible_faction_tiles = fog_of_war.faction_vision.get(view_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(view_faction, set())

        # **关键：只处理屏幕可见的格子**
        for (q, r) in visible_tiles:
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            if (q, r) in visible_faction_tiles:
                continue  # 当前视野，不绘制迷雾
            elif (q, r) in explored_tiles:
                # 已探索但非视野
                RMS.polygon(GameConfig.FOG_EXPLORED_COLOR, screen_corners)
            else:
                # 未探索
                RMS.polygon(GameConfig.FOG_UNEXPLORED_COLOR, screen_corners)

        # 渲染视野边界
        self._render_vision_circles(view_faction, camera_offset, zoom)

    def _render_vision_circles(self, faction: Faction, camera_offset: List[float], zoom: float):
        """渲染视野圆圈"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position or unit.faction != faction:
                continue

            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = (center_world_x * zoom) + camera_offset[0]
            center_screen_y = (center_world_y * zoom) + camera_offset[1]

            # 屏幕边界检查
            if (center_screen_x < -200 or center_screen_x > GameConfig.WINDOW_WIDTH + 200 or
                center_screen_y < -200 or center_screen_y > GameConfig.WINDOW_HEIGHT + 200):
                continue

            unit_stats = GameConfig.UNIT_STATS.get(unit.unit_type)
            if unit_stats:
                vision_range = unit_stats.vision_range
                circle_radius = int(vision_range * GameConfig.HEX_SIZE * 1.5 * zoom)
                RMS.circle(
                    GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                    (int(center_screen_x), int(center_screen_y)),
                    circle_radius, 2
                )

    def _render_boundaries_simple(self, visible_tiles: Set[Tuple[int, int]], 
                                camera_offset: List[float], zoom: float):
        """简化的边界渲染"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        for (q, r) in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if not tile_entity:
                continue
                
            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control or not territory_control.controlling_faction:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            faction_color = GameConfig.FACTION_COLORS.get(territory_control.controlling_faction)
            if faction_color:
                corners = self.hex_converter.get_hex_corners(q, r)
                screen_corners = [
                    ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                    for x, y in corners
                ]
                RMS.polygon(faction_color, screen_corners, max(1, int(2 * zoom)))

    def _get_terrain_texture(self, terrain_type: TerrainType, tile_key: Tuple[int, int]) -> Optional[pygame.Surface]:
        """获取地形贴图"""
        if not self.texture_loaded or terrain_type not in self.terrain_textures:
            return None

        textures = self.terrain_textures[terrain_type]
        if not textures:
            return None

        if tile_key in self.tile_texture_cache:
            return self.tile_texture_cache[tile_key]

        random.seed(tile_key[0] * 10007 + tile_key[1] * 10009)
        selected_texture = random.choice(textures)
        self.tile_texture_cache[tile_key] = selected_texture
        random.seed()

        return selected_texture 