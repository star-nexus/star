import pygame


class UIElement:
    """
    UI元素基类：所有UI元素的基础类
    """

    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.visible = True
        self.enabled = True
        self.parent = None
        self.children = []

    def get_rect(self):
        """获取元素的矩形区域"""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def contains_point(self, point):
        """检查点是否在元素内"""
        return self.get_rect().collidepoint(point)

    def add_child(self, child):
        """添加子元素"""
        self.children.append(child)
        child.parent = self
        return child

    def remove_child(self, child):
        """移除子元素"""
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def process_event(self, event):
        """处理事件"""
        # 首先让子元素处理事件
        for child in self.children:
            if child.visible and child.enabled:
                child.process_event(event)

    def update(self, delta_time):
        """更新UI元素"""
        # 更新所有子元素
        for child in self.children:
            if child.visible:
                child.update(delta_time)

    def render(self, surface):
        """渲染UI元素"""
        # 渲染所有子元素
        for child in self.children:
            if child.visible:
                child.render(surface)
