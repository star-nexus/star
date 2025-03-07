import math
import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    MapComponent,
    PositionComponent,
    RenderableComponent,
    UnitPositionComponent,
    UnitRenderComponent,
    UnitStatsComponent,
    UnitMovementComponent,
    FactionComponent,
    UnitStateComponent,
    TERRAIN_COLORS,
)

from rotk.managers import MapManager, CameraManager
from rotk.utils.terrain_renderer import TerrainRenderer


class MapSystem(System):
    """地图系统，负责地图生成和渲染"""

    def __init__(self):
        super().__init__([MapComponent], priority=10)
        self.camera_manager = None
        # self.map_manager = None
        self.selected_unit = None  # 当前选中的单位
        self.hover_unit = None  # 当前鼠标悬停的单位
        self.target_unit = None  # 当前目标单位（攻击目标）
        self.move_target = None  # 移动目标位置
        self.player_faction_id = 2  # 默认玩家控制蜀国

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        # map_manager: MapManager,
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
        # self.map_manager = map_manager
        self.camera_manager = camera_manager

        # 订阅鼠标事件来处理相机移动和单位选择
        self.event_manager.subscribe(
            "MOUSEMOTION", lambda message: self._handle_mouse_motion(world, message)
        )
        self.event_manager.subscribe(
            "KEYDOWN", lambda message: self._handle_camera_input(world, message)
        )
        # 添加鼠标点击事件处理
        self.event_manager.subscribe(
            "MOUSEBUTTONDOWN", lambda message: self._handle_mouse_click(world, message)
        )
        # 订阅按键事件以处理阵营切换
        self.event_manager.subscribe(
            "KEYDOWN", lambda message: self._handle_faction_switch(world, message)
        )

    def _handle_camera_input(self, world: World, message: Message) -> None:
        """处理相机移动输入"""
        if not self.camera_manager:
            return
        # print(message.data)
        key = message.data
        # 处理相机移动
        if key == pygame.K_UP:
            self.camera_manager.move(0, -10)
        elif key == pygame.K_DOWN:
            self.camera_manager.move(0, 10)
        elif key == pygame.K_LEFT:
            self.camera_manager.move(-10, 0)
        elif key == pygame.K_RIGHT:
            self.camera_manager.move(10, 0)
        elif key == pygame.K_KP_PLUS or key == pygame.K_EQUALS:
            self.camera_manager.zoom_in()
        elif key == pygame.K_KP_MINUS or key == pygame.K_MINUS:
            self.camera_manager.zoom_out()

        # 限制相机不超出地图范围
        self._constrain_camera(world)

    def _constrain_camera(self, world: World) -> None:
        """限制相机不超出地图范围"""
        if not self.camera_manager:
            return

        # map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        map_entity = world.get_entities_with_components(MapComponent)
        # map 只有一份
        # map_comp = map_entity[0].get_component(MapComponent)
        map_comp = world.get_component(map_entity[0], MapComponent)

        if map_comp:
            self.camera_manager.constrain(
                map_comp.width, map_comp.height, map_comp.cell_size
            )

    def _handle_mouse_motion(self, world: World, message: Message) -> None:
        """处理鼠标移动事件，控制相机和单位选择悬停"""
        if not self.camera_manager:
            return

        # 获取鼠标位置
        mouse_pos = message.data.get("pos", (0, 0))

        # 检查是否按住中键拖动
        if message.data.get("buttons") and message.data.get("buttons")[1]:  # 中键
            dx, dy = message.data.get("rel", (0, 0))
            # 反向移动相机以实现拖动效果
            self.camera_manager.move(
                -dx / self.camera_manager.zoom, -dy / self.camera_manager.zoom
            )

            # 限制相机不超出地图范围
            self._constrain_camera(world)

        # 更新鼠标悬停的单位
        self.hover_unit = self._get_unit_at_screen_position(world, mouse_pos)

    def _handle_mouse_click(self, world: World, message: Message) -> None:
        """处理鼠标点击事件，用于选择单位和发出命令"""
        if message.data.get("button") == 1:  # 左键
            mouse_pos = message.data.get("pos", (0, 0))

            # 获取点击位置的单位
            clicked_unit = self._get_unit_at_screen_position(world, mouse_pos)

            if clicked_unit:
                # 获取单位的阵营ID
                unit_stats = world.get_component(clicked_unit, UnitStatsComponent)

                # 检查是否是玩家的单位
                if unit_stats and unit_stats.faction_id == self.player_faction_id:
                    # 选择己方单位
                    self.selected_unit = clicked_unit
                    self.target_unit = None
                    self.move_target = None
                    print(f"选中单位: {unit_stats.name}")

                elif self.selected_unit:
                    # 如果已经有选中的单位，且点击的是其他阵营的单位，发起攻击
                    selected_stats = world.get_component(
                        self.selected_unit, UnitStatsComponent
                    )

                    if selected_stats and self._are_units_hostile(
                        world, self.selected_unit, clicked_unit
                    ):
                        self.target_unit = clicked_unit
                        # 发布攻击命令事件
                        self.event_manager.publish(
                            "ATTACK_COMMAND",
                            Message(
                                topic="ATTACK_COMMAND",
                                data_type="command",
                                data={
                                    "attacker": self.selected_unit,
                                    "target": clicked_unit,
                                },
                            ),
                        )
                        target_stats = world.get_component(
                            clicked_unit, UnitStatsComponent
                        )
                        print(
                            f"攻击目标: {target_stats.name if target_stats else '未知单位'}"
                        )
            else:
                # 如果有选中的玩家单位且点击的是空地，则发送移动命令
                if self.selected_unit:
                    selected_stats = world.get_component(
                        self.selected_unit, UnitStatsComponent
                    )

                    # 确认是玩家阵营单位
                    if (
                        selected_stats
                        and selected_stats.faction_id == self.player_faction_id
                    ):
                        # 转换屏幕坐标为世界坐标
                        world_pos = self.camera_manager.screen_to_world(*mouse_pos)
                        # map_comp = world.get_component(
                        #     self.map_manager.map_entity, MapComponent
                        # )
                        map_entity = world.get_entities_with_components(MapComponent)
                        # map 只有一份
                        map_comp = map_entity[0].get_component(MapComponent)
                        if map_comp:
                            # 将世界坐标转换为格子坐标
                            grid_x = int(world_pos[0] / map_comp.cell_size)
                            grid_y = int(world_pos[1] / map_comp.cell_size)

                            # 检查位置是否有效
                            if self.is_position_valid(map_comp, grid_x, grid_y):
                                self.move_target = (grid_x, grid_y)
                                # 发布移动命令事件
                                self.event_manager.publish(
                                    "MOVE_COMMAND",
                                    Message(
                                        topic="MOVE_COMMAND",
                                        data_type="command",
                                        data={
                                            "unit": self.selected_unit,
                                            "target_x": grid_x,
                                            "target_y": grid_y,
                                        },
                                    ),
                                )
                                print(f"移动命令: 到达 ({grid_x}, {grid_y})")
                    else:
                        # 不是玩家阵营的单位，取消选择
                        self._clear_selection()
                else:
                    # 点击空地且无选中单位，取消选择
                    self._clear_selection()

    def _get_unit_at_screen_position(self, world: World, screen_pos: tuple) -> int:
        """获取屏幕位置对应的单位实体ID

        Args:
            world: 游戏世界
            screen_pos: 屏幕坐标 (x, y)

        Returns:
            int: 单位实体ID，如果没有单位则返回None
        """
        if not self.camera_manager:  # or not self.map_manager:
            return None

        # 获取地图组件
        # map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        map_entity = world.get_entities_with_components(MapComponent)
        # map 只有一份
        map_comp = world.get_component(map_entity[0], MapComponent)
        if not map_comp:
            return None

        # 转换为世界坐标
        world_pos = self.camera_manager.screen_to_world(*screen_pos)
        grid_x = int(world_pos[0] / map_comp.cell_size)
        grid_y = int(world_pos[1] / map_comp.cell_size)

        # 检查是否有单位在该位置
        # for entity, (x, y) in map_comp.entities_positions.items():
        #     precise_pos = world.get_component(entity, PrecisePositionComponent)
        #     if precise_pos:
        #         # 使用精确位置比较
        #         unit_grid_x = precise_pos.grid_x
        #         unit_grid_y = precise_pos.grid_y
        #     else:
        #         unit_grid_x = x
        #         unit_grid_y = y

        #     # 简单判断是否在同一格子
        #     if unit_grid_x == grid_x and unit_grid_y == grid_y:
        #         if world.has_component(entity, UnitStatsComponent):
        #             return entity

        return None

    def _are_units_hostile(self, world: World, unit1: int, unit2: int) -> bool:
        """检查两个单位是否敌对

        Args:
            world: 游戏世界
            unit1: 第一个单位实体ID
            unit2: 第二个单位实体ID

        Returns:
            bool: 如果单位敌对返回True
        """
        stats1 = world.get_component(unit1, UnitStatsComponent)
        stats2 = world.get_component(unit2, UnitStatsComponent)

        if not stats1 or not stats2:
            return False

        # 不同阵营且关系为敌对
        return stats1.faction_id != stats2.faction_id

    def regenerate_map(self, world: World) -> None:
        """重新生成地图

        Args:
            world: 游戏世界
        """
        map_entity = world.get_entities_with_components(MapComponent)
        # map 只有一份
        map_comp = map_entity[0].get_component(MapComponent)
        if not map_comp:
            return

        # 保存尺寸信息
        # width, height = map_comp.width, map_comp.height

        # 清空实体位置字典但保留地图实体
        map_comp.entities_positions = {}

        # 重新生成地图内容
        # self.generate_map(world)

        # 发送地图重生成事件
        self.event_manager.publish(
            "MAP_REGENERATED",
            Message(
                topic="MAP_REGENERATED",
                data_type="map_event",
                data={"map_entity": map_entity},
            ),
        )

    def update(self, world: World, delta_time: float) -> None:
        """更新地图系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 地图系统的更新逻辑，目前为空
        pass

    # def render(self, world: World, render_manager) -> None:
    #         """渲染地图和实体

    #         Args:
    #             world: 游戏世界
    #             render_manager: 渲染管理器
    #         """
    #         # map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
    #         map_entity = world.get_entities_with_components(MapComponent)
    #         # map 只有一份
    #         map_comp = world.get_component(map_entity[0], MapComponent)
    #         if not map_comp:
    #             return

    #         width, height, cell_size = map_comp.width, map_comp.height, map_comp.cell_size
    #         grid = map_comp.grid

    #         # 设置渲染层级为0（最底层）
    #         render_manager.set_layer(0)

    #         # 计算可见区域（如果有相机的话）
    #         if self.camera_manager:
    #             # 转换为格子坐标，略微扩大可见区域以避免边缘问题
    #             screen_left, screen_top = self.camera_manager.screen_to_world(0, 0)
    #             screen_right, screen_bottom = self.camera_manager.screen_to_world(
    #                 self.camera_manager.screen_width, self.camera_manager.screen_height
    #             )

    #             start_x = max(0, int(screen_left / cell_size) - 1)  # 扩展1格
    #             start_y = max(0, int(screen_top / cell_size) - 1)  # 扩展1格
    #             end_x = min(width, int(screen_right / cell_size) + 2)  # 扩展1格
    #             end_y = min(height, int(screen_bottom / cell_size) + 2)  # 扩展1格
    #         else:
    #             # 没有相机时渲染整个地图
    #             start_x, start_y = 0, 0
    #             end_x, end_y = width, height

    #         # 渲染地图网格
    #         for y in range(start_y, end_y):
    #             for x in range(start_x, end_x):
    #                 if y < len(grid) and x < len(grid[y]):
    #                     terrain_type = grid[y][x]

    #                     # 计算单元格位置
    #                     world_x = x * cell_size
    #                     world_y = y * cell_size

    #                     # 应用相机转换（如果有相机）
    #                     if self.camera_manager:
    #                         screen_x, screen_y = self.camera_manager.world_to_screen(
    #                             world_x, world_y
    #                         )
    #                         # 应用缩放因子，使用ceil确保没有缝隙
    #                         cell_width = math.ceil(cell_size * self.camera_manager.zoom) + 1
    #                         cell_height = (
    #                             math.ceil(cell_size * self.camera_manager.zoom) + 1
    #                         )
    #                     else:
    #                         screen_x, screen_y = world_x, world_y
    #                         cell_width = cell_height = cell_size + 1

    #                     # 创建单元格矩形
    #                     rect = pygame.Rect(screen_x, screen_y, cell_width, cell_height)

    #                     # 使用地形渲染器绘制单元格
    #                     cell_surface = pygame.Surface((cell_width, cell_height))
    #                     TerrainRenderer.render_terrain(
    #                         cell_surface, terrain_type, cell_surface.get_rect()
    #                     )
    #                     render_manager.draw(cell_surface, rect)

    #         # 设置渲染层级为1（实体层）
    #         render_manager.set_layer(1)

    #         # 渲染实体 - 处理新的UnitRenderComponent和PrecisePositionComponent
    #         # map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
    #         map_entity = world.get_entities_with_components(MapComponent)
    #         # map 只有一份
    #         map_comp = world.get_component(map_entity[0], MapComponent)
    #         # for entity, (grid_x, grid_y) in map_comp.entities_positions.items():
    #         #     # 检查是否有新的渲染和位置组件
    #         #     unit_render = world.get_component(entity, UnitRenderComponent)
    #         #     precise_pos = world.get_component(entity, UnitPositionComponent)
    #         #     unit_stats = world.get_component(entity, UnitStatsComponent)

    #         #     if unit_render and precise_pos:
    #         #         # 使用精确位置
    #         #         world_x = (
    #         #             precise_pos.grid_x + precise_pos.offset_x
    #         #         ) * map_comp.cell_size
    #         #         world_y = (
    #         #             precise_pos.grid_y + precise_pos.offset_y
    #         #         ) * map_comp.cell_size

    #         #         # 应用相机转换（如果有相机）
    #         #         if self.camera_manager:
    #         #             screen_x, screen_y = self.camera_manager.world_to_screen(
    #         #                 world_x, world_y
    #         #             )
    #         #             # 调整实体大小以适应缩放
    #         #             radius = int(unit_render.size // 2 * self.camera_manager.zoom)
    #         #         else:
    #         #             screen_x, screen_y = world_x, world_y
    #         #             radius = unit_render.size // 2

    #         #         # 检查实体是否在可见区域内
    #         #         if self.camera_manager is None or (
    #         #             0 <= screen_x < self.camera_manager.screen_width
    #         #             and 0 <= screen_y < self.camera_manager.screen_height
    #         #         ):
    #         #             # 绘制单位底圈（用于阵营标识）
    #         #             outline_color = unit_render.main_color
    #         #             main_color = (
    #         #                 min(outline_color[0] + 40, 255),
    #         #                 min(outline_color[1] + 40, 255),
    #         #                 min(outline_color[2] + 40, 255),
    #         #             )

    #         #             # 绘制选中/悬停效果
    #         #             if entity == self.selected_unit:
    #         #                 # 选中单位显示白色边框
    #         #                 render_manager.draw_circle(
    #         #                     (255, 255, 255), (screen_x, screen_y), radius + 3, 2
    #         #                 )
    #         #             elif entity == self.hover_unit:
    #         #                 # 鼠标悬停单位显示灰色边框
    #         #                 render_manager.draw_circle(
    #         #                     (180, 180, 180), (screen_x, screen_y), radius + 2, 1
    #         #                 )

    #         #             if entity == self.target_unit:
    #         #                 # 目标单位显示红色边框
    #         #                 render_manager.draw_circle(
    #         #                     (255, 0, 0), (screen_x, screen_y), radius + 3, 2
    #         #                 )

    #         #             # 绘制单位底圈
    #         #             render_manager.draw_circle(
    #         #                 outline_color, (screen_x, screen_y), radius
    #         #             )

    #         #             # 绘制单位内圈
    #         #             render_manager.draw_circle(
    #         #                 main_color, (screen_x, screen_y), radius - 2
    #         #             )

    #         #             # 渲染单位符号
    #         #             font_size = int(
    #         #                 20 * (self.camera_manager.zoom if self.camera_manager else 1)
    #         #             )
    #         #             font = pygame.font.Font(None, max(14, font_size))

    #         #             # 使用类型特定的符号和颜色
    #         #             symbol_color = (0, 0, 0)  # 默认黑色文字
    #         #             if unit_stats and unit_stats.health < unit_stats.max_health * 0.3:
    #         #                 symbol_color = (255, 0, 0)  # 濒死状态显示红色

    #         #             text = font.render(unit_render.symbol, True, symbol_color)
    #         #             text_rect = text.get_rect(center=(screen_x, screen_y))
    #         #             render_manager.draw(text, text_rect)

    #         #             # 显示血量条
    #         #             if unit_stats:
    #         #                 health_ratio = unit_stats.health / unit_stats.max_health
    #         #                 health_width = radius * 2 * health_ratio
    #         #                 health_height = 3 * self.camera_manager.zoom
    #         #                 health_y_offset = radius + 4

    #         #                 # 背景条
    #         #                 bg_rect = pygame.Rect(
    #         #                     screen_x - radius,
    #         #                     screen_y + health_y_offset,
    #         #                     radius * 2,
    #         #                     health_height,
    #         #                 )
    #         #                 render_manager.draw_rect((50, 50, 50), bg_rect)

    #         #                 # 血量条
    #         #                 health_color = (0, 255, 0)  # 绿色
    #         #                 if health_ratio < 0.3:
    #         #                     health_color = (255, 0, 0)  # 红色
    #         #                 elif health_ratio < 0.7:
    #         #                     health_color = (255, 255, 0)  # 黄色

    #         #                 health_rect = pygame.Rect(
    #         #                     screen_x - radius,
    #         #                     screen_y + health_y_offset,
    #         #                     health_width,
    #         #                     health_height,
    #         #                 )
    #         #                 render_manager.draw_rect(health_color, health_rect)

    #         # 渲染移动目标标记
    #         if self.move_target and self.camera_manager:
    #             target_x, target_y = self.move_target
    #             world_x = target_x * map_comp.cell_size + map_comp.cell_size // 2
    #             world_y = target_y * map_comp.cell_size + map_comp.cell_size // 2
    #             screen_x, screen_y = self.camera_manager.world_to_screen(world_x, world_y)

    #             # 绘制移动目标标记
    #             mark_radius = int(8 * self.camera_manager.zoom)
    #             render_manager.draw_circle(
    #                 (0, 255, 0), (screen_x, screen_y), mark_radius, 2
    #             )

    def is_position_valid(self, map_comp, x, y):
        """检查位置是否在地图范围内且可通行"""

        if not map_comp:
            return False

        # 检查边界
        if x < 0 or x >= map_comp.width or y < 0 or y >= map_comp.height:
            return False

        # 检查地形是否可通行
        terrain_type = map_comp.grid[y][x]
        if terrain_type in [TerrainType.OCEAN]:  # 海洋不可通行
            return False

        return True

    def _handle_faction_switch(self, world: World, message: Message) -> None:
        """处理阵营切换"""
        if message.topic == "KEYDOWN":
            key = message.data
            # 使用数字键1-4切换阵营
            if key == pygame.K_1:
                self.player_faction_id = 1  # 魏国
                self._clear_selection()
                print(f"当前控制阵营: 魏国 (蓝色)")
            elif key == pygame.K_2:
                self.player_faction_id = 2  # 蜀国
                self._clear_selection()
                print(f"当前控制阵营: 蜀国 (红色)")
            elif key == pygame.K_3:
                self.player_faction_id = 3  # 吴国
                self._clear_selection()
                print(f"当前控制阵营: 吴国 (绿色)")
            elif key == pygame.K_4:
                self.player_faction_id = 4  # 黄巾
                self._clear_selection()
                print(f"当前控制阵营: 黄巾 (黄色)")

    def _clear_selection(self):
        """清除当前选择"""
        self.selected_unit = None
        self.target_unit = None
        self.move_target = None
