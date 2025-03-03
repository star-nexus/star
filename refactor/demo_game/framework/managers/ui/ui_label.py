import pygame
from typing import Tuple, Optional
from .ui_element import UIElement



class Label(UIElement):
    """标签UI元素"""
    
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int], 
                 text: str, font: pygame.font.Font,
                 text_color: Tuple[int, int, int] = (255, 255, 255),
                 background_color: Optional[Tuple[int, int, int]] = None):
        """初始化标签
        
        Args:
            position: 标签位置 (x, y)
            size: 标签大小 (width, height)
            text: 标签文本
            font: 字体对象
            text_color: 文本颜色
            background_color: 背景颜色，None表示透明
        """
        super().__init__(position, size)
        self.text = text
        self.font = font
        self.text_color = text_color
        self.background_color = background_color
    
    def render(self, render_manager) -> None:
        """渲染标签
        
        Args:
            render_manager: 渲染管理器
        """
        if not self.visible:
            return
            
        # 绘制背景
        if self.background_color:
            render_manager.draw_rect(self.background_color, self.rect)
        
        # 绘制文本
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        render_manager.draw_surface(text_surface, text_rect.topleft)
        
        # 渲染子元素
        super().render(render_manager)
