from dataclasses import dataclass, field
from typing import Tuple, Optional, Callable, List, Dict, Any
import pygame
from framework.core.ecs.component import Component


@dataclass
class UITransformComponent(Component):
    """UI元素的位置和大小"""

    position: Tuple[int, int]
    size: Tuple[int, int]
    z_index: int = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.position[0], self.position[1], self.size[0], self.size[1]
        )


@dataclass
class UIRenderComponent(Component):
    """UI元素的渲染属性"""

    visible: bool = True
    color: Tuple[int, int, int] = (100, 100, 100)
    border_color: Optional[Tuple[int, int, int]] = None
    border_width: int = 0


@dataclass
class UILabelComponent(Component):
    """标签组件"""

    text: str
    font: pygame.font.Font
    text_color: Tuple[int, int, int] = (255, 255, 255)


@dataclass
class UIButtonComponent(Component):
    """按钮组件"""

    normal_color: Tuple[int, int, int] = (100, 100, 100)
    hover_color: Tuple[int, int, int] = (150, 150, 150)
    pressed_color: Tuple[int, int, int] = (50, 50, 50)
    current_color: Tuple[int, int, int] = field(default=(100, 100, 100), init=False)
    is_hovered: bool = field(default=False, init=False)
    is_pressed: bool = field(default=False, init=False)


@dataclass
class UIInteractiveComponent(Component):
    """交互组件，处理事件响应"""

    enabled: bool = True
    on_click: Optional[Callable] = None
    on_hover: Optional[Callable] = None
    on_leave: Optional[Callable] = None


@dataclass
class UIParentComponent(Component):
    """父子关系组件，管理UI层次结构"""

    children: List[int] = field(default_factory=list)
    parent: Optional[int] = None
