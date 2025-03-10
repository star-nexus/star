import pygame
import math
from framework.managers.scenes import Scene
from framework.managers.events import Message


class EndScene(Scene):
    """游戏结束场景，显示结束信息和按钮"""

    # 添加类变量来存储场景间传递的数据
    victory_status = False
    game_stats = None

    def __init__(self, engine):
        super().__init__(engine)
        self.title_font = None
        self.text_font = None
        self.button_font = None
        self.victory = False  # 胜利标志
        self.result_text = None
        self.stats_text = []  # 游戏统计数据
        self.menu_button = None
        self.exit_button = None
        self.background_color = (20, 20, 30)  # 深色背景
        self.stats = {}  # 统计数据

    def enter(self) -> None:
        """场景进入时调用，从类变量中获取数据"""
        # 从类变量获取数据
        self.victory = EndScene.victory_status
        self.stats = EndScene.game_stats or {}

        # 创建字体
        self.title_font = pygame.font.Font(None, 72)
        self.text_font = pygame.font.Font(None, 36)
        self.button_font = pygame.font.Font(None, 48)

        # 创建结果文本
        if self.victory:
            self.result_text = self.title_font.render(
                "胜利!", True, (255, 215, 0)
            )  # 金色
        else:
            self.result_text = self.title_font.render(
                "失败!", True, (200, 50, 50)
            )  # 红色

        # 创建统计数据文本
        self.stats_text = []
        if self.stats:
            for key, value in self.stats.items():
                text = self.text_font.render(f"{key}: {value}", True, (200, 200, 200))
                self.stats_text.append(text)
        else:
            text = self.text_font.render("游戏结束", True, (200, 200, 200))
            self.stats_text.append(text)

        # 创建按钮
        self.menu_button_text = self.button_font.render("主菜单", True, (255, 255, 255))
        self.exit_button_text = self.button_font.render(
            "退出游戏", True, (255, 255, 255)
        )

        # 按钮位置和大小
        button_width, button_height = 200, 50
        button_margin = 20
        center_x = self.engine.width // 2
        menu_y = self.engine.height * 2 // 3
        exit_y = menu_y + button_height + button_margin

        # 创建按钮矩形
        self.menu_button = pygame.Rect(
            center_x - button_width // 2, menu_y, button_width, button_height
        )
        self.exit_button = pygame.Rect(
            center_x - button_width // 2, exit_y, button_width, button_height
        )

        # 订阅鼠标点击事件
        self.engine.event_manager.subscribe("MOUSEBUTTONDOWN", self._handle_mouse_click)
        self.engine.event_manager.subscribe("KEYDOWN", self._handle_key_press)

        # 播放结束音乐
        # if pygame.mixer.music.get_busy():
        #     pygame.mixer.music.stop()
        # if self.victory:
        #     pygame.mixer.music.load("assets/music/victory_theme.mp3")
        # else:
        #     pygame.mixer.music.load("assets/music/defeat_theme.mp3")
        # pygame.mixer.music.play(-1)  # 循环播放

    def exit(self) -> None:
        """场景退出时调用"""
        # 取消订阅事件
        self.engine.event_manager.unsubscribe(
            "MOUSEBUTTONDOWN", self._handle_mouse_click
        )
        self.engine.event_manager.unsubscribe("KEYDOWN", self._handle_key_press)

    def update(self, delta_time: float) -> None:
        """更新场景逻辑"""
        # 可以添加一些动画或粒子效果
        pass

    def render(self, render_manager) -> None:
        """渲染场景"""
        # 清屏
        render_manager.set_layer(0)
        bg_rect = pygame.Rect(0, 0, self.engine.width, self.engine.height)
        render_manager.draw_rect(self.background_color, bg_rect)

        # 绘制结果文本
        result_rect = self.result_text.get_rect()
        result_rect.centerx = self.engine.width // 2
        result_rect.top = self.engine.height // 6
        render_manager.draw(self.result_text, result_rect)

        # 绘制统计数据
        start_y = self.engine.height // 3
        line_height = 40
        for i, text in enumerate(self.stats_text):
            text_rect = text.get_rect()
            text_rect.centerx = self.engine.width // 2
            text_rect.top = start_y + i * line_height
            render_manager.draw(text, text_rect)

        # 绘制主菜单按钮
        button_color = (50, 70, 120)
        render_manager.draw_rect(button_color, self.menu_button)
        menu_text_rect = self.menu_button_text.get_rect()
        menu_text_rect.center = self.menu_button.center
        render_manager.draw(self.menu_button_text, menu_text_rect)

        # 绘制退出按钮
        render_manager.draw_rect(button_color, self.exit_button)
        exit_text_rect = self.exit_button_text.get_rect()
        exit_text_rect.center = self.exit_button.center
        render_manager.draw(self.exit_button_text, exit_text_rect)

    def _handle_mouse_click(self, message):
        """处理鼠标点击事件"""
        if message.data.get("button") == 1:  # 左键点击
            mouse_pos = message.data.get("pos", (0, 0))

            # 检查是否点击主菜单按钮
            if self.menu_button.collidepoint(mouse_pos):
                print("返回主菜单")
                self.engine.switch_scene("start")

            # 检查是否点击退出按钮
            elif self.exit_button.collidepoint(mouse_pos):
                print("退出游戏")
                self.engine.quit()

    def _handle_key_press(self, message):
        """处理键盘按键事件"""
        key = message.data
        if key == pygame.K_RETURN or key == pygame.K_SPACE:
            print("返回主菜单 (键盘触发)")
            self.engine.switch_scene("start")
        elif key == pygame.K_ESCAPE:
            print("退出游戏 (键盘触发)")
            self.engine.quit()
