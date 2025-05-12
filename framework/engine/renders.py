import pygame
from typing import Dict, List, Tuple, Optional


class RenderManager:
    """渲染管理器，负责管理游戏中的渲染逻辑"""

    def __init__(self, screen: pygame.Surface):
        """初始化渲染管理器"""
        self.current_layer = 0
        self._render_queue: Dict[int, List[Tuple[pygame.Surface, pygame.Rect]]] = {}
        self.screen = screen

    def set_layer(self, layer: int) -> None:
        """设置当前渲染层

        Args:
            layer: 渲染层级，数字越大越靠前
        """
        self.current_layer = layer

    def draw(self, surface: pygame.Surface, dest: pygame.Rect, layer: int = -1) -> None:
        """添加渲染项到当前层

        Args:
            surface: 要渲染的表面
            dest: 目标位置和大小
        """
        if layer == -1:
            layer = self.current_layer
        else:
            self.set_layer(layer)
        if self.current_layer not in self._render_queue:
            self._render_queue[self.current_layer] = []
        self._render_queue[self.current_layer].append((surface, dest))

    def draw_surface(
        self, surface: pygame.Surface, position: Tuple[int, int], layer: int = -1
    ) -> None:
        """绘制表面

        Args:
            surface: 要绘制的表面
            position: 绘制位置 (x, y)
        """
        self.draw(
            surface,
            pygame.Rect(
                position[0], position[1], surface.get_width(), surface.get_height()
            ),
            layer,
        )

    def update(self, screen: pygame.Surface) -> None:
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
