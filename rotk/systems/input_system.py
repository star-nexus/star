"""
输入处理系统
"""

import pygame
from typing import Tuple, Optional
from framework_v2 import (
    System,
    World,
    QuitEvent,
    KeyDownEvent,
    MouseButtonDownEvent,
    MouseMotionEvent,
)
from framework_v2.engine.events import EBS
from ..components import InputState, UIState, HexPosition, Unit, GameState
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter
from ..events import TileClickedEvent, UnitSelectedEvent


class InputHandlingSystem(System):
    """输入处理系统"""

    def __init__(self):
        super().__init__(priority=10)  # 高优先级
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE)
        # 摄像机偏移：将地图中心(0,0)放在屏幕中心
        self.camera_offset = [
            GameConfig.WINDOW_WIDTH // 2,
            GameConfig.WINDOW_HEIGHT // 2,
        ]

    def initialize(self, world: World) -> None:
        self.world = world
        # 初始化输入状态
        input_state = InputState()
        self.world.add_singleton_component(input_state)

        # 初始化UI状态
        ui_state = UIState()
        self.world.add_singleton_component(ui_state)

    def subscribe_events(self):
        """订阅事件"""
        EBS.subscribe(KeyDownEvent, self._handle_key_down)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def update(self, delta_time: float) -> None:
        """处理输入事件"""
        input_state = self.world.get_singleton_component(InputState)
        ui_state = self.world.get_singleton_component(UIState)

        if not input_state or not ui_state:
            return

        # 处理pygame事件
        # for event in pygame.event.get():
        #     self._handle_event(event, input_state, ui_state)

        # 更新鼠标位置
        mouse_pos = pygame.mouse.get_pos()
        input_state.mouse_pos = mouse_pos

        hex_pos = self._screen_to_hex(mouse_pos)
        ui_state.hovered_tile = hex_pos

        # 处理键盘输入
        keys = pygame.key.get_pressed()
        self._handle_keyboard(keys, input_state, delta_time)

    def _handle_mouse_click(self, event: MouseButtonDownEvent):
        """处理鼠标点击"""
        ui_state = self.world.get_singleton_component(UIState)
        if event.button == 1:  # 左键
            hex_pos = self._screen_to_hex(event.pos)

            if hex_pos:
                # 检查坐标是否在地图范围内 - 使用中心偏移的坐标系
                q, r = hex_pos
                half_width = GameConfig.MAP_WIDTH // 2
                half_height = GameConfig.MAP_HEIGHT // 2

                if -half_width <= q < half_width and -half_height <= r < half_height:
                    self._handle_tile_click(hex_pos, ui_state)

        elif event.button == 3:  # 右键
            # 取消选择
            ui_state.selected_unit = None

    def _handle_tile_click(self, hex_pos: Tuple[int, int], ui_state: UIState):
        """处理地块点击"""
        # 检查是否点击了单位
        clicked_unit = self._get_unit_at_position(hex_pos)

        if clicked_unit:
            # 检查是否是当前玩家的单位
            if self._is_current_player_unit(clicked_unit):
                # 选择单位
                ui_state.selected_unit = clicked_unit
                EBS.publish(UnitSelectedEvent(clicked_unit))
            else:
                # 如果有选中的单位，尝试攻击
                if ui_state.selected_unit:
                    self._try_attack_target(ui_state.selected_unit, clicked_unit)
        else:
            # 点击了空地块
            if ui_state.selected_unit:
                # 尝试移动选中的单位
                self._try_move_unit(ui_state.selected_unit, hex_pos)

        # 发送地块点击事件
        EBS.publish(TileClickedEvent(hex_pos, 1))

    def _handle_key_down(self, event: KeyDownEvent):
        """处理按键按下"""
        ui_state = self.world.get_singleton_component(UIState)
        if event.key == pygame.K_SPACE:
            # 空格键结束回合
            self._end_current_turn()

        elif event.key == pygame.K_TAB:
            # Tab键切换统计界面
            ui_state.show_stats = not ui_state.show_stats

        elif event.key == pygame.K_F1:
            # F1键显示帮助
            ui_state.show_help = not ui_state.show_help

        elif event.key == pygame.K_ESCAPE:
            # ESC键取消选择
            ui_state.selected_unit = None

    def _handle_keyboard(
        self,
        keys: pygame.key.ScancodeWrapper,
        input_state: InputState,
        delta_time: float,
    ):
        """处理持续按键"""
        camera_speed = 200  # 像素/秒

        # 摄像机移动
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.camera_offset[1] += camera_speed * delta_time
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.camera_offset[1] -= camera_speed * delta_time
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.camera_offset[0] += camera_speed * delta_time
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.camera_offset[0] -= camera_speed * delta_time

    def _screen_to_hex(self, screen_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """屏幕坐标转六边形坐标 - 高精度版本"""
        x, y = screen_pos

        # 应用摄像机偏移 - 确保精确的浮点运算
        world_x = float(x) - float(self.camera_offset[0])
        world_y = float(y) - float(self.camera_offset[1])

        # 使用高精度转换
        hex_pos = self.hex_converter.pixel_to_hex(world_x, world_y)

        return hex_pos

    def _hex_to_screen(self, hex_pos: Tuple[int, int]) -> Tuple[float, float]:
        """六边形坐标转屏幕坐标"""
        world_x, world_y = self.hex_converter.hex_to_pixel(*hex_pos)
        screen_x = world_x + self.camera_offset[0]
        screen_y = world_y + self.camera_offset[1]
        return screen_x, screen_y

    def _get_unit_at_position(self, hex_pos: Tuple[int, int]) -> Optional[int]:
        """获取指定位置的单位"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            if position and (position.col, position.row) == hex_pos:
                return entity
        return None

    def _is_current_player_unit(self, unit_entity: int) -> bool:
        """检查是否是当前玩家的单位"""
        game_state = self.world.get_singleton_component(GameState)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not unit:
            return False

        return unit.faction == game_state.current_player

    def _try_attack_target(self, attacker_entity: int, target_entity: int):
        """尝试攻击目标"""
        combat_system = self._get_combat_system()
        if combat_system:
            combat_system.attack(attacker_entity, target_entity)

    def _try_move_unit(self, unit_entity: int, target_pos: Tuple[int, int]):
        """尝试移动单位"""
        movement_system = self._get_movement_system()
        if movement_system:
            movement_system.move_unit(unit_entity, target_pos)

    def _end_current_turn(self):
        """结束当前回合"""
        turn_system = self._get_turn_system()
        if turn_system:
            turn_system.end_turn()

    def _get_combat_system(self):
        """获取战斗系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_movement_system(self):
        """获取移动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None
