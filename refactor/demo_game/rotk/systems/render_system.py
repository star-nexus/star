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

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        camera_manager: CameraManager = None,
    ) -> None:
        self.event_manager = event_manager
        self.camera_manager = camera_manager
        # 可以订阅渲染相关的事件
        # ...existing code...

    def update(self, world: World, delta_time: float) -> None:
        # 这里不做更新处理，渲染在render()中完成
        pass

    def render(self, world: World, render_manager) -> None:
        map_entity = world.get_entities_with_components(MapComponent)
        map_comp = (
            world.get_component(map_entity[0], MapComponent) if map_entity else None
        )
        if not map_comp:
            return
        width, height, cell_size = map_comp.width, map_comp.height, map_comp.cell_size
        grid = map_comp.grid

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

        # 新增：渲染单位
        units = world.get_entities_with_components(
            UnitRenderComponent, UnitStatsComponent, UnitPositionComponent
        )
        render_manager.set_layer(1)  # 单位层级
        for unit in units:
            unit_render = world.get_component(unit, UnitRenderComponent)
            unit_stats = world.get_component(unit, UnitStatsComponent)
            unit_pos = world.get_component(unit, UnitPositionComponent)
            if unit_render and unit_pos:
                world_x, world_y = unit_pos.x, unit_pos.y
                if self.camera_manager:
                    screen_x, screen_y = self.camera_manager.world_to_screen(
                        world_x, world_y
                    )
                else:
                    screen_x, screen_y = world_x, world_y
                unit_surf = pygame.Surface(
                    (unit_render.size, unit_render.size), pygame.SRCALPHA
                )
                pygame.draw.circle(
                    unit_surf,
                    unit_render.main_color,
                    (unit_render.size // 2, unit_render.size // 2),
                    unit_render.size // 2,
                )
                rect = pygame.Rect(
                    screen_x, screen_y, unit_render.size, unit_render.size
                )
                render_manager.draw(unit_surf, rect)
