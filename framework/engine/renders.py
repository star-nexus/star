import pygame
from typing import Dict, List, Tuple, Optional, Union, Callable
from collections import defaultdict
from contextlib import contextmanager
from abc import ABC, abstractmethod
from ..ecs import profiling

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

    __slots__ = ("draw_func", "args", "kwargs")

    def __init__(self, draw_func: Callable, *args, **kwargs):
        self.draw_func = draw_func
        self.args = args
        self.kwargs = kwargs

    def execute(self, screen: pygame.Surface) -> None:
        self.draw_func(screen, *self.args, **self.kwargs)


class BlitCommand(RenderCommand):
    """Surface blit command with a batchable fast path.

    Most terrain/unit rendering is a plain ``screen.blit(surface, dest)``. Keeping
    that operation typed lets ``RenderEngine.update`` submit long consecutive runs
    through ``Surface.blits`` instead of crossing Python once per tile/unit.
    Commands with an ``area`` or special flags retain the exact single-blit path.
    """

    __slots__ = ("surface", "dest", "area", "special_flags")

    def __init__(
        self,
        surface: pygame.Surface,
        dest: PositionType,
        area: Optional[pygame.Rect] = None,
        special_flags: int = 0,
    ):
        self.surface = surface
        self.dest = dest
        self.area = area
        self.special_flags = special_flags

    @property
    def batchable(self) -> bool:
        return self.area is None and self.special_flags == 0

    def execute(self, screen: pygame.Surface) -> None:
        screen.blit(self.surface, self.dest, self.area, self.special_flags)


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
        return self._add_command(
            BlitCommand(surface, dest, area=area, special_flags=special_flags), layer
        )

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
        """Render all queued layers while exposing coarse queue-drain attribution.

        This instrumentation deliberately leaves the submission algorithm unchanged.
        ``render_engine`` remains the parent timer owned by ``GameEngine``; the
        sections below only split its existing queue-drain work into prepare,
        submit, and clear phases.
        """
        if not self.screen:
            raise RuntimeError("屏幕表面未设置，请先调用 set_screen()")

        profiler = profiling.profiler
        with profiler.time_system("render_queue_prepare", category="render"):
            layer_keys = sorted(self._render_queue.keys())
            command_count = sum(len(commands) for commands in self._render_queue.values())
            layer_count = len(layer_keys)

        profiler.set_frame_metric("render_commands", command_count)
        profiler.set_frame_metric("render_layers", layer_count)

        simple_blits = 0
        blit_batches = 0
        batch_runs = 0
        single_plain_blits = 0
        nonbatch_blits = 0
        draw_commands = 0
        other_commands = 0
        max_batch_size = 0

        # Preserve layer and command order exactly. Only consecutive plain blits
        # are collapsed; any geometry/custom command is an ordering barrier.
        with profiler.time_system("render_queue_submit", category="render"):
            for layer in layer_keys:
                commands = self._render_queue[layer]
                index = 0
                while index < len(commands):
                    command = commands[index]
                    if isinstance(command, BlitCommand) and command.batchable:
                        batch_runs += 1
                        batch = []
                        while index < len(commands):
                            candidate = commands[index]
                            if (
                                not isinstance(candidate, BlitCommand)
                                or not candidate.batchable
                            ):
                                break
                            batch.append((candidate.surface, candidate.dest))
                            index += 1

                        batch_size = len(batch)
                        simple_blits += batch_size
                        max_batch_size = max(max_batch_size, batch_size)
                        if batch_size >= 2:
                            self.screen.blits(batch, False)
                            blit_batches += 1
                        else:
                            single_plain_blits += 1
                            command.execute(self.screen)
                        continue

                    if isinstance(command, BlitCommand):
                        nonbatch_blits += 1
                    elif isinstance(command, DrawCommand):
                        draw_commands += 1
                    else:
                        other_commands += 1
                    command.execute(self.screen)
                    index += 1

        scalar_commands = nonbatch_blits + draw_commands + other_commands
        profiler.set_frame_metric("render_simple_blits", simple_blits)
        profiler.set_frame_metric("render_blit_batches", blit_batches)
        profiler.set_frame_metric("render_batch_runs", batch_runs)
        profiler.set_frame_metric("render_single_plain_blits", single_plain_blits)
        profiler.set_frame_metric("render_nonbatch_blits", nonbatch_blits)
        profiler.set_frame_metric("render_draw_commands", draw_commands)
        profiler.set_frame_metric("render_other_commands", other_commands)
        profiler.set_frame_metric("render_scalar_commands", scalar_commands)
        profiler.set_frame_metric("render_max_batch_size", max_batch_size)

        # The scale snapshot already exports ``scale_*`` metadata. These values
        # intentionally describe the latest completed frame, not a rolling mean;
        # rolling timing attribution remains owned by the hierarchical profiler.
        profiler.set_metadata(
            scale_render_queue_last_commands=command_count,
            scale_render_queue_last_layers=layer_count,
            scale_render_queue_last_batch_runs=batch_runs,
            scale_render_queue_last_simple_blits=simple_blits,
            scale_render_queue_last_blit_batches=blit_batches,
            scale_render_queue_last_scalar_commands=scalar_commands,
            scale_render_queue_last_max_batch_size=max_batch_size,
        )

        with profiler.time_system("render_queue_clear", category="render"):
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
