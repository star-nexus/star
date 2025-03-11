import pygame
from framework.ui.ui_element import UIElement


class UIText(UIElement):
    """
    文本UI元素
    """

    def __init__(self, x, y, text="", font=None, color=(255, 255, 255), centered=True):
        # 初始时宽高为0，会在计算文本尺寸后更新
        super().__init__(x, y, 0, 0)
        self.text = text
        self.font = font
        self.color = color
        self.centered = centered  # 是否居中显示
        self._update_size()

    def _update_size(self):
        """根据文本内容更新元素尺寸"""
        if self.font and self.text:
            text_surf = self.font.render(self.text, True, self.color)
            self.width, self.height = text_surf.get_size()

    def set_text(self, text):
        """设置文本内容"""
        self.text = text
        self._update_size()

    def set_font(self, font):
        """设置字体"""
        self.font = font
        self._update_size()

    def set_color(self, color):
        """设置颜色"""
        self.color = color

    def render(self, surface):
        """渲染文本"""
        if self.font and self.text:
            text_surf = self.font.render(self.text, True, self.color)

            if self.centered:
                # 创建居中显示的文本矩形
                text_rect = text_surf.get_rect(
                    center=(self.x + self.width // 2, self.y + self.height // 2)
                )
                surface.blit(text_surf, text_rect)
            else:
                # 原始显示方式
                surface.blit(text_surf, (self.x, self.y))

        super().render(surface)
