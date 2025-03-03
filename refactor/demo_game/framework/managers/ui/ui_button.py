import pygame
from typing import Tuple, Callable
from .ui_element import UIElement
class Button(UIElement):
    """按钮UI元素"""
    
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int], 
                 text: str, font: pygame.font.Font, 
                 normal_color: Tuple[int, int, int] = (100, 100, 100),
                 hover_color: Tuple[int, int, int] = (150, 150, 150),
                 pressed_color: Tuple[int, int, int] = (50, 50, 50),
                 text_color: Tuple[int, int, int] = (255, 255, 255)):
        """初始化按钮
        
        Args:
            position: 按钮位置 (x, y)
            size: 按钮大小 (width, height)
            text: 按钮文本
            font: 字体对象
            normal_color: 正常状态颜色
            hover_color: 悬停状态颜色
            pressed_color: 按下状态颜色
            text_color: 文本颜色
        """
        super().__init__(position, size)
        self.text = text
        self.font = font
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.text_color = text_color
        self.current_color = normal_color
        self.is_hovered = False
        self.is_pressed = False
        self.on_click = None
    
    def set_on_click(self, callback: Callable) -> None:
        """设置点击回调函数
        
        Args:
            callback: 回调函数
        """
        self.on_click = callback
    
    def update(self, delta_time: float) -> None:
        """更新按钮状态
        
        Args:
            delta_time: 帧间隔时间
        """
        super().update(delta_time)
        
        if not self.enabled:
            self.current_color = self.normal_color
            return
            
        # 更新按钮颜色
        if self.is_pressed:
            self.current_color = self.pressed_color
        elif self.is_hovered:
            self.current_color = self.hover_color
        else:
            self.current_color = self.normal_color
    
    def render(self, render_manager) -> None:
        """渲染按钮
        
        Args:
            render_manager: 渲染管理器
        """
        if not self.visible:
            return
            
        # 绘制按钮背景
        render_manager.draw_rect(self.current_color, self.rect)
        
        # 绘制按钮文本
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        render_manager.draw_surface(text_surface, text_rect.topleft)
        
        # 渲染子元素
        super().render(render_manager)
    
    def handle_event(self, event_type: str, event_data) -> bool:
        """处理按钮事件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
            
        Returns:
            是否处理了事件
        """
        if not self.enabled:
            return False
            
        # 先让子元素处理事件
        if super().handle_event(event_type, event_data):
            return True
            
        # 处理鼠标事件
        if event_type == "MOUSEMOTION":
            mouse_pos = event_data.get("pos")
            if mouse_pos:
                self.is_hovered = self.rect.collidepoint(mouse_pos)
            return self.is_hovered
            
        elif event_type == "MOUSEBUTTONDOWN" and event_data.get("button") == 1:  # 左键
            mouse_pos = event_data.get("pos")
            if mouse_pos and self.rect.collidepoint(mouse_pos):
                self.is_pressed = True
                return True
                
        elif event_type == "MOUSEBUTTONUP" and event_data.get("button") == 1:  # 左键
            was_pressed = self.is_pressed
            self.is_pressed = False
            
            mouse_pos = event_data.get("pos")
            if was_pressed and mouse_pos and self.rect.collidepoint(mouse_pos):
                if self.on_click:
                    self.on_click()
                return True
                
        return False
