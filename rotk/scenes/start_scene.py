"""
开始场景
Start Scene
"""

import pygame
from typing import Dict, Any, Optional
from framework_v2 import (
    World,
    RMS,
    EBS,
    MouseButtonDownEvent,
    MouseMotionEvent,
    Event,
    KeyDownEvent,
    QuitEvent,
)
from framework_v2.engine.scenes import Scene
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import StartMenuConfig, StartMenuButtons, StartMenuOptions
from ..systems.start_scene_render_system import StartSceneRenderSystem


class StartScene(Scene):
    """开始场景类"""

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "start"
        self.world = World()
        self.game_config = None  # 将传递给GameScene的配置

    def enter(self, **kwargs) -> None:
        """进入场景时调用"""
        super().enter(**kwargs)
        # 创建配置实体
        self.world.add_singleton_component(StartMenuConfig())

        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        # 定义按钮
        buttons = {
            "start_game": {
                "text": "开始游戏",
                "rect": pygame.Rect(
                    screen_width // 2 - 100, screen_height - 150, 200, 50
                ),
                "hover": False,
                "default_color": (60, 80, 120),
                "hover_color": (80, 100, 140),
                "action": self._start_game,
            },
            "quit": {
                "text": "退出游戏",
                "rect": pygame.Rect(
                    screen_width // 2 - 100, screen_height - 80, 200, 50
                ),
                "hover": False,
                "default_color": (60, 80, 120),
                "hover_color": (80, 100, 140),
                "action": self._quit_game,
            },
        }

        options = {}
        # 创建配置选项组件

        self.world.add_singleton_component(
            StartMenuButtons(buttons=buttons, options=options)
        )

        # 初始化渲染系统
        self.world.add_system(StartSceneRenderSystem())
        self.subscribe_events()

    def subscribe_events(self) -> None:
        EBS.subscribe(MouseMotionEvent, self._update_hover_state)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)
        # EBS.subscribe(KeyDownEvent, self._handle_key_down)

    def update(self, dt: float) -> None:
        """更新场景"""

        # 更新渲染系统
        self.world.update(dt)

    def _update_hover_state(self, event: MouseMotionEvent) -> None:
        """更新悬停状态"""
        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if not buttons_component:
            return

        # 检查按钮悬停
        for button_name, button in buttons_component.buttons.items():
            if button["rect"].collidepoint(event.pos):
                button["hover"] = True
            else:
                button["hover"] = False

        # self.render_system.set_hover_button(hover_button)

        # 检查配置选项悬停
        # self._update_option_hover()

    def _update_option_hover(self) -> None:
        """更新选项悬停状态"""
        pass
        # 获取屏幕尺寸
        # screen_width = GameConfig.WINDOW_WIDTH
        # screen_height = GameConfig.WINDOW_HEIGHT
        # # 面板位置
        # panel_x = (screen_width - 600) // 2
        # panel_y = 200

        # # 检查各种选项的悬停
        # hover_option = None

        # # 游戏模式选项
        # mode_y = panel_y + 70
        # for i, mode in enumerate([GameMode.TURN_BASED, GameMode.REAL_TIME]):
        #     option_rect = pygame.Rect(panel_x + 50 + i * 150, mode_y, 120, 30)
        #     if option_rect.collidepoint(self.mouse_pos):
        #         hover_option = f"mode_{mode.value}"
        #         break

        # # 玩家配置选项
        # if not hover_option:
        #     player_y = panel_y + 170
        #     for i in range(3):  # 三个玩家配置选项
        #         option_rect = pygame.Rect(panel_x + 50, player_y + i * 30, 200, 30)
        #         if option_rect.collidepoint(self.mouse_pos):
        #             hover_option = f"player_{i}"
        #             break

        # # 场景配置选项
        # if not hover_option:
        #     scenario_y = panel_y + 270
        #     for i in range(3):  # 三个场景选项
        #         option_rect = pygame.Rect(panel_x + 50, scenario_y + i * 30, 200, 30)
        #         if option_rect.collidepoint(self.mouse_pos):
        #             hover_option = f"scenario_{i}"
        #             break

        # self.render_system.set_hover_option(hover_option)

    def _handle_mouse_click(self, event: MouseButtonDownEvent) -> None:
        """处理鼠标点击"""
        pos = event.pos
        # 检查按钮点击
        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if buttons_component:
            for button_name, button in buttons_component.buttons.items():
                if button["rect"].collidepoint(pos):
                    button["action"]()
                    return

        # 检查配置选项点击
        self._handle_config_click(pos)

    def _handle_config_click(self, pos: tuple) -> None:
        """处理配置选项点击"""
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        # 面板位置
        panel_x = (screen_width - 600) // 2
        panel_y = 200

        # 检查游戏模式选项点击
        mode_y = panel_y + 90
        for i, mode in enumerate([GameMode.TURN_BASED, GameMode.REAL_TIME]):
            option_rect = pygame.Rect(panel_x + 50 + i * 150, mode_y, 120, 30)
            if option_rect.collidepoint(pos):
                config.selected_mode = mode
                return

        # 检查玩家配置选项点击
        player_y = panel_y + 190
        player_configs = [
            {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
            {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
            {
                Faction.WEI: PlayerType.HUMAN,
                Faction.SHU: PlayerType.AI,
                Faction.WU: PlayerType.AI,
            },
        ]

        for i, player_config in enumerate(player_configs):
            option_rect = pygame.Rect(panel_x + 50, player_y + i * 30, 200, 30)
            if option_rect.collidepoint(pos):
                config.selected_players = player_config.copy()
                return

        # # 检查场景配置选项点击
        # scenario_y = panel_y + 290
        # scenarios = ["default", "plains", "mountains"]
        # for i, scenario in enumerate(scenarios):
        #     option_rect = pygame.Rect(panel_x + 50, scenario_y + i * 30, 200, 30)
        #     if option_rect.collidepoint(pos):
        #         config.selected_scenario = scenario
        #         return

    def _start_game(self) -> None:
        """开始游戏"""
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # 准备游戏配置
        self.game_config = {
            "mode": config.selected_mode,
            "players": config.selected_players.copy(),
            "scenario": config.selected_scenario,
        }

        # 通过引擎切换到游戏场景
        self.engine.scene_manager.switch_to("game", **self.game_config)

    def _quit_game(self) -> None:
        """退出游戏"""
        EBS.publish(QuitEvent(sender=__name__, timestamp=pygame.time.get_ticks()))

    def exit(self) -> None:
        """退出场景"""
        super().exit()
        self.cleanup()

    def cleanup(self) -> None:
        """清理场景"""
        if self.world:
            self.world.reset()
        EBS.unsubscribe(MouseMotionEvent, self._update_hover_state)
        EBS.unsubscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def get_game_config(self) -> Optional[Dict[str, Any]]:
        """获取游戏配置"""
        return self.game_config
