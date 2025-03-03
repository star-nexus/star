import pygame
from framework.ui.ui_element import UIElement


class UIManager:
    """
    UI管理器：管理游戏中的所有UI元素
    """

    def __init__(self, screen):
        self.screen = screen
        self.root = UIElement(0, 0, screen.get_width(), screen.get_height())

    def add_element(self, element):
        """添加UI元素"""
        return self.root.add_child(element)

    def remove_element(self, element):
        """移除UI元素"""
        self.root.remove_child(element)

    def process_event(self, event):
        """处理UI事件"""
        self.root.process_event(event)

    def update(self, delta_time):
        """更新UI元素"""
        self.root.update(delta_time)

    def render(self):
        """渲染UI元素"""
        self.root.render(self.screen)
