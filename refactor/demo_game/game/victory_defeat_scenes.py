import pygame
from framework.managers.scenes import Scene


class VictoryScene(Scene):
    """胜利场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_label = None
        self.message_label = None
        self.back_button = None
        # 添加场景加载状态标志
        self.is_loaded = False

    def enter(self) -> None:
        # 防止重复初始化
        if self.is_loaded:
            return

        # 加载字体
        title_font = self.engine.resource_manager.load_font("default", None, 74)
        message_font = self.engine.resource_manager.load_font("default", None, 36)
        button_font = self.engine.resource_manager.load_font("default", None, 48)

        # 创建胜利标题
        self.title_label = self.engine.ui_manager.create_label(
            position=(200, 100),
            size=(400, 80),
            text="Victory!",
            font=title_font,
            text_color=(0, 255, 0),  # 绿色
            z_index=10,
        )

        # 创建胜利信息
        self.message_label = self.engine.ui_manager.create_label(
            position=(100, 200),
            size=(600, 100),
            text="Congratulations! You have defeated the enemy!",
            font=message_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

        # 创建返回按钮
        self.back_button = self.engine.ui_manager.create_button(
            position=(300, 350),
            size=(200, 60),
            text="Main Menu",
            font=button_font,
            on_click=self._on_back_click,
            z_index=10,
        )

        # 确保游戏管理器知道游戏已经结束
        self.engine.game_manager.is_game_over = True

        # 标记场景已加载
        self.is_loaded = True
        print("VictoryScene: Scene loaded")

    def exit(self) -> None:
        # 清理UI元素
        if self.title_label:
            self.engine.ui_manager.remove_element(self.title_label)
            self.title_label = None

        if self.message_label:
            self.engine.ui_manager.remove_element(self.message_label)
            self.message_label = None

        if self.back_button:
            self.engine.ui_manager.remove_element(self.back_button)
            self.back_button = None

        # 退出时重置游戏状态
        self.engine.game_manager.reset()

        # 标记场景已卸载
        self.is_loaded = False
        print("VictoryScene: Scene unloaded")

    def _on_back_click(self):
        """返回按钮点击回调"""
        # 立即清理UI元素以防止重叠
        self.exit()
        self.engine.switch_scene("menu")

    def update(self, delta_time: float) -> None:
        # 检查空格键或回车键（作为备用控制方式）
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_RETURN]:
            # 立即清理UI元素以防止重叠
            self.exit()
            self.engine.switch_scene("menu")


class DefeatScene(Scene):
    """失败场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_label = None
        self.message_label = None
        self.back_button = None
        # 添加场景加载状态标志
        self.is_loaded = False

    def enter(self) -> None:
        # 防止重复初始化
        if self.is_loaded:
            return

        # 加载字体
        title_font = self.engine.resource_manager.load_font("default", None, 74)
        message_font = self.engine.resource_manager.load_font("default", None, 36)
        button_font = self.engine.resource_manager.load_font("default", None, 48)

        # 创建失败标题
        self.title_label = self.engine.ui_manager.create_label(
            position=(200, 100),
            size=(400, 80),
            text="Defeat",
            font=title_font,
            text_color=(255, 0, 0),  # 红色
            z_index=10,
        )

        # 创建失败信息
        self.message_label = self.engine.ui_manager.create_label(
            position=(100, 200),
            size=(600, 100),
            text="You have been defeated! Try again?",
            font=message_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

        # 创建返回按钮
        self.back_button = self.engine.ui_manager.create_button(
            position=(300, 350),
            size=(200, 60),
            text="Try Again",
            font=button_font,
            on_click=self._on_back_click,
            z_index=10,
        )

        # 确保游戏管理器知道游戏已经结束
        self.engine.game_manager.is_game_over = True

        # 标记场景已加载
        self.is_loaded = True
        print("DefeatScene: Scene loaded")

    def exit(self) -> None:
        # 清理UI元素
        if self.title_label:
            self.engine.ui_manager.remove_element(self.title_label)
            self.title_label = None

        if self.message_label:
            self.engine.ui_manager.remove_element(self.message_label)
            self.message_label = None

        if self.back_button:
            self.engine.ui_manager.remove_element(self.back_button)
            self.back_button = None

        # 退出时重置游戏状态
        self.engine.game_manager.reset()

        # 标记场景已卸载
        self.is_loaded = False
        print("DefeatScene: Scene unloaded")

    def _on_back_click(self):
        """返回按钮点击回调"""
        # 立即清理UI元素以防止重叠
        self.exit()
        self.engine.switch_scene("menu")

    def update(self, delta_time: float) -> None:
        # 检查空格键或回车键（作为备用控制方式）
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_RETURN]:
            # 立即清理UI元素以防止重叠
            self.exit()
            self.engine.switch_scene("menu")
