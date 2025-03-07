import math
import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message
from rotk.components import (
    MapComponent,
    UnitRenderComponent,
    UnitStatsComponent,
    UnitPositionComponent,
)
from rotk.managers import CameraManager
from rotk.utils.terrain_renderer import TerrainRenderer


class RenderSystem(System):
    def __init__(self):
        # 这里根据需要定义依赖的组件，例如MapComponent、UnitRenderComponent等
        super().__init__([], priority=15)
        self.camera_manager: CameraManager = None
        self.player_faction_id = 2  # 默认蜀国，需要从地图系统同步
        self.selected_unit = None  # 当前选中的单位
        self.target_unit = None  # 当前目标单位

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        camera_manager: CameraManager = None,
    ) -> None:
        self.event_manager = event_manager
        self.camera_manager = camera_manager

        # 订阅单位选择和目标选择事件
        self.event_manager.subscribe("UNIT_SELECTED", self._handle_unit_selected)
        self.event_manager.subscribe("TARGET_SELECTED", self._handle_target_selected)
        self.event_manager.subscribe("FACTION_SWITCHED", self._handle_faction_switched)

    def _handle_unit_selected(self, message):
        """处理单位选择事件"""
        self.selected_unit = message.data.get("unit")

    def _handle_target_selected(self, message):
        """处理目标选择事件"""
        self.target_unit = message.data.get("target")

    def _handle_faction_switched(self, message):
        """处理阵营切换事件"""
        self.player_faction_id = message.data.get("faction_id")

    def update(self, world: World, delta_time: float) -> None:
        # 这里不做更新处理，渲染在render()中完成
        # 从地图系统更新玩家阵营ID和选中单位
        map_systems = [s for s in world.systems if hasattr(s, "player_faction_id")]
        if map_systems:
            self.player_faction_id = map_systems[0].player_faction_id
            self.selected_unit = map_systems[0].selected_unit
            self.target_unit = map_systems[0].target_unit

    def render(self, world: World, render_manager) -> None:
        map_entity = world.get_entities_with_components(MapComponent)
        map_comp = (
            world.get_component(map_entity[0], MapComponent) if map_entity else None
        )
        if not map_comp:
            return
        width, height, cell_size = map_comp.width, map_comp.height, map_comp.cell_size
        grid = map_comp.grid

        # 渲染地形
        render_manager.set_layer(0)
        if self.camera_manager:
            screen_left, screen_top = self.camera_manager.screen_to_world(0, 0)
            screen_right, screen_bottom = self.camera_manager.screen_to_world(
                self.camera_manager.screen_width, self.camera_manager.screen_height
            )
            start_x = max(0, int(screen_left / cell_size) - 1)
            start_y = max(0, int(screen_top / cell_size) - 1)
            end_x = min(width, int(screen_right / cell_size) + 2)
            end_y = min(height, int(screen_bottom / cell_size) + 2)
        else:
            start_x, start_y = 0, 0
            end_x, end_y = width, height

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                if y < len(grid) and x < len(grid[y]):
                    terrain_type = grid[y][x]
                    world_x = x * cell_size
                    world_y = y * cell_size
                    if self.camera_manager:
                        screen_x, screen_y = self.camera_manager.world_to_screen(
                            world_x, world_y
                        )
                        cell_width = math.ceil(cell_size * self.camera_manager.zoom) + 1
                        cell_height = (
                            math.ceil(cell_size * self.camera_manager.zoom) + 1
                        )
                    else:
                        screen_x, screen_y = world_x, world_y
                        cell_width = cell_height = cell_size + 1
                    rect = pygame.Rect(screen_x, screen_y, cell_width, cell_height)
                    cell_surface = pygame.Surface((cell_width, cell_height))
                    TerrainRenderer.render_terrain(
                        cell_surface, terrain_type, cell_surface.get_rect()
                    )
                    render_manager.draw(cell_surface, rect)

        # 渲染单位
        units = world.get_entities_with_components(
            UnitRenderComponent, UnitStatsComponent, UnitPositionComponent
        )
        render_manager.set_layer(1)  # 单位层级

        # 先排序单位，确保选中的单位在最上层
        sorted_units = sorted(
            units,
            key=lambda u: (
                u == self.selected_unit or u == self.target_unit,
                u == self.selected_unit,
            ),
        )

        for unit in sorted_units:
            unit_render = world.get_component(unit, UnitRenderComponent)
            unit_stats = world.get_component(unit, UnitStatsComponent)
            unit_pos = world.get_component(unit, UnitPositionComponent)
            if unit_render and unit_pos and unit_stats:
                # 计算单位在世界中的真实位置
                world_x = unit_pos.x * cell_size
                world_y = unit_pos.y * cell_size

                if self.camera_manager:
                    screen_x, screen_y = self.camera_manager.world_to_screen(
                        world_x, world_y
                    )
                else:
                    screen_x, screen_y = world_x, world_y

                # 调整渲染大小以适应缩放
                display_size = unit_render.size
                if self.camera_manager:
                    display_size = int(unit_render.size * self.camera_manager.zoom)

                # 创建一个大一点的表面，以容纳额外的标记
                padding = 6  # 额外边距，用于绘制选择标记
                if unit == self.selected_unit or unit == self.target_unit:
                    padding = 10

                total_size = display_size + padding * 2
                unit_surf = pygame.Surface((total_size, total_size), pygame.SRCALPHA)

                # 绘制特殊标记
                # 1. 当前阵营标记 - 在单位下方绘制一个小三角形
                if unit_stats.faction_id == self.player_faction_id:
                    triangle_size = display_size // 3
                    triangle_points = [
                        (total_size // 2, total_size - padding // 2),  # 底部中心点
                        (
                            total_size // 2 - triangle_size // 2,
                            total_size - triangle_size - padding // 2,
                        ),  # 左上
                        (
                            total_size // 2 + triangle_size // 2,
                            total_size - triangle_size - padding // 2,
                        ),  # 右上
                    ]
                    pygame.draw.polygon(
                        unit_surf, (255, 255, 0), triangle_points  # 明亮的黄色
                    )

                # 2. 选中单位的标记 - 绘制一个亮色边框
                if unit == self.selected_unit:
                    border_color = (0, 255, 255)  # 青色，醒目
                    border_width = 3
                    pygame.draw.circle(
                        unit_surf,
                        border_color,
                        (total_size // 2, total_size // 2),
                        display_size // 2 + border_width,
                        border_width,
                    )

                    # 为选中单位绘制方向指示器
                    if unit_stats.faction_id == self.player_faction_id:
                        direction_length = display_size // 2 + 10
                        pygame.draw.line(
                            unit_surf,
                            border_color,
                            (total_size // 2, total_size // 2),
                            (total_size // 2, total_size // 2 - direction_length),
                            2,
                        )

                # 3. 目标单位的标记 - 绘制一个红色边框
                elif unit == self.target_unit:
                    target_color = (255, 0, 0)  # 红色
                    border_width = 2
                    pygame.draw.circle(
                        unit_surf,
                        target_color,
                        (total_size // 2, total_size // 2),
                        display_size // 2 + border_width,
                        border_width,
                    )

                # 绘制单位底圈（用于阵营标识）
                pygame.draw.circle(
                    unit_surf,
                    unit_render.main_color,
                    (total_size // 2, total_size // 2),
                    display_size // 2,
                )

                # 绘制单位符号
                font_size = max(14, int(display_size * 0.7))
                font = pygame.font.Font(None, font_size)
                text = font.render(unit_render.symbol, True, (0, 0, 0))
                text_rect = text.get_rect(center=(total_size // 2, total_size // 2))
                unit_surf.blit(text, text_rect)

                # 绘制血条
                if unit_stats:
                    health_ratio = unit_stats.health / unit_stats.max_health
                    health_width = display_size * health_ratio
                    health_height = max(2, int(display_size * 0.1))
                    health_y_offset = total_size - padding

                    # 背景条
                    pygame.draw.rect(
                        unit_surf,
                        (50, 50, 50),
                        (padding, health_y_offset, display_size, health_height),
                    )

                    # 血条
                    health_color = (0, 255, 0)  # 绿色
                    if health_ratio < 0.3:
                        health_color = (255, 0, 0)  # 红色
                    elif health_ratio < 0.7:
                        health_color = (255, 255, 0)  # 黄色

                    pygame.draw.rect(
                        unit_surf,
                        health_color,
                        (padding, health_y_offset, int(health_width), health_height),
                    )

                rect = pygame.Rect(
                    screen_x - total_size // 2,
                    screen_y - total_size // 2,
                    total_size,
                    total_size,
                )
                render_manager.draw(unit_surf, rect)

        # 渲染移动目标标记
        map_systems = [s for s in world.systems if hasattr(s, "move_target")]
        if map_systems and map_systems[0].move_target and self.camera_manager:
            move_target = map_systems[0].move_target
            target_x, target_y = move_target
            world_x = target_x * cell_size + cell_size // 2
            world_y = target_y * cell_size + cell_size // 2
            screen_x, screen_y = self.camera_manager.world_to_screen(world_x, world_y)

            # 绘制移动目标标记 - 绿色圆圈
            mark_radius = int(10 * self.camera_manager.zoom)
            render_manager.draw_circle(
                (0, 255, 0), (screen_x, screen_y), mark_radius, 2
            )

            # 绘制从选中单位到目标的虚线
            if self.selected_unit:
                selected_pos = world.get_component(
                    self.selected_unit, UnitPositionComponent
                )
                if selected_pos:
                    start_world_x = selected_pos.x * cell_size
                    start_world_y = selected_pos.y * cell_size
                    start_screen_x, start_screen_y = (
                        self.camera_manager.world_to_screen(
                            start_world_x, start_world_y
                        )
                    )

                    # 计算线段总长度
                    line_length = math.sqrt(
                        (screen_x - start_screen_x) ** 2
                        + (screen_y - start_screen_y) ** 2
                    )
                    segments = int(line_length / 10)  # 每10像素一个线段

                    if segments > 0:
                        dx = (screen_x - start_screen_x) / segments
                        dy = (screen_y - start_screen_y) / segments

                        for i in range(segments):
                            if i % 2 == 0:  # 只绘制偶数段，形成虚线效果
                                start_point = (
                                    start_screen_x + i * dx,
                                    start_screen_y + i * dy,
                                )
                                end_point = (
                                    start_screen_x + (i + 1) * dx,
                                    start_screen_y + (i + 1) * dy,
                                )
                                render_manager.draw_line(
                                    (0, 255, 0), start_point, end_point, 2
                                )
