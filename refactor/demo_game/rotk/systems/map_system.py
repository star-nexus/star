import math
import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    MapComponent,
    PositionComponent,
    RenderableComponent,
    TERRAIN_COLORS,
)

from rotk.managers import MapManager, CameraManager
from rotk.utils.terrain_renderer import TerrainRenderer


class MapSystem(System):
    """地图系统，负责地图生成和渲染"""

    def __init__(self):
        super().__init__([MapComponent], priority=10)
        self.camera_manager = None
        self.map_manager = None

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager: MapManager,
        camera_manager: CameraManager = None,
    ) -> None:
        """初始化地图系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            camera_manager: 相机管理器（可选）
        """
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.camera_manager = camera_manager

        # 订阅鼠标事件来处理相机移动
        if self.camera_manager:
            self.event_manager.subscribe(
                "MOUSEMOTION", lambda message: self._handle_mouse_motion(world, message)
            )
            self.event_manager.subscribe(
                "KEYDOWN", lambda message: self._handle_camera_input(world, message)
            )

    def _handle_mouse_motion(self, world: World, message: Message) -> None:
        """处理鼠标移动事件，控制相机"""
        if not self.camera_manager:
            return

        # 检查是否按住中键拖动
        if message.data.get("buttons") and message.data.get("buttons")[1]:  # 中键
            dx, dy = message.data.get("rel", (0, 0))
            # 反向移动相机以实现拖动效果
            self.camera_manager.move(
                -dx / self.camera_manager.zoom, -dy / self.camera_manager.zoom
            )

            # 限制相机不超出地图范围
            self._constrain_camera(world)

    def _handle_camera_input(self, world: World, message: Message) -> None:
        """处理相机缩放的键盘输入

        Args:
            world: 游戏世界
            message: 事件消息
        """
        if not self.camera_manager:
            return

        key = message.data
        # 处理缩放控制 (+ 和 - 键)
        if key == pygame.K_PLUS or key == pygame.K_EQUALS:  # EQUALS 键也是 + 键
            self.camera_manager.adjust_zoom(1.1)  # 放大
            self._constrain_camera(world)
        elif key == pygame.K_MINUS:
            self.camera_manager.adjust_zoom(0.9)  # 缩小
            self._constrain_camera(world)

    def _constrain_camera(self, world: World) -> None:
        """限制相机不超出地图范围

        Args:
            world: 游戏世界
        """
        if not self.camera_manager:
            return

        # 限制相机不超出地图范围
        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        if map_comp:
            self.camera_manager.constrain(
                map_comp.width, map_comp.height, map_comp.cell_size
            )

    def regenerate_map(self, world: World) -> None:
        """重新生成地图

        Args:
            world: 游戏世界
        """
        self.map_manager.regenerate_map(world)

    def update(self, world: World, delta_time: float) -> None:
        """更新地图系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 地图系统的更新逻辑，目前为空
        pass

    def render(self, world: World, render_manager) -> None:
        """渲染地图和实体

        Args:
            world: 游戏世界
            render_manager: 渲染管理器
        """
        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        if not map_comp:
            return

        width, height, cell_size = map_comp.width, map_comp.height, map_comp.cell_size
        grid = map_comp.grid

        # 设置渲染层级为0（最底层）
        render_manager.set_layer(0)

        # 计算可见区域（如果有相机的话）
        if self.camera_manager:
            # 转换为格子坐标，略微扩大可见区域以避免边缘问题
            screen_left, screen_top = self.camera_manager.screen_to_world(0, 0)
            screen_right, screen_bottom = self.camera_manager.screen_to_world(
                self.camera_manager.screen_width, self.camera_manager.screen_height
            )

            start_x = max(0, int(screen_left / cell_size) - 1)  # 扩展1格
            start_y = max(0, int(screen_top / cell_size) - 1)  # 扩展1格
            end_x = min(width, int(screen_right / cell_size) + 2)  # 扩展1格
            end_y = min(height, int(screen_bottom / cell_size) + 2)  # 扩展1格
        else:
            # 没有相机时渲染整个地图
            start_x, start_y = 0, 0
            end_x, end_y = width, height

        # 渲染地图网格
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                if y < len(grid) and x < len(grid[y]):
                    terrain_type = grid[y][x]

                    # 计算单元格位置
                    world_x = x * cell_size
                    world_y = y * cell_size

                    # 应用相机转换（如果有相机）
                    if self.camera_manager:
                        screen_x, screen_y = self.camera_manager.world_to_screen(
                            world_x, world_y
                        )
                        # 应用缩放因子，使用ceil确保没有缝隙
                        cell_width = math.ceil(cell_size * self.camera_manager.zoom) + 1
                        cell_height = (
                            math.ceil(cell_size * self.camera_manager.zoom) + 1
                        )
                    else:
                        screen_x, screen_y = world_x, world_y
                        cell_width = cell_height = cell_size + 1

                    # 创建单元格矩形
                    rect = pygame.Rect(screen_x, screen_y, cell_width, cell_height)

                    # 使用地形渲染器绘制单元格
                    cell_surface = pygame.Surface((cell_width, cell_height))
                    TerrainRenderer.render_terrain(
                        cell_surface, terrain_type, cell_surface.get_rect()
                    )
                    render_manager.draw(cell_surface, rect)

        # 设置渲染层级为1（实体层）
        render_manager.set_layer(1)

        # 渲染实体
        for entity, (x, y) in map_comp.entities_positions.items():
            renderable = world.get_component(entity, RenderableComponent)
            if renderable:
                # 计算实体在世界坐标系中的位置
                world_x = x * cell_size + cell_size // 2
                world_y = y * cell_size + cell_size // 2

                # 应用相机转换（如果有相机）
                if self.camera_manager:
                    screen_x, screen_y = self.camera_manager.world_to_screen(
                        world_x, world_y
                    )
                    # 调整实体大小以适应缩放
                    radius = int(renderable.size // 2 * self.camera_manager.zoom)
                else:
                    screen_x, screen_y = world_x, world_y
                    radius = renderable.size // 2

                # 检查实体是否在可见区域内
                if self.camera_manager is None or (
                    0 <= screen_x < self.camera_manager.screen_width
                    and 0 <= screen_y < self.camera_manager.screen_height
                ):
                    # 绘制实体
                    render_manager.draw_circle(
                        renderable.color, (screen_x, screen_y), radius
                    )

                    # 加载默认字体绘制符号
                    font_size = int(
                        20 * (self.camera_manager.zoom if self.camera_manager else 1)
                    )
                    font = pygame.font.Font(None, max(10, font_size))
                    text = font.render(renderable.symbol, True, (255, 255, 255))
                    text_rect = text.get_rect(center=(screen_x, screen_y))
                    render_manager.draw(text, text_rect)
