import pygame
from typing import Tuple

class UIElement:
    """UI元素基类"""
    
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int]):
        """初始化UI元素
        
        Args:
            position: 元素位置 (x, y)
            size: 元素大小 (width, height)
        """
        self.position = position
        self.size = size
        self.rect = pygame.Rect(position[0], position[1], size[0], size[1])
        self.visible = True
        self.enabled = True
        self.parent = None
        self.children = []
    
    def contains_point(self, point: Tuple[int, int]) -> bool:
        """检查点是否在元素内

        Args:
            point: 点的位置 (x, y)

        Returns:
            bool: 如果点在元素内返回True，否则返回False
        """
        return self.rect.collidepoint(point)
    
    def add_child(self, child) -> None:
        """添加子元素
        
        Args:
            child: 子UI元素
        """
        child.parent = self
        self.children.append(child)
    
    def remove_child(self, child) -> None:
        """移除子元素
        
        Args:
            child: 子UI元素
        """
        if child in self.children:
            child.parent = None
            self.children.remove(child)
    
    def update(self, delta_time: float) -> None:
        """更新UI元素
        
        Args:
            delta_time: 帧间隔时间
        """
        if not self.visible:
            return
            
        # 更新子元素
        for child in self.children:
            child.update(delta_time)
    
    def render(self, render_manager) -> None:
        """渲染UI元素
        
        Args:
            render_manager: 渲染管理器
        """
        if not self.visible:
            return
            
        # 渲染子元素
        for child in self.children:
            child.render(render_manager)
    
    def process_event(self, event_type, event_data) -> bool:
        """处理事件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
            
        Returns:
            是否处理了事件
        """
        if not self.enabled:
            return False
            
        # 先让子元素处理事件
        for child in reversed(self.children):  # 从上到下处理
            if child.process_event(event_type, event_data):
                return True
                
        return False
