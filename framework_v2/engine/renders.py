import pygame
from typing import Dict, List, Tuple, Optional, Union, Callable
from collections import defaultdict
from contextlib import contextmanager
from abc import ABC, abstractmethod

# 类型别名
ColorType = Union[pygame.Color, Tuple[int, int, int], Tuple[int, int, int, int]]
PositionType = Union[pygame.Rect, Tuple[int, int]]
PointType = Tuple[int, int]


class RenderCommand(ABC):
    """渲染命令基类"""

    @abstractmethod
    def execute(self, screen: pygame.Surface) -> None:
        """执行渲染命令"""
        pass


class DrawCommand(RenderCommand):
    """通用绘制命令"""

    def __init__(self, draw_func: Callable, *args, **kwargs):
        self.draw_func = draw_func
        self.args = args
        self.kwargs = kwargs

    def execute(self, screen: pygame.Surface) -> None:
        self.draw_func(screen, *self.args, **self.kwargs)


class RenderEngine:
    """渲染引擎 - 单例模式，负责管理游戏渲染逻辑"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, screen: Optional[pygame.Surface] = None):
        """初始化渲染引擎"""
        if hasattr(self, "_initialized"):
            return
        self._screen = None
        self.current_layer = 0
        self._render_queue: Dict[int, List[RenderCommand]] = defaultdict(list)
        self._initialized = True

    @property
    def screen(self) -> pygame.Surface:
        """获取屏幕表面"""
        if not self._screen:
            raise RuntimeError("屏幕表面未设置，请先调用 set_screen()")
        return self._screen

    @screen.setter
    def screen(self, value: pygame.Surface) -> None:
        """设置屏幕表面"""
        if not isinstance(value, pygame.Surface):
            raise TypeError("屏幕必须是 pygame.Surface 类型")
        self._screen = value

    def set_layer(self, layer: int) -> "RenderEngine":
        """设置当前渲染层，支持链式调用"""
        self.current_layer = layer
        return self

    @contextmanager
    def layer(self, layer: int):
        """临时切换渲染层的上下文管理器"""
        old_layer = self.current_layer
        self.current_layer = layer
        try:
            yield self
        finally:
            self.current_layer = old_layer

    def _add_command(
        self, command: RenderCommand, layer: Optional[int] = None
    ) -> "RenderEngine":
        """添加渲染命令"""
        target_layer = layer if layer is not None else self.current_layer
        self._render_queue[target_layer].append(command)
        return self

    # 基础绘制方法
    def draw(
        self,
        surface: pygame.Surface,
        dest: PositionType,
        area: Optional[pygame.Rect] = None,
        special_flags: int = 0,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制表面到指定位置"""
        command = DrawCommand(
            lambda screen, surface, dest, area, special: screen.blit(
                surface, dest, area, special
            ),
            surface,
            dest,
            area,
            special_flags,
        )
        # command = BlitCommand(surface, dest, area, special_flags)
        return self._add_command(command, layer)

    # 几何图形绘制方法
    def rect(
        self,
        color: ColorType,
        rect: pygame.Rect,
        width: int = 0,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制矩形"""
        command = DrawCommand(pygame.draw.rect, color, rect, width)
        return self._add_command(command, layer)

    def circle(
        self,
        color: ColorType,
        center: PointType,
        radius: int,
        width: int = 0,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制圆形"""
        command = DrawCommand(pygame.draw.circle, color, center, radius, width)
        return self._add_command(command, layer)

    def line(
        self,
        color: ColorType,
        start_pos: PointType,
        end_pos: PointType,
        width: int = 1,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制直线"""
        command = DrawCommand(pygame.draw.line, color, start_pos, end_pos, width)
        return self._add_command(command, layer)

    def lines(
        self,
        color: ColorType,
        closed: bool,
        points: List[PointType],
        width: int = 1,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制连线"""
        command = DrawCommand(pygame.draw.lines, color, closed, points, width)
        return self._add_command(command, layer)

    def polygon(
        self,
        color: ColorType,
        points: List[PointType],
        width: int = 0,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制多边形"""
        command = DrawCommand(pygame.draw.polygon, color, points, width)
        return self._add_command(command, layer)

    def ellipse(
        self,
        color: ColorType,
        rect: pygame.Rect,
        width: int = 0,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制椭圆"""
        command = DrawCommand(pygame.draw.ellipse, color, rect, width)
        return self._add_command(command, layer)

    def arc(
        self,
        color: ColorType,
        rect: pygame.Rect,
        start_angle: float,
        stop_angle: float,
        width: int = 1,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """绘制弧形"""
        command = DrawCommand(
            pygame.draw.arc, color, rect, start_angle, stop_angle, width
        )
        return self._add_command(command, layer)

    # 高级绘制方法
    def custom(
        self, draw_func: Callable, *args, layer: Optional[int] = None, **kwargs
    ) -> "RenderEngine":
        """执行自定义绘制函数"""
        command = DrawCommand(draw_func, *args, **kwargs)
        return self._add_command(command, layer)

    def fill(
        self,
        color: ColorType,
        rect: Optional[pygame.Rect] = None,
        layer: Optional[int] = None,
    ) -> "RenderEngine":
        """填充屏幕或指定区域"""
        if rect:
            command = DrawCommand(lambda screen, c, r: screen.fill(c, r), color, rect)
        else:
            command = DrawCommand(lambda screen, c: screen.fill(c), color)
        return self._add_command(command, layer)

    def update(self) -> None:
        """渲染所有图层到屏幕"""
        if not self.screen:
            raise RuntimeError("屏幕表面未设置，请先调用 set_screen()")

        # 按层级顺序渲染
        for layer in sorted(self._render_queue.keys()):
            for command in self._render_queue[layer]:
                command.execute(self.screen)

        self.clear()

    def clear(self) -> None:
        """清空渲染队列"""
        self._render_queue.clear()

    def clear_layer(self, layer: int) -> None:
        """清空指定层级"""
        if layer in self._render_queue:
            del self._render_queue[layer]


RMS = RenderEngine()  # 全局渲染引擎实例
# Render Manager System
