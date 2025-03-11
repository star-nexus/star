import pygame
from framework.ui.ui_element import UIElement


class UIButton(UIElement):
    """
    按钮UI元素
    """

    def __init__(self, x, y, width, height, text="", callback=None):
        super().__init__(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = None
        self.font_color = (255, 255, 255)
        self.normal_color = (100, 100, 100)
        self.hover_color = (150, 150, 150)
        self.pressed_color = (50, 50, 50)
        self.disabled_color = (80, 80, 80)
        self.current_color = self.normal_color
        self.is_hovered = False
        self.is_pressed = False
        self.padding = 5

    def set_font(self, font, color=(255, 255, 255)):
        """设置按钮字体和颜色"""
        self.font = font
        self.font_color = color

    def process_event(self, event):
        """处理按钮事件"""
        if not self.enabled:
            self.current_color = self.disabled_color
            return

        mouse_pos = pygame.mouse.get_pos()
        self.is_hovered = self.contains_point(mouse_pos)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                self.is_pressed = True
                self.current_color = self.pressed_color

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.is_pressed
            self.is_pressed = False

            if was_pressed and self.is_hovered and self.callback:
                self.callback()

        super().process_event(event)

    def update(self, delta_time):
        """更新按钮状态"""
        if not self.enabled:
            self.current_color = self.disabled_color
        elif self.is_pressed:
            self.current_color = self.pressed_color
        elif self.is_hovered:
            self.current_color = self.hover_color
        else:
            self.current_color = self.normal_color

        super().update(delta_time)

    def render(self, surface):
        """渲染按钮"""
        # 绘制按钮背景
        pygame.draw.rect(surface, self.current_color, self.get_rect(), border_radius=5)
        pygame.draw.rect(surface, (0, 0, 0), self.get_rect(), 2, border_radius=5)

        # 如果有文本，则渲染文本
        if self.text and self.font:
            text_surf = self.font.render(self.text, True, self.font_color)
            text_rect = text_surf.get_rect(center=self.get_rect().center)
            surface.blit(text_surf, text_rect)

        super().render(surface)
