import pygame
from typing import Dict, List, Tuple, Optional, Callable
from .ui_element import UIElement


class Panel(UIElement):
    """面板UI元素"""
    
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int], 
                 color: Tuple[int, int, int] = (80, 80, 80),
                 border_color: Optional[Tuple[int, int, int]] = None,
                 border_width: int = 0):
        """初始化面板
        
        Args:
            position: 面板位置 (x, y)
            size: 面板大小 (width, height)
            color: 面板颜色
            border_color: 边框颜色，None表示无边框
            border_width: 边框宽度
        """
        super().__init__(position, size)
        self.color = color
        self.border_color = border_color
        self.border_width = border_width
    
    def render(self, render_manager) -> None:
        """渲染面板
        
        Args:
            render_manager: 渲染管理器
        """
        if not self.visible:
            return
            
        # 绘制面板背景
        render_manager.draw_rect(self.color, self.rect)
        
        # 绘制边框
        if self.border_color and self.border_width > 0:
            render_manager.draw_rect(self.border_color, self.rect, self.border_width)
        
        # 渲染子元素
        super().render(render_manager)
