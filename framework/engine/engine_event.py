from dataclasses import dataclass
from .events import Event
from typing import Any


@dataclass
class QuitEvent(Event):
    """退出事件"""

    sender: str
    timestamp: int


@dataclass
class KeyDownEvent(Event):
    """键盘按下事件"""

    key: Any
    sender: str
    timestamp: int


@dataclass
class KeyUpEvent(Event):
    """键盘抬起事件"""

    key: Any
    sender: str
    timestamp: int


@dataclass
class MouseButtonDownEvent(Event):
    """鼠标按下事件"""

    button: int
    pos: tuple[int, int]
    sender: str
    timestamp: int


@dataclass
class MouseButtonUpEvent(Event):
    """鼠标抬起事件"""

    button: int
    pos: tuple[int, int]
    sender: str
    timestamp: int


@dataclass
class MouseMotionEvent(Event):
    """鼠标移动事件"""

    pos: tuple[int, int]
    rel: tuple[int, int]
    buttons: tuple[int, int, int]
    sender: str
    timestamp: int


@dataclass
class MouseWheelEvent(Event):
    """鼠标滚轮事件"""

    x: int
    y: int
    pos: tuple[int, int]
    sender: str
    timestamp: int
