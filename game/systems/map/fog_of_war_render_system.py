import pygame
import numpy as np
from typing import Tuple, List, Dict, Optional
from framework.ecs.system import System
from framework.utils.logging_tool import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import MapComponent
from game.components import TileComponent
from game.components import CameraComponent
from game.components import FogOfWarComponent
from game.utils import RenderLayer, FOWType
from game.utils.game_types import ViewMode


class FogOfWarRenderSystem(System):
    """地图渲染系统，负责渲染地图和地图上的实体"""

    def __init__(self, priority: int = 40):
        """初始化地图渲染系统"""
        super().__init__(
            required_components=[MapComponent, FogOfWarComponent], priority=priority
        )
        self.logger = get_logger("FogOfWarRenderSystem")
        self.fow_colors = self._init_terrain_colors()
        self.tile_cache = {}  # 缓存渲染过的格子，提高性能
        self.fog_surface = None
        self.map_component = None
        self.camera_component = None
        self.fog_of_war_component = None

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("战争迷雾渲染系统初始化")

    def _init_terrain_colors(self) -> Dict[FOWType, Tuple[int, int, int]]:
        """初始化地形类型对应的颜色"""
        return {
            # 渲染相关
            FOWType.FOG: (20, 20, 20, 180),  # 迷雾颜色（RGBA）
            FOWType.EXPLORATION: (60, 60, 60, 120),  # 已探索区域的迷雾颜色
        }

    def get_fow_color(self, fow_type: FOWType) -> Tuple[int, int, int, int]:
        """获取地形类型对应的颜色"""
        return self.fow_colors.get(fow_type, (200, 200, 200))  # 默认为灰色

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
        """更新战争迷雾渲染系统"""
        # 获取地图组件
        self.map_component = self._get_map_component()
        if not self.map_component:
            return

        # 获取战争迷雾组件
        fow_entity = self.context.with_all(FogOfWarComponent).first()
        if not fow_entity:
            return
        self.fog_of_war_component = self.context.get_component(
            fow_entity, FogOfWarComponent
        )

        # 获取渲染表面并渲染战争迷雾
        if self.context.render_manager and self.context.screen:
            self.render(self.context.screen)

    def render(self, surface: pygame.Surface):
        """渲染战争迷雾"""
        if (
            not self.is_enabled()
            or not self.fog_of_war_component
            or not self.map_component
        ):
            return

        # 如果战争迷雾被禁用，不进行渲染
        # if not self.fog_of_war_component.fog_of_war_enabled:
        #     return

        # 在地图渲染后、单位渲染前调用此方法

        # 获取相机组件
        camera_entity = self.context.with_all(CameraComponent).first()
        if not camera_entity:
            return
        self.camera_component = self.context.get_component(
            camera_entity, CameraComponent
        )

        # 获取当前玩家ID
        current_player_id = self.fog_of_war_component.current_player_id

        # 创建或调整迷雾表面大小
        if not self.fog_surface or self.fog_surface.get_size() != (
            surface.get_width(),
            surface.get_height(),
        ):
            self.fog_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # 清除迷雾表面
        self.fog_surface.fill((0, 0, 0, 0))

        # 获取地图尺寸和格子大小
        map_width, map_height = self.map_component.width, self.map_component.height
        tile_size = self.map_component.tile_size

        # 计算可见区域
        for y in range(map_height):
            for x in range(map_width):
                # 将地图坐标转换为世界坐标
                world_x = x * tile_size + tile_size / 2
                world_y = y * tile_size + tile_size / 2

                # 将世界坐标转换为屏幕坐标
                screen_x, screen_y = self._world_to_screen(
                    world_x, world_y, self.camera_component
                )

                # 检查是否在屏幕范围内
                if (
                    0 <= screen_x <= surface.get_width()
                    and 0 <= screen_y <= surface.get_height()
                ):
                    # 根据视角模式确定可见性
                    is_visible = False
                    is_explored = False

                    # 全局视角模式 - 显示所有已探索区域
                    if self.fog_of_war_component.view_mode == ViewMode.GLOBAL:
                        # 检查任何玩家是否已探索该区域
                        for player_id in self.fog_of_war_component.explored_map:
                            if (
                                self.fog_of_war_component.explored_map[player_id][y, x]
                                == 1
                            ):
                                is_explored = True
                                # 检查是否当前可见
                                if (
                                    self.fog_of_war_component.visibility_map[player_id][
                                        y, x
                                    ]
                                    == 1
                                ):
                                    is_visible = True
                                    break
                    # 玩家视角模式 - 只显示当前玩家的可见区域
                    else:
                        if (
                            current_player_id
                            in self.fog_of_war_component.visibility_map
                        ):
                            is_visible = (
                                self.fog_of_war_component.visibility_map[
                                    current_player_id
                                ][y, x]
                                == 1
                            )
                        if current_player_id in self.fog_of_war_component.explored_map:
                            is_explored = (
                                self.fog_of_war_component.explored_map[
                                    current_player_id
                                ][y, x]
                                == 1
                            )

                    # 绘制迷雾
                    if not is_visible:
                        # 已探索但不可见的区域使用半透明迷雾
                        if is_explored:
                            pygame.draw.rect(
                                self.fog_surface,
                                self.get_fow_color(FOWType.EXPLORATION),
                                (
                                    screen_x
                                    - tile_size / 2 * self.camera_component.zoom,
                                    screen_y
                                    - tile_size / 2 * self.camera_component.zoom,
                                    tile_size * self.camera_component.zoom,
                                    tile_size * self.camera_component.zoom,
                                ),
                            )
                        # 未探索区域使用完全不透明迷雾
                        else:
                            pygame.draw.rect(
                                self.fog_surface,
                                self.get_fow_color(FOWType.FOG),
                                (
                                    screen_x
                                    - tile_size / 2 * self.camera_component.zoom,
                                    screen_y
                                    - tile_size / 2 * self.camera_component.zoom,
                                    tile_size * self.camera_component.zoom,
                                    tile_size * self.camera_component.zoom,
                                ),
                            )

        # 将迷雾表面绘制到主表面
        # surface.blit(self.fog_surface, (0, 0))
        self.context.render_manager.draw_surface(
            self.fog_surface,
            (0, 0),
            RenderLayer.FOW.value,
        )
