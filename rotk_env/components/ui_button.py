"""
UI按钮组件
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Callable, Any
from framework import Component, SingletonComponent
import pygame


@dataclass
class UIButton(Component):
    """UI按钮组件"""

    # 按钮属性
    x: int
    y: int
    width: int
    height: int
    text: str

    # 样式属性
    background_color: Tuple[int, int, int] = (70, 70, 70)
    hover_color: Tuple[int, int, int] = (100, 100, 100)
    text_color: Tuple[int, int, int] = (255, 255, 255)
    border_color: Tuple[int, int, int] = (150, 150, 150)
    border_width: int = 2

    # 状态属性
    is_hovered: bool = False
    is_pressed: bool = False
    is_enabled: bool = True
    is_visible: bool = True

    # 回调函数名称（系统会根据这个名称调用相应的方法）
    callback_name: str = ""

    # 附加数据
    data: Any = None


@dataclass
class UIButtonCollection(SingletonComponent):
    """UI按钮集合单例组件"""

    buttons: dict = field(default_factory=dict)  # button_id -> entity_id 的映射

    def add_button(self, button_id: str, entity_id: int):
        """添加按钮"""
        self.buttons[button_id] = entity_id

    def remove_button(self, button_id: str):
        """移除按钮"""
        if button_id in self.buttons:
            del self.buttons[button_id]

    def get_button(self, button_id: str) -> Optional[int]:
        """获取按钮实体ID"""
        return self.buttons.get(button_id)


@dataclass
class UIPanel(Component):
    """UI面板组件"""

    x: int
    y: int
    width: int
    height: int
    background_color: Tuple[int, int, int] = (50, 50, 50)
    border_color: Tuple[int, int, int] = (100, 100, 100)
    border_width: int = 2
    alpha: int = 200  # 透明度
    is_visible: bool = True
