import pygame
import logging
from .events import EventBus, Event
from .engine_event import (
    QuitEvent,
    KeyDownEvent,
    KeyUpEvent,
    MouseButtonDownEvent,
    MouseButtonUpEvent,
    MouseMotionEvent,
    MouseWheelEvent,
    WindowResizeEvent,
)
from ..ecs import profiling


class InputSystem:
    """输入管理器，负责管理游戏中的输入逻辑"""

    _instance = None

    def __new__(cls):
        """单例模式，确保只有一个输入管理器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化输入管理器"""
        if hasattr(self, "_initialized"):
            return

        self.event_manager = EventBus()
        self.logger = logging.getLogger(__name__)
        self._last_window_size: tuple[int, int] | None = None
        self._initialized = True

    def update(self):
        profiler = profiling.profiler

        # A rare long frame was traced to the engine-level input_system timer.
        # Split SDL queue retrieval from synchronous EventBus dispatch so the
        # next spike tells us whether we are draining a large OS/SDL backlog or
        # spending the time in one of the input callbacks.
        with profiler.time_system("input_event_get", category="input"):
            events = pygame.event.get()

        collect_metrics = bool(getattr(profiler, "enabled", False))
        counts = None
        if collect_metrics:
            counts = {
                "quit": 0,
                "key_down": 0,
                "key_up": 0,
                "mouse_button": 0,
                "mouse_motion": 0,
                "mouse_wheel": 0,
                "window": 0,
                "other": 0,
            }
            profiler.set_frame_metric("input_events", len(events))

        with profiler.time_system("input_dispatch", category="input"):
            for event in events:
                if counts is not None:
                    if event.type == pygame.QUIT:
                        counts["quit"] += 1
                    elif event.type == pygame.KEYDOWN:
                        counts["key_down"] += 1
                    elif event.type == pygame.KEYUP:
                        counts["key_up"] += 1
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        counts["mouse_button"] += 1
                    elif event.type == pygame.MOUSEMOTION:
                        counts["mouse_motion"] += 1
                    elif event.type == pygame.MOUSEWHEEL:
                        counts["mouse_wheel"] += 1
                    elif event.type == pygame.VIDEORESIZE or event.type in (
                        getattr(pygame, "WINDOWRESIZED", None),
                        getattr(pygame, "WINDOWSIZECHANGED", None),
                    ):
                        counts["window"] += 1
                    else:
                        counts["other"] += 1

                if event.type == pygame.QUIT:
                    self.logger.debug("收到退出事件")
                    self.event_manager.publish(
                        QuitEvent(
                            sender=type(self).__name__,
                            timestamp=pygame.time.get_ticks(),
                        )
                    )

                # 鼠标/键盘
                match event.type:
                    case pygame.KEYDOWN:
                        self._publisher(
                            KeyDownEvent(
                                key=event.key,
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(f"键盘按下: {event.key}")
                    case pygame.KEYUP:
                        self._publisher(
                            KeyUpEvent(
                                key=event.key,
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(f"键盘抬起: {event.key}")
                    case pygame.MOUSEBUTTONDOWN:
                        self._publisher(
                            MouseButtonDownEvent(
                                button=event.button,
                                pos=event.pos,
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(f"鼠标按下: {event.button} at {event.pos}")
                    case pygame.MOUSEBUTTONUP:
                        self._publisher(
                            MouseButtonUpEvent(
                                button=event.button,
                                pos=event.pos,
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(f"鼠标抬起: {event.button} at {event.pos}")
                    case pygame.MOUSEMOTION:
                        self._publisher(
                            MouseMotionEvent(
                                pos=event.pos,
                                rel=event.rel,
                                buttons=event.buttons,
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(
                            f"鼠标移动: pos {event.pos} rel {event.rel} buttons {event.buttons}"
                        )
                    case pygame.VIDEORESIZE:
                        self._publish_window_resize(event.w, event.h)
                    case t if t is not None and t in (
                        getattr(pygame, "WINDOWRESIZED", None),
                        getattr(pygame, "WINDOWSIZECHANGED", None),
                    ):
                        self._publish_window_resize(event.x, event.y)
                    case pygame.MOUSEWHEEL:
                        self._publisher(
                            MouseWheelEvent(
                                x=event.x,
                                y=event.y,
                                pos=pygame.mouse.get_pos(),
                                sender=type(self).__name__,
                                timestamp=pygame.time.get_ticks(),
                            )
                        )
                        self.logger.debug(
                            f"鼠标滚轮: x {event.x} y {event.y} pos {pygame.mouse.get_pos()}"
                        )
                    case _:
                        self.logger.debug(f"其他事件: {event}")

        if counts is not None:
            for name, value in counts.items():
                profiler.set_frame_metric(f"input_{name}", value)

    def _publish_window_resize(self, width: int, height: int) -> None:
        size = (int(width), int(height))
        if size[0] <= 0 or size[1] <= 0 or size == self._last_window_size:
            return
        self._last_window_size = size
        self._publisher(
            WindowResizeEvent(
                width=size[0],
                height=size[1],
                sender=type(self).__name__,
                timestamp=pygame.time.get_ticks(),
            )
        )

    def _publisher(self, event: Event):
        """发布输入事件"""
        self.event_manager.publish(event)
        pass


IPS = InputSystem()

# Input System
