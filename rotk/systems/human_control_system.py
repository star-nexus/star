import pygame
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    MapComponent,
    UnitStatsComponent,
    UnitPositionComponent,
    UnitRenderComponent,
    UnitStateComponent,
    TerrainType,
    HumanControlComponent,
)

from rotk.managers import CameraManager


class HumanControlSystem(System):
    """人类玩家控制系统，处理玩家的输入和交互"""

    def __init__(self):
        super().__init__([], priority=5)  # 优先级较高，确保输入能立即处理
        self.camera_manager = None
        # self.selected_unit = None  # 当前选中的单位
        # self.hover_unit = None  # 当前鼠标悬停的单位
        # self.target_unit = None  # 当前目标单位（攻击目标）
        # self.move_target = None  # 移动目标位置
        # self.player_faction_id = 2  # 默认玩家控制蜀国

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        camera_manager: CameraManager = None,
    ) -> None:
        """初始化控制系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            camera_manager: 相机管理器
        """
        self.event_manager = event_manager
        self.camera_manager = camera_manager

        # 订阅鼠标事件来处理单位选择
        self.event_manager.subscribe(
            "MOUSEMOTION", lambda message: self._handle_mouse_motion(world, message)
        )
        self.event_manager.subscribe(
            "MOUSEBUTTONDOWN", lambda message: self._handle_mouse_click(world, message)
        )

        # 订阅按键事件以处理阵营切换和相机控制
        self.event_manager.subscribe(
            "KEYDOWN", lambda message: self._handle_key_input(world, message)
        )

    def _handle_mouse_motion(self, world: World, message: Message) -> None:
        """处理鼠标移动事件，控制单位选择悬停"""
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
        # self.hover_unit = self._get_unit_at_screen_position(world, mouse_pos)

    def _handle_mouse_click(self, world: World, message: Message) -> None:
        """处理鼠标点击事件，用于选择单位和发出命令"""
        hc_entity = world.get_unique_entity(HumanControlComponent)
        if not hc_entity:
            return
        hc_comp = world.get_component(hc_entity, HumanControlComponent)

        if message.data.get("button") == 1:  # 左键
            mouse_pos = message.data.get("pos", (0, 0))

            # 获取点击位置的单位
            clicked_unit = self._get_unit_at_screen_position(world, mouse_pos)

            if clicked_unit:
                # 获取单位的阵营ID
                unit_stats = world.get_component(clicked_unit, UnitStatsComponent)

                # 检查是否是玩家的单位
                if unit_stats and unit_stats.faction_id == hc_comp.selected_faction_id:
                    # 选择己方单位
                    hc_comp.selected_unit = clicked_unit
                    hc_comp.target_unit = None
                    hc_comp.selected_position = None
                    print(f"选中单位: {unit_stats.name}")

                    # 发布单位选择事件
                    self.event_manager.publish(
                        "UNIT_SELECTED",
                        Message(
                            topic="UNIT_SELECTED",
                            data_type="unit_event",
                            data={
                                "unit": clicked_unit,
                                "unit_name": unit_stats.name,
                                "faction_id": unit_stats.faction_id,
                            },
                        ),
                    )

                elif hc_comp.selected_unit:
                    # 如果已经有选中的单位，且点击的是其他阵营的单位，发起攻击
                    selected_stats = world.get_component(
                        hc_comp.selected_unit, UnitStatsComponent
                    )

                    # 不同阵营视为敌对
                    if (
                        selected_stats
                        and selected_stats.faction_id != unit_stats.faction_id
                    ):
                        hc_comp.target_unit = clicked_unit

                        # 发布目标选择事件
                        self.event_manager.publish(
                            "TARGET_SELECTED",
                            Message(
                                topic="TARGET_SELECTED",
                                data_type="unit_event",
                                data={
                                    "target": clicked_unit,
                                    "target_name": unit_stats.name,
                                    "target_faction_id": unit_stats.faction_id,
                                },
                            ),
                        )

                        # 发布攻击命令事件
                        self.event_manager.publish(
                            "ATTACK_COMMAND",
                            Message(
                                topic="ATTACK_COMMAND",
                                data_type="command",
                                data={
                                    "attacker": hc_comp.selected_unit,
                                    "target": clicked_unit,
                                },
                            ),
                        )
                        print(f"攻击目标: {unit_stats.name}")
            else:
                # 如果有选中的玩家单位且点击的是空地，则发送移动命令
                if hc_comp.selected_unit:
                    selected_stats = world.get_component(
                        hc_comp.selected_unit, UnitStatsComponent
                    )

                    # 确认是玩家阵营单位
                    if (
                        selected_stats
                        and selected_stats.faction_id == hc_comp.selected_faction_id
                    ):
                        # 转换屏幕坐标为世界坐标
                        world_pos = self.camera_manager.screen_to_world(*mouse_pos)
                        map_entity = world.get_unique_entity(MapComponent)
                        map_comp = world.get_component(map_entity, MapComponent)

                        if map_comp:
                            # 更精确地将世界坐标转换为格子坐标
                            # 使用显式浮点数除法确保精度
                            grid_x = world_pos[0] / map_comp.cell_size
                            grid_y = world_pos[1] / map_comp.cell_size

                            # 保留小数精度，不四舍五入，确保准确定位
                            hc_comp.move_target = (grid_x, grid_y)

                            # 检查位置是否有效
                            if self._is_position_valid(world, map_comp, grid_x, grid_y):
                                # 发布移动命令事件，传递精确坐标
                                self.event_manager.publish(
                                    "MOVE_COMMAND",
                                    Message(
                                        topic="MOVE_COMMAND",
                                        data_type="command",
                                        data={
                                            "unit": hc_comp.selected_unit,
                                            "target_x": grid_x,
                                            "target_y": grid_y,
                                        },
                                    ),
                                )
                                print(f"移动命令: 到达 ({grid_x:.3f}, {grid_y:.3f})")
                    else:
                        # 不是玩家阵营的单位，取消选择
                        self._clear_selection(hc_comp)
                else:
                    # 点击空地且无选中单位，取消选择
                    self._clear_selection(hc_comp)

    def _handle_key_input(self, world: World, message: Message) -> None:
        """处理键盘输入，包括相机控制和阵营切换"""
        key = message.data
        hc_entity = world.get_unique_entity(HumanControlComponent)
        hc_comp = world.get_component(hc_entity, HumanControlComponent)
        # 相机控制
        if self.camera_manager:
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

        # 阵营切换
        if key == pygame.K_1:  # 魏国
            self._switch_faction(hc_comp, 1, "魏国")
        elif key == pygame.K_2:  # 蜀国
            self._switch_faction(hc_comp, 2, "蜀国")
        elif key == pygame.K_3:  # 吴国
            self._switch_faction(hc_comp, 3, "吴国")
        elif key == pygame.K_4:  # 黄巾
            self._switch_faction(hc_comp, 4, "黄巾")

    def _switch_faction(self, hc_comp, faction_id: int, faction_name: str) -> None:
        """切换控制的阵营

        Args:
            faction_id: 阵营ID
            faction_name: 阵营名称
        """

        hc_comp.selected_faction_id = faction_id
        self._clear_selection(hc_comp)
        print(f"当前控制阵营: {faction_name}")

        # 发布阵营切换事件
        self.event_manager.publish(
            "FACTION_SWITCHED",
            Message(
                topic="FACTION_SWITCHED",
                data_type="faction_change",
                data={
                    "faction_id": faction_id,
                    "faction_name": faction_name,
                },
            ),
        )

    def _get_unit_at_screen_position(self, world: World, screen_pos: tuple) -> int:
        """获取屏幕位置对应的单位实体ID"""
        if not self.camera_manager:
            return None

        # 获取地图组件
        map_entity = world.get_unique_entity(MapComponent)
        map_comp = world.get_component(map_entity, MapComponent)
        if not map_comp:
            return None

        # 转换为世界坐标
        world_pos = self.camera_manager.screen_to_world(*screen_pos)

        # 遍历所有单位，检查点击位置
        units = world.get_entities_with_components(
            UnitPositionComponent, UnitRenderComponent
        )

        for entity in units:
            unit_pos = world.get_component(entity, UnitPositionComponent)
            unit_render = world.get_component(entity, UnitRenderComponent)

            if not unit_pos or not unit_render:
                continue

            # 计算单位在世界中的位置
            unit_world_x = unit_pos.x * map_comp.cell_size
            unit_world_y = unit_pos.y * map_comp.cell_size

            # 计算距离
            dx = world_pos[0] - unit_world_x
            dy = world_pos[1] - unit_world_y
            distance = math.sqrt(dx * dx + dy * dy)

            # 检查是否点击在单位上
            click_radius = unit_render.size / 2 * self.camera_manager.zoom
            if distance <= click_radius:
                return entity

        return None

    def _is_position_valid(self, world: World, map_comp, x: float, y: float) -> bool:
        """检查位置是否在地图范围内且可通行"""
        # 转换为整数坐标
        grid_x = int(x)
        grid_y = int(y)

        # 检查边界
        if (
            grid_x < 0
            or grid_x >= map_comp.width
            or grid_y < 0
            or grid_y >= map_comp.height
        ):
            return False

        # 检查地形是否可通行
        terrain_type = map_comp.grid[grid_y][grid_x]
        if terrain_type in [TerrainType.OCEAN]:  # 海洋不可通行
            return False

        return True

    def _constrain_camera(self, world: World) -> None:
        """限制相机不超出地图范围"""
        if not self.camera_manager:
            return

        map_entity = world.get_entities_with_components(MapComponent)
        map_comp = world.get_component(map_entity[0], MapComponent)

        if map_comp:
            self.camera_manager.constrain(
                map_comp.width * map_comp.cell_size,
                map_comp.height * map_comp.cell_size,
                map_comp.cell_size,
            )

    def _clear_selection(self, hc_comp) -> None:
        """清除当前选择"""
        # 清除选择前发送选择取消事件
        if hc_comp.selected_unit:
            self.event_manager.publish(
                "UNIT_DESELECTED",
                Message(
                    topic="UNIT_DESELECTED",
                    data_type="unit_event",
                    data={"unit": hc_comp.selected_unit},
                ),
            )

        hc_comp.selected_unit = None
        hc_comp.target_unit = None
        hc_comp.move_target = None
        hc_comp.selected_position = None
        hc_comp.selection_rect = None  # 清除选择框

    def update(self, world: World, delta_time: float) -> None:
        """更新控制系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 控制系统的更新逻辑，可能包含一些输入状态的处理
        pass
