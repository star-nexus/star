import pygame
from typing import Dict, List, Tuple

class RenderManager:
    """渲染管理器，负责管理游戏中的渲染逻辑"""
    
    def __init__(self):
        """初始化渲染管理器"""
        self.current_layer = 0
        self._render_queue: Dict[int, List[Tuple[pygame.Surface, pygame.Rect]]] = {}
    
    def set_layer(self, layer: int) -> None:
        """设置当前渲染层
        
        Args:
            layer: 渲染层级，数字越大越靠前
        """
        self.current_layer = layer
    
    def draw(self, surface: pygame.Surface, dest: pygame.Rect) -> None:
        """添加渲染项到当前层
        
        Args:
            surface: 要渲染的表面
            dest: 目标位置和大小
        """
        if self.current_layer not in self._render_queue:
            self._render_queue[self.current_layer] = []
        self._render_queue[self.current_layer].append((surface, dest))
    
    def render(self, screen: pygame.Surface) -> None:
        """渲染所有图层到屏幕
        
        Args:
            screen: 目标屏幕表面
        """
        # 按层级顺序渲染
        for layer in sorted(self._render_queue.keys()):
            for surface, dest in self._render_queue[layer]:
                screen.blit(surface, dest)
        
        # 清空渲染队列
        self._render_queue.clear()