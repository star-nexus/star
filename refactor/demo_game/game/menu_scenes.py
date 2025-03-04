import pygame
from framework.managers.scenes import Scene
from framework.managers.renders import RenderManager


class MenuScene(Scene):
    """游戏菜单场景，显示开始游戏选项"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_label = None
        self.start_button = None
        # 添加场景加载状态标志
        self.is_loaded = False

    def enter(self) -> None:
        # 防止重复初始化
        if self.is_loaded:
            return

        # 加载字体
        title_font = self.engine.resource_manager.load_font("default", None, 74)
        button_font = self.engine.resource_manager.load_font("default", None, 48)

        # 创建标题标签
        self.title_label = self.engine.ui_manager.create_label(
            position=(200, 150),
            size=(400, 80),
            text="Simple Demo Game",
            font=title_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

        # 创建开始游戏按钮
        self.start_button = self.engine.ui_manager.create_button(
            position=(300, 350),
            size=(200, 60),
            text="Start Game",
            font=button_font,
            on_click=self._on_start_click,
            z_index=10,
        )

        # 标记场景已加载
        self.is_loaded = True
        print("MenuScene: Scene loaded")

    def exit(self) -> None:
        # 清理UI元素
        if self.title_label:
            self.engine.ui_manager.remove_element(self.title_label)
            self.title_label = None

        if self.start_button:
            self.engine.ui_manager.remove_element(self.start_button)
            self.start_button = None

        # 标记场景已卸载
        self.is_loaded = False
        print("MenuScene: Scene unloaded")

    def _on_start_click(self):
        """开始游戏按钮点击回调"""
        # 立即清理UI元素以防止重叠
        self.exit()
        self.engine.switch_scene("game")

    def update(self, delta_time: float) -> None:
        # 检查空格键是否被按下（作为备用控制方式）
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            # 立即清理UI元素以防止重叠
            self.exit()
            self.engine.switch_scene("game")

    def render(self, render_manager: RenderManager) -> None:
        # UI元素由UI系统自动渲染，这里不需要额外操作
        pass


class GameOverScene(Scene):
    """游戏结束场景，显示游戏结果"""

    def __init__(self, engine, is_victory: bool = False):
        super().__init__(engine)
        self.is_victory = is_victory
        self.result_label = None
        self.restart_button = None

    def enter(self) -> None:
        # 加载字体
        title_font = self.engine.resource_manager.load_font("default", None, 74)
        button_font = self.engine.resource_manager.load_font("default", None, 48)

        # 创建结果标签
        result_text = "Victory!" if self.is_victory else "Defeat!"
        result_color = (
            (0, 255, 0) if self.is_victory else (255, 0, 0)
        )  # 胜利为绿色，失败为红色

        self.result_label = self.engine.ui_manager.create_label(
            position=(300, 150),
            size=(200, 80),
            text=result_text,
            font=title_font,
            text_color=result_color,
            z_index=10,
        )

        # 创建重新开始按钮
        self.restart_button = self.engine.ui_manager.create_button(
            position=(300, 350),
            size=(200, 60),
            text="Restart",
            font=button_font,
            on_click=self._on_restart_click,
            z_index=10,
        )

    def exit(self) -> None:
        # 清理UI元素
        if self.result_label:
            self.engine.ui_manager.remove_element(self.result_label)
            self.result_label = None

        if self.restart_button:
            self.engine.ui_manager.remove_element(self.restart_button)
            self.restart_button = None

    def _on_restart_click(self):
        """重新开始按钮点击回调"""
        self.engine.switch_scene("menu")

    def update(self, delta_time: float) -> None:
        # 检查R键是否被按下（作为备用控制方式）
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            self.engine.switch_scene("menu")

    def render(self, render_manager: RenderManager) -> None:
        # UI元素由UI系统自动渲染，这里不需要额外操作
        pass
