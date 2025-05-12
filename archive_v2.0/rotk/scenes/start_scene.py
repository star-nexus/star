import pygame
import math
from framework.managers.scenes import Scene
from framework.managers.events import Message


class StartScene(Scene):
    """游戏开始场景，显示标题和开始按钮"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_font = None
        self.button_font = None
        self.title_text = None
        self.start_button = None
        self.exit_button = None
        self.background_color = (10, 30, 50)  # 深蓝色背景

        # 标题动画参数
        self.title_scale = 1.0
        self.scale_direction = 0.0005
        self.title_y_offset = 0
        self.title_move_speed = 0.2

    def enter(self) -> None:
        """场景进入时调用"""
        # 创建字体
        self.title_font = pygame.font.Font(None, 72)
        self.button_font = pygame.font.Font(None, 48)

        # 创建标题文本
        self.title_text = self.title_font.render(
            "RoTK", True, (255, 215, 0)
        )  # 金色标题
        self.subtitle_text = self.button_font.render("RTS", True, (220, 220, 220))

        # 创建按钮
        self.start_button_text = self.button_font.render("Start", True, (255, 255, 255))
        self.exit_button_text = self.button_font.render("Exit", True, (255, 255, 255))

        # 按钮位置和大小
        button_width, button_height = 200, 50
        button_margin = 20
        center_x = self.engine.width // 2
        start_y = self.engine.height // 2 + 50
        exit_y = start_y + button_height + button_margin

        # 创建按钮矩形
        self.start_button = pygame.Rect(
            center_x - button_width // 2, start_y, button_width, button_height
        )
        self.exit_button = pygame.Rect(
            center_x - button_width // 2, exit_y, button_width, button_height
        )

        # 订阅鼠标点击事件
        self.engine.event_manager.subscribe("MOUSEBUTTONDOWN", self._handle_mouse_click)
        self.engine.event_manager.subscribe("KEYDOWN", self._handle_key_press)

        # 播放背景音乐
        # if pygame.mixer.music.get_busy():
        #     pygame.mixer.music.stop()
        # pygame.mixer.music.load("assets/music/title_theme.mp3")
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
        # 更新标题动画
        self.title_scale += self.scale_direction
        if self.title_scale > 1.05 or self.title_scale < 0.95:
            self.scale_direction *= -1

        # 轻微上下移动标题
        self.title_y_offset = 5 * math.sin(pygame.time.get_ticks() / 1000)

    def render(self, render_manager) -> None:
        """渲染场景"""
        # 清屏
        render_manager.set_layer(0)
        bg_rect = pygame.Rect(0, 0, self.engine.width, self.engine.height)
        render_manager.draw_rect(self.background_color, bg_rect)

        # 绘制标题
        title_rect = self.title_text.get_rect()
        title_rect.centerx = self.engine.width // 2
        title_rect.centery = self.engine.height // 3 + int(self.title_y_offset)

        # 缩放标题
        scaled_title = pygame.transform.scale(
            self.title_text,
            (
                int(title_rect.width * self.title_scale),
                int(title_rect.height * self.title_scale),
            ),
        )
        scaled_rect = scaled_title.get_rect()
        scaled_rect.center = title_rect.center
        render_manager.draw(scaled_title, scaled_rect)

        # 绘制副标题
        subtitle_rect = self.subtitle_text.get_rect()
        subtitle_rect.centerx = self.engine.width // 2
        subtitle_rect.top = title_rect.bottom + 10
        render_manager.draw(self.subtitle_text, subtitle_rect)

        # 绘制开始按钮
        button_color = (50, 100, 150)  # 蓝色按钮
        render_manager.draw_rect(button_color, self.start_button)
        start_text_rect = self.start_button_text.get_rect()
        start_text_rect.center = self.start_button.center
        render_manager.draw(self.start_button_text, start_text_rect)

        # 绘制退出按钮
        render_manager.draw_rect(button_color, self.exit_button)
        exit_text_rect = self.exit_button_text.get_rect()
        exit_text_rect.center = self.exit_button.center
        render_manager.draw(self.exit_button_text, exit_text_rect)

        # 绘制版权信息
        copyright_font = pygame.font.Font(None, 24)
        copyright_text = copyright_font.render(
            "© 2025 RoTK Demo", True, (150, 150, 150)
        )
        copyright_rect = copyright_text.get_rect()
        copyright_rect.centerx = self.engine.width // 2
        copyright_rect.bottom = self.engine.height - 20
        render_manager.draw(copyright_text, copyright_rect)

    def _handle_mouse_click(self, message):
        """处理鼠标点击事件"""
        if message.data.get("button") == 1:  # 左键点击
            mouse_pos = message.data.get("pos", (0, 0))

            # 检查是否点击开始按钮
            if self.start_button.collidepoint(mouse_pos):
                print("开始游戏")
                self.engine.switch_scene("game")

            # 检查是否点击退出按钮
            elif self.exit_button.collidepoint(mouse_pos):
                print("退出游戏")
                self.engine.quit()

    def _handle_key_press(self, message):
        """处理键盘按键事件"""
        key = message.data
        if key == pygame.K_RETURN or key == pygame.K_SPACE:
            print("开始游戏 (键盘触发)")
            self.engine.switch_scene("game")
        elif key == pygame.K_ESCAPE:
            print("退出游戏 (键盘触发)")
            self.engine.quit()
