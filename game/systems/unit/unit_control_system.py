import pygame
from typing import List, Dict, Tuple, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.engine.events import EventType, EventMessage
from framework.utils.logging_tool import get_logger
from game.components import UnitComponent, UnitState, UnitType
from game.components import MapComponent
from game.components import CameraComponent
from game.utils.game_types import ViewMode


class UnitControlSystem(System):
    """单位控制系统，负责处理玩家对单位的控制操作

    包括：
    1. 框选单位
    2. 移动单位
    3. 切换单位视角
    4. 攻击敌方单位
    5. 控制战争迷雾
    """

    def __init__(self, priority: int = 25):
        """初始化单位控制系统，优先级设置为25（在UnitSystem之后执行）"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("UnitControlSystem")
        self.selected_units: List[Entity] = []  # 当前选中的单位列表
        # 框选相关
        self.selection_start = None  # 框选起始点
        self.is_selecting = False  # 是否正在框选
        self.current_mouse_pos = (0, 0)  # 当前鼠标位置

        # 战争迷雾
        self.fog_of_war_enabled = True  # 战争迷雾是否启用
        self.view_mode = ViewMode.PLAYER  # 视图模式：GLOBAL（全局）或PLAYER（玩家）

        # 当前控制的玩家ID
        self.current_player_id = 0  # 默认为玩家0

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("单位控制系统初始化")

        # 订阅事件
        self.subscribe_events()
        self.logger.info("单位控制系统初始化完成")

    def subscribe_events(self):
        """订阅事件"""
        self.context.event_manager.subscribe(
            [
                EventType.KEY_DOWN,
                EventType.MOUSEBUTTON_DOWN,
                EventType.MOUSEBUTTON_UP,
                EventType.MOUSE_MOTION,
            ],
            self._handle_event,
        )

    def _handle_event(self, event: EventMessage):
        """处理输入事件"""
        self.logger.debug(f"收到事件: 类型:{event.type}, 数据:{event.data}")
        if event.type == EventType.KEY_DOWN:
            self.handle_key_event(event)
        elif event.type == EventType.MOUSEBUTTON_DOWN:
            self.handle_mouse_down_event(event)
        elif event.type == EventType.MOUSEBUTTON_UP:
            self.handle_mouse_up_event(event)
        elif event.type == EventType.MOUSE_MOTION:
            self.handle_mouse_motion_event(event)

    def handle_key_event(self, event: EventMessage):
        """处理键盘事件"""
        key = event.data.get("key")
        self.logger.debug(
            f"处理键盘事件: key={key}, pygame.K_ESCAPE={pygame.K_ESCAPE}, pygame.K_f={pygame.K_f}, pygame.K_TAB={pygame.K_TAB}"
        )

        # ESC键 - 取消选择
        if key == pygame.K_ESCAPE:
            self.logger.info("按下ESC键，取消选择所有单位")
            # 如果正在框选，取消框选
            if self.is_selecting:
                self.is_selecting = False
                self.selection_start = None
                # 发送选择框取消事件
                if self.context and self.context.event_manager:
                    self.context.event_manager.publish(
                        EventMessage(EventType.SELECTION_BOX_CANCELED, {})
                    )
                    self.logger.debug("已发布选择框取消事件")
            self.deselect_all_units()

        # F键 - 切换战争迷雾
        elif key == pygame.K_f:
            self.logger.info("按下F键，切换战争迷雾")
            self.toggle_fog_of_war()

        # 数字键1-4 - 切换控制的玩家
        elif pygame.K_1 <= key <= pygame.K_4:
            player_id = key - pygame.K_1  # 转换为玩家ID 0-3
            self.logger.info(f"按下数字键{key - pygame.K_0}，切换到控制玩家{player_id}")
            self.switch_player(player_id)

        # 数字键5-9 - 快速选择对应编号的单位
        elif pygame.K_5 <= key <= pygame.K_9:
            num = key - pygame.K_0  # 转换为数字5-9
            self.logger.info(f"按下数字键{num}，快速选择单位")
            self.quick_select_unit(num)

        # Tab键 - 在已选择的单位间切换
        elif key == pygame.K_TAB:
            self.logger.info("按下Tab键，循环切换选中的单位")
            self.cycle_selected_units()

    def handle_mouse_down_event(self, event: EventMessage):
        """处理鼠标按下事件"""
        button = event.data.get("button")
        pos = event.data.get("pos", (0, 0))

        self.logger.debug(
            f"鼠标按下事件: 按钮={button}, 位置={pos}, 事件数据={event.data}"
        )

        # 左键 - 选择单位或开始框选
        if button == 1:  # 左键
            # 如果按住Shift键，则是多选模式
            is_multi_select = pygame.key.get_mods() & pygame.KMOD_SHIFT
            self.logger.debug(
                f"多选模式: {is_multi_select}, Shift状态: {pygame.key.get_mods() & pygame.KMOD_SHIFT}"
            )

            # 尝试选择单位，如果没有选中单位则开始框选
            if not is_multi_select and not self._try_select_unit_at_position(pos):
                self.logger.info(f"未选中单位，开始框选，起始位置: {pos}")
                self.start_box_selection(pos)
            else:
                self.logger.info(
                    f"尝试选择单位结果: {'成功' if self._try_select_unit_at_position(pos) else '失败'}"
                )

        # 右键 - 移动或攻击
        elif button == 3:  # 右键
            self.logger.info(
                f"右键点击: {pos}, 当前选中单位数: {len(self.selected_units)}"
            )
            self.handle_right_click(pos)

    def handle_mouse_up_event(self, event: EventMessage):
        """处理鼠标释放事件"""
        button = event.data.get("button")
        pos = event.data.get("pos", (0, 0))

        self.logger.debug(
            f"鼠标释放事件: 按钮={button}, 位置={pos}, 是否正在框选={self.is_selecting}, 框选起始点={self.selection_start}"
        )

        # 左键释放 - 完成框选
        if button == 1 and self.is_selecting:
            self.logger.info(f"完成框选: 从 {self.selection_start} 到 {pos}")
            self.complete_box_selection(pos)
        else:
            self.logger.debug(
                f"忽略鼠标释放事件: button={button}, is_selecting={self.is_selecting}"
            )

    def handle_mouse_motion_event(self, event: EventMessage):
        """处理鼠标移动事件"""
        pos = event.data.get("pos", (0, 0))

        # 仅在框选状态下处理
        if self.is_selecting:
            # 记录当前鼠标位置用于实时显示选择框
            self.current_mouse_pos = pos
            self.logger.debug(f"框选更新: 从 {self.selection_start} 到 {pos}")

            # 发布一个事件通知渲染系统绘制选择框
            if self.context and self.context.event_manager:
                self.context.event_manager.publish(
                    EventMessage(
                        EventType.SELECTION_BOX_RENDERING,
                        {
                            "start": self.selection_start,
                            "end": pos,
                        },
                    )
                )
                self.logger.debug("已发布选择框更新事件")

    def update(self, delta_time: float):
        """更新单位控制系统"""
        if not self.is_enabled():
            return

        # # 添加调试信息，每秒输出一次系统状态
        # if hasattr(self, "_debug_timer"):
        #     self._debug_timer += delta_time
        #     if self._debug_timer >= 5.0:  # 每5秒输出一次
        #         self._debug_timer = 0.0
        #         selected_unit_names = []
        #         for entity in self.selected_units:
        #             unit = self.context.get_component(entity, UnitComponent)
        #             if unit:
        #                 selected_unit_names.append(f"{unit.name}({unit.unit_type})")

        #         self.logger.debug(
        #             f"单位控制系统状态: 选中单位数={len(self.selected_units)}, "
        #             f"框选状态={self.is_selecting}, "
        #             f"选中单位={', '.join(selected_unit_names) if selected_unit_names else '无'}"
        #         )
        # else:
        #     self._debug_timer = 0.0

        # 如果正在框选，更新选择框
        if (
            self.is_selecting
            and self.selection_start
            and hasattr(self, "current_mouse_pos")
        ):
            pass

    def start_box_selection(self, pos: Tuple[int, int]):
        """开始框选"""
        self.selection_start = pos
        self.is_selecting = True
        self.logger.debug(f"开始框选，起始位置: {pos}")

    def complete_box_selection(self, end_pos: Tuple[int, int]):
        """完成框选，选择框内的所有单位"""
        if not self.selection_start:
            return

        # 获取相机组件
        camera_comp = self._get_camera_component()
        if not camera_comp:
            self.logger.warning("未找到相机组件，无法处理框选")
            self.is_selecting = False
            self.selection_start = None
            return

        # 计算选择框范围（屏幕坐标）
        start_x, start_y = self.selection_start
        end_x, end_y = end_pos

        # 确保start是左上角，end是右下角（屏幕坐标）
        screen_left = min(start_x, end_x)
        screen_top = min(start_y, end_y)
        screen_right = max(start_x, end_x)
        screen_bottom = max(start_y, end_y)

        # 如果选择框太小，视为点击
        if abs(screen_right - screen_left) < 5 and abs(screen_bottom - screen_top) < 5:
            self.is_selecting = False
            self.selection_start = None
            # 发送选择框取消事件
            if self.context and self.context.event_manager:
                self.context.event_manager.publish(
                    EventMessage(EventType.SELECTION_BOX_CANCELED, {})
                )
                self.logger.debug("已发布选择框取消事件")
            return

        # 将屏幕坐标框转换为世界坐标框
        world_start = self._screen_to_world(screen_left, screen_top, camera_comp)
        world_end = self._screen_to_world(screen_right, screen_bottom, camera_comp)

        # 确保世界坐标中的左上和右下
        world_left = min(world_start[0], world_end[0])
        world_top = min(world_start[1], world_end[1])
        world_right = max(world_start[0], world_end[0])
        world_bottom = max(world_start[1], world_end[1])

        # 清除之前的选择（除非按住Shift键）
        if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
            self.deselect_all_units()

        # 选择框内的所有单位
        selected_count = 0
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if not unit or unit.state == UnitState.DEAD:
                continue

            # 单位位置是世界坐标
            unit_x, unit_y = unit.position_x, unit.position_y

            # 检查单位是否在选择框内（世界坐标）
            if (
                world_left <= unit_x <= world_right
                and world_top <= unit_y <= world_bottom
            ):
                # 只选择当前玩家的单位
                if unit.owner_id == self.current_player_id:
                    unit.is_selected = True
                    if entity not in self.selected_units:
                        self.selected_units.append(entity)
                        selected_count += 1

        self.logger.info(f"框选完成，选中了 {selected_count} 个单位")
        self.is_selecting = False
        self.selection_start = None

        # 发送选择框完成事件
        if self.context and self.context.event_manager:
            self.context.event_manager.publish(
                EventMessage(
                    EventType.SELECTION_BOX_COMPLETED,
                    {},
                )
            )
            self.logger.debug("已发布选择框完成事件")

    def _get_camera_component(self):
        """获取相机组件"""
        camera_entity = self.context.with_all(CameraComponent).first()
        if not camera_entity:
            return None
        return self.context.get_component(camera_entity, CameraComponent)

    def _screen_to_world(
        self, screen_x: int, screen_y: int, camera_comp
    ) -> Tuple[float, float]:
        """将屏幕坐标转换为世界坐标"""
        if not camera_comp:
            return (0, 0)
        # 计算相对于相机的偏移
        world_x = (screen_x - camera_comp.width / 2) / camera_comp.zoom + camera_comp.x
        world_y = (screen_y - camera_comp.height / 2) / camera_comp.zoom + camera_comp.y
        return (world_x, world_y)

    def _world_to_screen(
        self, world_x: float, world_y: float, camera_comp
    ) -> Tuple[int, int]:
        """将世界坐标转换为屏幕坐标"""
        if not camera_comp:
            return (0, 0)
        # 计算相对于相机的偏移
        screen_x = int(
            (world_x - camera_comp.x) * camera_comp.zoom + camera_comp.width / 2
        )
        screen_y = int(
            (world_y - camera_comp.y) * camera_comp.zoom + camera_comp.height / 2
        )
        return (screen_x, screen_y)

    def _try_select_unit_at_position(self, pos: Tuple[int, int]) -> bool:
        """尝试选择指定位置的单位，返回是否成功选中"""
        mouse_x, mouse_y = pos
        self.logger.debug(f"尝试选择单位，屏幕坐标: ({mouse_x}, {mouse_y})")

        # 获取相机组件
        camera_comp = self._get_camera_component()
        if not camera_comp:
            self.logger.warning("未找到相机组件，无法处理单位选择")
            return False

        # 将屏幕坐标转换为世界坐标
        world_x, world_y = self._screen_to_world(mouse_x, mouse_y, camera_comp)
        self.logger.debug(f"转换为世界坐标: ({world_x:.2f}, {world_y:.2f})")

        # 检查是否点击到了单位
        clicked_entity = None
        clicked_unit = None

        # 遍历所有单位，查找点击位置的单位
        unit_count = 0
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            unit_count += 1
            if not unit or unit.state == UnitState.DEAD:
                continue

            # 计算点击位置与单位位置的距离（在世界坐标系中）
            distance = (
                (world_x - unit.position_x) ** 2 + (world_y - unit.position_y) ** 2
            ) ** 0.5

            # 记录单位位置和距离，便于调试
            self.logger.debug(
                f"单位 {unit.name}(ID:{entity}) 位置: ({unit.position_x:.2f}, {unit.position_y:.2f}), "
                f"距离: {distance:.2f}, 尺寸: {unit.unit_size}, 所有者: {unit.owner_id}"
            )

            if distance <= unit.unit_size * 0.5:  # 半径为单位尺寸的一半
                clicked_entity = entity
                clicked_unit = unit
                self.logger.info(
                    f"找到点击的单位: {unit.name}(ID:{entity}), 距离: {distance:.2f}, 所有者: {unit.owner_id}"
                )
                break

        self.logger.debug(f"场景中共有 {unit_count} 个单位")

        if clicked_entity:
            # 如果按住Shift键，则是多选模式
            is_multi_select = pygame.key.get_mods() & pygame.KMOD_SHIFT
            self.logger.debug(
                f"多选模式: {is_multi_select}, Shift状态: {pygame.key.get_mods()}"
            )

            # 只选择当前玩家的单位
            if clicked_unit.owner_id != self.current_player_id:
                self.logger.info(
                    f"忽略非当前玩家单位: {clicked_unit.name}, 所有者ID: {clicked_unit.owner_id}, 当前玩家ID: {self.current_player_id}"
                )
                return False

            if not is_multi_select:
                # 单选模式：取消之前的选择
                self.logger.info("单选模式: 取消之前的所有选择")
                self.deselect_all_units()

            # 如果单位已经被选中，则取消选择；否则选中它
            if clicked_unit.is_selected and is_multi_select:
                clicked_unit.is_selected = False
                if clicked_entity in self.selected_units:
                    self.selected_units.remove(clicked_entity)
                self.logger.info(f"取消选择单位: {clicked_unit.name}(ID:{entity})")
            else:
                clicked_unit.is_selected = True
                if clicked_entity not in self.selected_units:
                    self.selected_units.append(clicked_entity)
                self.logger.info(
                    f"选择单位: {clicked_unit.name}(ID:{entity}), 当前选中单位数: {len(self.selected_units)}"
                )

            return True

        self.logger.debug("未找到点击位置的单位")
        return False

    def handle_right_click(self, pos: Tuple[int, int]):
        """处理右键点击（移动或攻击）"""
        # 如果正在框选，取消框选
        if self.is_selecting:
            self.is_selecting = False
            self.selection_start = None
            # 发送选择框取消事件
            if self.context and self.context.event_manager:
                self.context.event_manager.publish(
                    EventMessage(EventType.SELECTION_BOX_CANCELED, {})
                )
                self.logger.debug("右键点击，已发布选择框取消事件")
            return

        if not self.selected_units:
            self.logger.info("没有选中的单位，忽略右键点击")
            return

        mouse_x, mouse_y = pos
        self.logger.info(
            f"处理右键点击，屏幕坐标: ({mouse_x}, {mouse_y})，选中单位数: {len(self.selected_units)}"
        )

        # 获取相机组件
        camera_comp = self._get_camera_component()
        if not camera_comp:
            self.logger.warning("未找到相机组件，无法处理右键点击")
            return

        # 将屏幕坐标转换为世界坐标
        world_x, world_y = self._screen_to_world(mouse_x, mouse_y, camera_comp)
        self.logger.info(f"转换为世界坐标: ({world_x:.2f}, {world_y:.2f})")

        # 检查是否点击到了敌方单位（攻击）
        target_entity = None
        target_unit = None

        # 遍历所有单位，查找点击位置的敌方单位
        enemy_count = 0
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if not unit or unit.state == UnitState.DEAD:
                continue

            # 跳过己方单位
            if unit.owner_id == self.current_player_id:
                continue

            enemy_count += 1

            # 计算点击位置与单位位置的距离（在世界坐标系中）
            distance = (
                (world_x - unit.position_x) ** 2 + (world_y - unit.position_y) ** 2
            ) ** 0.5

            self.logger.debug(
                f"敌方单位 {unit.name}(ID:{entity}) 位置: ({unit.position_x:.2f}, {unit.position_y:.2f}), "
                f"距离: {distance:.2f}, 尺寸: {unit.unit_size}, 所有者: {unit.owner_id}"
            )

            if distance <= unit.unit_size * 0.5:  # 半径为单位尺寸的一半
                target_entity = entity
                target_unit = unit
                self.logger.info(
                    f"找到点击的敌方单位: {unit.name}(ID:{entity}), 距离: {distance:.2f}, 所有者: {unit.owner_id}"
                )
                break

        self.logger.info(f"场景中共有 {enemy_count} 个敌方单位")

        # 如果点击到敌方单位，则攻击
        if target_entity:
            self.logger.info(
                f"命令选中的 {len(self.selected_units)} 个单位攻击目标: {target_unit.name}(ID:{target_entity})"
            )
            for entity in self.selected_units:
                unit_comp = self.context.get_component(entity, UnitComponent)
                if unit_comp:
                    self.logger.info(
                        f"单位 {unit_comp.name}(ID:{entity}) 攻击敌方单位 {target_unit.name}(ID:{target_entity})"
                    )
                    try:
                        # unit_system.attack_unit(entity, target_entity)
                        self.context.event_manager.publish(
                            EventMessage(
                                EventType.UNIT_ATTACKED,
                                {"entity": entity, "target": target_entity},
                            )
                        )
                        self.logger.debug(
                            f"攻击命令已发送: {entity} -> {target_entity}"
                        )
                    except Exception as e:
                        self.logger.error(f"攻击命令失败: {e}")
                else:
                    self.logger.warning(f"无法获取单位组件: {entity}")
        else:
            # 否则移动到目标位置（使用世界坐标）
            self.logger.info(
                f"命令选中的 {len(self.selected_units)} 个单位移动到世界坐标 ({world_x:.1f}, {world_y:.1f})"
            )
            for entity in self.selected_units:
                unit_comp = self.context.get_component(entity, UnitComponent)
                if unit_comp:
                    self.logger.info(
                        f"单位 {unit_comp.name}(ID:{entity}) 正在移动到 ({world_x:.1f}, {world_y:.1f})"
                    )
                    try:
                        # unit_system.move_unit(entity, world_x, world_y)
                        self.context.event_manager.publish(
                            EventMessage(
                                EventType.UNIT_MOVED,
                                {
                                    "entity": entity,
                                    "target_x": float("{:.1f}".format(world_x)),
                                    "target_y": float("{:.1f}".format(world_y)),
                                },
                            )
                        )
                        self.logger.debug(
                            f"移动命令已发送: {entity} -> ({world_x:.1f}, {world_y:.1f})"
                        )
                    except Exception as e:
                        self.logger.error(f"移动命令失败: {e}")
                else:
                    self.logger.warning(f"无法获取单位组件: {entity}")

    def deselect_all_units(self):
        """取消选择所有单位"""
        for entity in self.selected_units:
            unit = self.context.get_component(entity, UnitComponent)
            if unit:
                unit.is_selected = False

        self.selected_units.clear()
        self.logger.info("取消选择所有单位")

    def toggle_fog_of_war(self):
        """切换战争迷雾状态"""
        self.fog_of_war_enabled = not self.fog_of_war_enabled
        self.logger.info(f"战争迷雾已{'启用' if self.fog_of_war_enabled else '禁用'}")

        # 发布迷雾切换事件
        if self.context and self.context.event_manager:
            self.context.event_manager.publish(
                EventMessage(
                    EventType.FOG_OF_WAR_TOGGLED, {"enabled": self.fog_of_war_enabled}
                )
            )

    def toggle_view_mode(self):
        """切换视图模式（全局/玩家）"""
        # 在全局和玩家视角之间切换
        if self.view_mode == ViewMode.GLOBAL:
            self.view_mode = ViewMode.PLAYER
            self.logger.info("切换到玩家视角模式")
        else:
            self.view_mode = ViewMode.GLOBAL
            self.logger.info("切换到全局视角模式")

        # 发布视图模式切换事件
        if self.context and self.context.event_manager:
            self.context.event_manager.publish(
                EventMessage(
                    EventType.FOG_OF_WAR_TOGGLED, {"view_mode": self.view_mode}
                )
            )

    def quick_select_unit(self, index: int):
        """快速选择指定编号的单位"""
        # 这里可以实现根据编号快速选择单位的逻辑
        # 例如，可以预先为重要单位分配编号
        self.logger.info(f"快速选择编号为 {index} 的单位")

    def cycle_selected_units(self):
        """在已选择的单位间循环切换"""
        if not self.selected_units:
            return

        # 取消当前所有选择
        for entity in self.selected_units:
            unit = self.context.get_component(entity, UnitComponent)
            if unit:
                unit.is_selected = False

        # 将第一个单位移到列表末尾，实现循环
        entity = self.selected_units.pop(0)
        self.selected_units.append(entity)

        # 选中新的第一个单位
        unit = self.context.get_component(self.selected_units[0], UnitComponent)
        if unit:
            unit.is_selected = True
            self.logger.info(f"切换到单位: {unit.name}")

            # 可以添加相机聚焦到该单位的逻辑
            # 例如发布一个事件，让CameraSystem处理
            if self.context.event_manager:
                self.context.event_manager.publish(
                    EventMessage(
                        EventType.CUSTOM_EVENT,
                        {
                            "event_name": "FOCUS_UNIT",
                            "entity": self.selected_units[0],
                            "position": (unit.position_x, unit.position_y),
                        },
                    )
                )

    def switch_player(self, player_id: int):
        """切换控制的玩家

        Args:
            player_id: 要切换到的玩家ID (0-3)
        """
        if player_id < 0 or player_id > 3:
            self.logger.warning(f"无效的玩家ID: {player_id}，有效范围为0-3")
            return

        # 如果是同一个玩家，不做任何操作
        if player_id == self.current_player_id:
            self.logger.info(f"已经是玩家{player_id}，无需切换")
            return

        # 切换玩家前，取消所有选中的单位
        self.deselect_all_units()

        # 更新当前玩家ID
        old_player_id = self.current_player_id
        self.current_player_id = player_id
        self.logger.info(f"已切换控制玩家: 从 {old_player_id} 到 {player_id}")

        # 发布玩家切换事件
        if self.context and self.context.event_manager:
            self.context.event_manager.publish(
                EventMessage(EventType.PLAYER_SWITCHED, {"player_id": player_id})
            )
            self.logger.debug(f"已发布玩家切换事件: 从 {old_player_id} 到 {player_id}")
