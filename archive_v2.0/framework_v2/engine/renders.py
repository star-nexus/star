import pygame
from typing import Dict, List, Tuple, Optional


class RenderManager:
    """渲染管理器，负责管理游戏中的渲染逻辑"""

    def __init__(self,screen:pygame.Surface):
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

    def draw(self, surface: pygame.Surface, dest: pygame.Rect) -> None:
        """添加渲染项到当前层

        Args:
            surface: 要渲染的表面
            dest: 目标位置和大小
        """
        if self.current_layer not in self._render_queue:
            self._render_queue[self.current_layer] = []
        self._render_queue[self.current_layer].append((surface, dest))

    def draw_rect(
        self, color: Tuple[int, int, int], rect: pygame.Rect, width: int = 0
    ) -> None:
        """绘制矩形

        Args:
            color: 矩形颜色 (R, G, B)
            rect: 矩形区域
            width: 线宽，0表示填充
        """
        surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(
            surface, color, pygame.Rect(0, 0, rect.width, rect.height), width
        )
        self.draw(surface, rect)

    def draw_circle(
        self,
        color: Tuple[int, int, int],
        center: Tuple[int, int],
        radius: int,
        width: int = 0,
    ) -> None:
        """绘制圆形

        Args:
            color: 圆形颜色 (R, G, B)
            center: 圆心位置 (x, y)
            radius: 半径
            width: 线宽，0表示填充
        """
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surface, color, (radius, radius), radius, width)
        rect = pygame.Rect(
            center[0] - radius, center[1] - radius, radius * 2, radius * 2
        )
        self.draw(surface, rect)

    def draw_line(
        self,
        color: Tuple[int, int, int],
        start_pos: Tuple[int, int],
        end_pos: Tuple[int, int],
        width: int = 1,
    ) -> None:
        """绘制直线

        Args:
            color: 线段颜色 (R, G, B)
            start_pos: 起点位置 (x, y)
            end_pos: 终点位置 (x, y)
            width: 线宽
        """
        # 计算线段的包围盒
        min_x = min(start_pos[0], end_pos[0])
        min_y = min(start_pos[1], end_pos[1])
        max_x = max(start_pos[0], end_pos[0])
        max_y = max(start_pos[1], end_pos[1])

        # 创建表面并绘制线段
        surface = pygame.Surface(
            (max_x - min_x + width * 2, max_y - min_y + width * 2), pygame.SRCALPHA
        )
        pygame.draw.line(
            surface,
            color,
            (start_pos[0] - min_x + width, start_pos[1] - min_y + width),
            (end_pos[0] - min_x + width, end_pos[1] - min_y + width),
            width,
        )
        rect = pygame.Rect(
            min_x - width,
            min_y - width,
            max_x - min_x + width * 2,
            max_y - min_y + width * 2,
        )
        self.draw(surface, rect)

    def draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        position: Tuple[int, int],
        align: str = "left",
    ) -> None:
        """绘制文本

        Args:
            text: 文本内容
            font: 字体对象
            color: 文本颜色 (R, G, B)
            position: 文本位置 (x, y)
            align: 对齐方式 ("left", "center", "right")
        """
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()

        if align == "left":
            text_rect.topleft = position
        elif align == "center":
            text_rect.midtop = position
        elif align == "right":
            text_rect.topright = position

        self.draw(text_surface, text_rect)

    def draw_surface(self, surface: pygame.Surface, position: Tuple[int, int]) -> None:
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
        
