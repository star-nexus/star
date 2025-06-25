"""
效果渲染系统 - 负责选择、移动、攻击范围、瓦片悬停等效果的渲染
"""

import pygame
from typing import List, Set, Tuple
from framework_v2 import System, RMS
from ..components import (
    UIState,
    InputState,
    HexPosition,
    Unit,
    Movement,
    Combat,
    Camera,
    FogOfWar,
    GameState,
)
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter, HexMath, PathFinding


class EffectRenderSystem(System):
    """效果渲染系统"""

    def __init__(self):
        super().__init__(priority=3)  # 在单位之上渲染效果
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE)

    def initialize(self, world) -> None:
        """初始化效果渲染系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件（效果渲染系统不需要订阅事件）"""
        pass

    def update(self, delta_time: float) -> None:
        """更新效果渲染"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # 计算摄像机偏移
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # 渲染各种效果
        self._render_selection_effects(camera_offset, zoom)
        self._render_tile_hover(camera_offset, zoom)

    def _render_selection_effects(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染选择效果"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return

        # 渲染单位选择
        if ui_state.selected_unit:
            self._render_unit_selection(ui_state.selected_unit, camera_offset, zoom)

            # 获取选中单位的组件
            movement = self.world.get_component(ui_state.selected_unit, Movement)
            combat = self.world.get_component(ui_state.selected_unit, Combat)

            # 显示移动范围（如果单位还没有移动）
            if movement and not movement.has_moved:
                self._render_movement_range(ui_state.selected_unit, camera_offset, zoom)

            # 显示攻击范围（如果单位还没有攻击）
            if combat and not combat.has_attacked:
                self._render_attack_range(ui_state.selected_unit, camera_offset, zoom)

    def _render_unit_selection(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """渲染单位选择效果"""
        position = self.world.get_component(unit_entity, HexPosition)
        if not position:
            return

        # 转换为屏幕坐标（修复坐标转换）
        world_x, world_y = self.hex_converter.hex_to_pixel(position.col, position.row)
        screen_x = world_x * zoom + camera_offset[0]
        screen_y = world_y * zoom + camera_offset[1]

        # 绘制选择圆环
        radius = int(GameConfig.HEX_SIZE * 0.8 * zoom)
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 0), (int(screen_x), int(screen_y)), radius, 3
        # )
        RMS.circle((255, 255, 0), (int(screen_x), int(screen_y)), radius, 3)

        # 绘制闪烁效果
        import time

        pulse = abs(0.5 - (time.time() % 1.0)) * 0.4 + 0.6
        inner_radius = int(radius * pulse)
        # 注意：pygame不支持alpha通道的circle，需要用surface
        s = pygame.Surface((inner_radius * 2, inner_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            s, (255, 255, 0, 50), (inner_radius, inner_radius), inner_radius
        )
        RMS.screen.blit(s, (int(screen_x - inner_radius), int(screen_y - inner_radius)))

    def _render_movement_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """渲染移动范围"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, Movement)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not movement or not unit:
            return

        # 获取障碍物
        obstacles = self._get_obstacles()
        # 计算可移动范围
        movement_range = PathFinding().get_movement_range(
            (position.col, position.row), movement.current_movement, obstacles
        )

        # # 获取在移动范围内的所有瓦片
        # reachable_tiles = set()
        # for distance in range(1, movement.current_movement + 1):
        #     ring_tiles = HexMath.hex_ring(position.col, position.row, distance)
        #     for tile_col, tile_row in ring_tiles:
        #         # 检查路径是否可达
        #         path = pathfinding.find_path(
        #             (position.col, position.row),
        #             (tile_col, tile_row),
        #             obstacles,
        #             movement.current_movement,
        #         )
        #         if path and len(path) - 1 <= movement.current_movement:
        #             reachable_tiles.add((tile_col, tile_row))

        # # 渲染可移动区域
        # for tile_col, tile_row in reachable_tiles:
        #     # 检查是否在地图范围内
        #     if not (
        #         -GameConfig.MAP_WIDTH // 2 <= tile_col < GameConfig.MAP_WIDTH // 2
        #         and -GameConfig.MAP_HEIGHT // 2 <= tile_row < GameConfig.MAP_HEIGHT // 2
        #     ):
        #         continue

        #     # 转换为屏幕坐标（修复坐标转换）
        #     world_x, world_y = self.hex_converter.hex_to_pixel(tile_col, tile_row)
        #     screen_x = world_x * zoom + camera_offset[0]
        #     screen_y = world_y * zoom + camera_offset[1]

        #     # 检查是否在屏幕范围内
        #     if not (
        #         0 <= screen_x < GameConfig.WINDOW_WIDTH
        #         and 0 <= screen_y < GameConfig.WINDOW_HEIGHT
        #     ):
        #         continue

        #     # pygame.draw.circle(
        #     #     RMS.screen, (0, 255, 0, 100), (int(screen_x), int(screen_y)), radius
        #     # )
        #     # pygame.draw.circle(
        #     #     RMS.screen, (0, 255, 0), (int(screen_x), int(screen_y)), radius, 2
        #     # )
        # 绘制移动范围
        for q, r in movement_range:
            if (q, r) == (position.col, position.row):
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 绘制半透明蓝色覆盖（应用缩放）
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            hex_size_scaled = int(GameConfig.HEX_SIZE * zoom)
            overlay = pygame.Surface((hex_size_scaled * 2, hex_size_scaled * 2))
            overlay.set_alpha(100)
            overlay.fill((0, 0, 255))

            # 创建六边形蒙版
            mask_surface = pygame.Surface(
                (hex_size_scaled * 2, hex_size_scaled * 2), pygame.SRCALPHA
            )
            mask_corners = [
                (
                    (x * zoom) - (world_x * zoom) + hex_size_scaled,
                    (y * zoom) - (world_y * zoom) + hex_size_scaled,
                )
                for x, y in corners
            ]
            pygame.draw.polygon(mask_surface, (0, 0, 255, 100), mask_corners)

            RMS.draw(
                mask_surface,
                (screen_x - hex_size_scaled, screen_y - hex_size_scaled),
            )

    def _render_attack_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """渲染攻击范围"""
        position = self.world.get_component(unit_entity, HexPosition)
        combat = self.world.get_component(unit_entity, Combat)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not combat or not unit:
            return

        # 获取攻击范围内的瓦片
        attack_tiles = HexMath.hex_in_range(
            position.col, position.row, combat.attack_range
        )

        # 渲染攻击范围
        for tile_col, tile_row in attack_tiles:
            # 跳过单位自身位置
            if tile_col == position.col and tile_row == position.row:
                continue

            # 检查是否在地图范围内
            if not (
                -GameConfig.MAP_WIDTH // 2 <= tile_col < GameConfig.MAP_WIDTH // 2
                and -GameConfig.MAP_HEIGHT // 2 <= tile_row < GameConfig.MAP_HEIGHT // 2
            ):
                continue

            # 转换为屏幕坐标（修复坐标转换）
            world_x, world_y = self.hex_converter.hex_to_pixel(tile_col, tile_row)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]

            # 检查是否在屏幕范围内
            if not (
                0 <= screen_x < GameConfig.WINDOW_WIDTH
                and 0 <= screen_y < GameConfig.WINDOW_HEIGHT
            ):
                continue

            # 检查是否有敌方单位
            enemy_unit = self._get_enemy_unit_at_position(
                (tile_col, tile_row), unit.faction
            )
            if enemy_unit:
                # 如果有敌方单位，用红色高亮
                radius = int(GameConfig.HEX_SIZE * 0.7 * zoom)
                # pygame.draw.circle(
                #     RMS.screen, (255, 0, 0, 150), (int(screen_x), int(screen_y)), radius
                # )
                # pygame.draw.circle(
                #     RMS.screen, (255, 0, 0), (int(screen_x), int(screen_y)), radius, 3
                # )
                RMS.circle(
                    (255, 0, 0, 150),
                    (int(screen_x), int(screen_y)),
                    radius,
                )
                # RMS.circle(
                #     (255, 0, 0),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                #     1,
                # )
            else:
                # 否则用橙色显示攻击范围
                radius = int(GameConfig.HEX_SIZE * 0.5 * zoom)
                # pygame.draw.circle(
                #     RMS.screen,
                #     (255, 165, 0, 80),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                # )
                # pygame.draw.circle(
                #     RMS.screen, (255, 165, 0), (int(screen_x), int(screen_y)), radius, 2
                # )
                RMS.circle(
                    (255, 165, 0, 80),
                    (int(screen_x), int(screen_y)),
                    radius,
                )
                # RMS.circle(
                #     (255, 165, 0),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                #     1,
                # )

    def _render_tile_hover(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染瓦片悬停效果"""
        # input_state = self.world.get_singleton_component(InputState)
        # if not input_state:
        #     return

        # 获取鼠标悬停的瓦片位置
        # mouse_x, mouse_y = pygame.mouse.get_pos()

        # # 转换为世界坐标（修复坐标转换）
        # world_x = (mouse_x - camera_offset[0]) / zoom
        # world_y = (mouse_y - camera_offset[1]) / zoom

        # # 转换为六边形坐标
        # hex_col, hex_row = self.hex_converter.pixel_to_hex(world_x, world_y)

        # # 检查是否在地图范围内
        # if not (
        #     -GameConfig.MAP_WIDTH // 2 <= hex_col < GameConfig.MAP_WIDTH // 2
        #     and -GameConfig.MAP_HEIGHT // 2 <= hex_row < GameConfig.MAP_HEIGHT // 2
        # ):
        #     return

        # # 转换回屏幕坐标进行渲染
        # world_x, world_y = self.hex_converter.hex_to_pixel(hex_col, hex_row)
        # screen_x = world_x * zoom + camera_offset[0]
        # screen_y = world_y * zoom + camera_offset[1]

        # 绘制悬停效果
        # radius = int(GameConfig.HEX_SIZE * 0.9 * zoom)
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 255, 100), (int(screen_x), int(screen_y)), radius
        # )
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 255), (int(screen_x), int(screen_y)), radius, 1
        # )
        # RMS.circle(
        #     (255, 255, 255, 100),
        #     (int(screen_x), int(screen_y)),
        #     radius,
        # )
        # RMS.circle(
        #     (255, 255, 255),
        #     (int(screen_x), int(screen_y)),
        #     radius,
        #     1,
        # )
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state.hovered_tile:
            return
        (q, r) = ui_state.hovered_tile
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        screen_x = (world_x * zoom) + camera_offset[0]
        screen_y = (world_y * zoom) + camera_offset[1]

        # 绘制悬停边框（应用缩放）
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
            for x, y in corners
        ]
        # pygame.draw.polygon(self.screen, (255, 255, 255), screen_corners, 2)
        RMS.polygon((255, 255, 255), screen_corners, 2)

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """获取障碍物位置"""
        obstacles = set()

        # 添加所有单位位置作为障碍物
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            if position:
                obstacles.add((position.col, position.row))

        return obstacles

    def _get_enemy_unit_at_position(self, position: Tuple[int, int], friendly_faction):
        """获取指定位置的敌方单位"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if (
                pos
                and unit
                and (pos.col, pos.row) == position
                and unit.faction != friendly_faction
            ):
                return entity

        return None
