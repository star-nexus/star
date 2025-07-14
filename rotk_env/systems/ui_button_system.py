"""
UI按钮系统 - 处理UI按钮的渲染、交互和回调
"""

import pygame
from pathlib import Path
from framework import System, RMS
from ..components import (
    UIButton,
    UIButtonCollection,
    UIPanel,
    InputState,
    GameState,
    TurnManager,
    Player,
    UIState,
)
from ..prefabs.config import GameConfig


class UIButtonSystem(System):
    """UI按钮系统"""

    def __init__(self):
        super().__init__(priority=2)  # 高优先级，在UI渲染之前处理
        self.font = None
        self.button_font = None

        # 初始化字体
        pygame.font.init()
        try:
            file_path = Path("rotk_env/assets/fonts/sh.otf")
            self.font = pygame.font.Font(file_path, 18)
            self.button_font = pygame.font.Font(file_path, 16)
        except:
            # 使用默认字体作为后备
            self.font = pygame.font.Font(None, 18)
            self.button_font = pygame.font.Font(None, 16)

    def initialize(self, world) -> None:
        """初始化按钮系统"""
        self.world = world
        self._create_ui_buttons()

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新按钮系统"""
        self._update_button_states()
        self._handle_button_clicks()
        self._render_buttons()

    def _create_ui_buttons(self):
        """创建UI按钮"""
        # 创建按钮集合单例组件
        button_collection = UIButtonCollection()
        self.world.add_singleton_component(button_collection)

        print("正在创建UI按钮...")  # 调试输出

        # 创建结束回合按钮
        end_turn_button = self.world.create_entity()
        self.world.add_component(
            end_turn_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 150,
                y=GameConfig.WINDOW_HEIGHT - 60,
                width=140,
                height=40,
                text="结束回合",
                background_color=(80, 120, 80),
                hover_color=(100, 150, 100),
                callback_name="end_turn",
            ),
        )
        button_collection.add_button("end_turn", end_turn_button)
        print(f"✓ 创建结束回合按钮 (实体ID: {end_turn_button})")

        # 创建设置按钮
        settings_button = self.world.create_entity()
        self.world.add_component(
            settings_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 80,
                y=10,
                width=70,
                height=30,
                text="设置",
                background_color=(100, 100, 100),
                hover_color=(130, 130, 130),
                callback_name="show_settings",
            ),
        )
        button_collection.add_button("settings", settings_button)
        print(f"✓ 创建设置按钮 (实体ID: {settings_button})")

        # 创建帮助按钮
        help_button = self.world.create_entity()
        self.world.add_component(
            help_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 160,
                y=10,
                width=70,
                height=30,
                text="帮助",
                background_color=(80, 80, 120),
                hover_color=(100, 100, 150),
                callback_name="toggle_help",
            ),
        )
        button_collection.add_button("help", help_button)
        print(f"✓ 创建帮助按钮 (实体ID: {help_button})")

        # 创建统计按钮
        stats_button = self.world.create_entity()
        self.world.add_component(
            stats_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 240,
                y=10,
                width=70,
                height=30,
                text="统计",
                background_color=(120, 80, 80),
                hover_color=(150, 100, 100),
                callback_name="toggle_stats",
            ),
        )
        button_collection.add_button("stats", stats_button)
        print(f"✓ 创建统计按钮 (实体ID: {stats_button})")

        print("UI按钮创建完成！")

    def _update_button_states(self):
        """更新按钮状态"""
        input_state = self.world.get_singleton_component(InputState)
        if not input_state:
            return

        mouse_x, mouse_y = input_state.mouse_pos

        # 更新所有按钮的悬停状态
        for entity in self.world.query().with_component(UIButton).entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_enabled or not button.is_visible:
                continue

            # 检查鼠标是否在按钮上
            is_hovered = (
                button.x <= mouse_x <= button.x + button.width
                and button.y <= mouse_y <= button.y + button.height
            )
            button.is_hovered = is_hovered

    def _handle_button_clicks(self):
        """处理按钮点击"""
        input_state = self.world.get_singleton_component(InputState)
        if not input_state:
            return

        # 检查鼠标左键是否刚刚按下
        if 1 not in input_state.mouse_pressed:  # 1 是左键
            return

        mouse_x, mouse_y = input_state.mouse_pos

        # 检查点击的按钮
        for entity in self.world.query().with_component(UIButton).entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_enabled or not button.is_visible:
                continue

            # 检查点击是否在按钮内
            if (
                button.x <= mouse_x <= button.x + button.width
                and button.y <= mouse_y <= button.y + button.height
            ):
                self._handle_button_callback(button)
                break

    def _handle_button_callback(self, button: UIButton):
        """处理按钮回调"""
        if not button.callback_name:
            return

        print(f"按钮被点击: {button.text} (回调: {button.callback_name})")  # 调试输出

        # 根据回调名称执行相应的功能
        if button.callback_name == "end_turn":
            self._end_turn()
        elif button.callback_name == "show_settings":
            self._show_settings()
        elif button.callback_name == "toggle_help":
            self._toggle_help()
        elif button.callback_name == "toggle_stats":
            self._toggle_stats()

    def _end_turn(self):
        """结束当前回合"""
        print("执行结束回合操作...")  # 调试输出

        game_state = self.world.get_singleton_component(GameState)
        turn_manager = self.world.get_singleton_component(TurnManager)

        if not game_state or not turn_manager:
            print("无法获取游戏状态或回合管理器")
            return

        # 切换到下一个玩家
        current_index = turn_manager.current_player_index
        turn_manager.next_player()

        # 如果回到第一个玩家，增加回合数
        if turn_manager.current_player_index == 0:
            game_state.turn_number += 1
            print(f"新回合开始: {game_state.turn_number}")

        # 更新当前玩家
        current_player_entity = turn_manager.get_current_player()
        if current_player_entity:
            player = self.world.get_component(current_player_entity, Player)
            if player:
                game_state.current_player = player.faction
                print(f"切换到玩家: {player.faction.value}")

    def _show_settings(self):
        """显示设置面板"""
        print("显示设置面板")  # 临时实现

    def _toggle_help(self):
        """切换帮助面板显示"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.show_help = not ui_state.show_help
            print(f"帮助面板: {'显示' if ui_state.show_help else '隐藏'}")

    def _toggle_stats(self):
        """切换统计面板显示"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.show_stats = not ui_state.show_stats
            print(f"统计面板: {'显示' if ui_state.show_stats else '隐藏'}")

    def _render_buttons(self):
        """渲染所有按钮"""
        for entity in self.world.query().with_component(UIButton).entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_visible:
                continue

            self._render_button(button)

    def _render_button(self, button: UIButton):
        """渲染单个按钮"""
        # 选择背景颜色
        if button.is_hovered and button.is_enabled:
            bg_color = button.hover_color
        else:
            bg_color = button.background_color

        # 如果按钮被禁用，使用较暗的颜色
        if not button.is_enabled:
            bg_color = tuple(c // 2 for c in bg_color)

        # 创建按钮表面
        button_surface = pygame.Surface((button.width, button.height))
        button_surface.fill(bg_color)

        # 绘制边框
        if button.border_width > 0:
            border_color = button.border_color
            if not button.is_enabled:
                border_color = tuple(c // 2 for c in border_color)
            pygame.draw.rect(
                button_surface,
                border_color,
                (0, 0, button.width, button.height),
                button.border_width,
            )

        # 渲染文本
        text_color = button.text_color
        if not button.is_enabled:
            text_color = tuple(c // 2 for c in text_color)

        text_surface = self.button_font.render(button.text, True, text_color)
        text_rect = text_surface.get_rect(
            center=(button.width // 2, button.height // 2)
        )
        button_surface.blit(text_surface, text_rect)

        # 绘制到屏幕
        RMS.draw(button_surface, (button.x, button.y))
