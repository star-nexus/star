import pygame
from typing import Tuple, Callable
from ..events import EventManager
from .ui_element import UIElement
from .ui_button import Button
from .ui_panel import Panel
from .ui_label import Label


class UIManager:
    """UI管理器，负责管理游戏界面元素"""

    def __init__(self, event_manager: EventManager):
        """初始化UI管理器

        Args:
            event_manager: 事件管理器
        """
        self.event_manager = event_manager
        self.root_elements = []
        self.focused_element = None

        # 注册事件监听
        self.event_manager.subscribe("MOUSEMOTION", self._handle_event)
        self.event_manager.subscribe("MOUSEBUTTONDOWN", self._handle_event)
        self.event_manager.subscribe("MOUSEBUTTONUP", self._handle_event)
        self.event_manager.subscribe("KEYDOWN", self._handle_event)
        self.event_manager.subscribe("KEYUP", self._handle_event)

    def add_element(self, element: UIElement) -> None:
        """添加UI元素

        Args:
            element: UI元素
        """
        self.root_elements.append(element)

    def remove_element(self, element: UIElement) -> None:
        """移除UI元素

        Args:
            element: UI元素
        """
        if element in self.root_elements:
            self.root_elements.remove(element)

        if self.focused_element == element:
            self.focused_element = None

    def clear(self) -> None:
        """清空所有UI元素"""
        self.root_elements.clear()
        self.focused_element = None

    def update(self, delta_time: float) -> None:
        """更新所有UI元素

        Args:
            delta_time: 帧间隔时间
        """
        for element in self.root_elements:
            element.update(delta_time)

    def render(self, render_manager) -> None:
        """渲染所有UI元素

        Args:
            render_manager: 渲染管理器
        """
        # 设置UI渲染层
        render_manager.set_layer(100)  # UI通常在最上层

        # 渲染所有根元素
        for element in self.root_elements:
            element.render(render_manager)

    def _process_event(self, event) -> None:
        """处理UI事件

        Args:
            event_data: 事件数据
        """
        event_type, event_data = event.popitem()

        # 从上到下传递事件给UI元素
        for element in reversed(self.root_elements):
            if element.process_event(event_type, event_data):
                break

    def create_button(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        text: str,
        font: pygame.font.Font,
        on_click: Callable = None,
    ) -> Button:
        """创建按钮

        Args:
            position: 按钮位置 (x, y)
            size: 按钮大小 (width, height)
            text: 按钮文本
            font: 字体对象
            on_click: 点击回调函数

        Returns:
            创建的按钮对象
        """
        button = Button(position, size, text, font)
        if on_click:
            button.set_on_click(on_click)
        self.add_element(button)
        return button

    def create_panel(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        color: Tuple[int, int, int] = (80, 80, 80),
    ) -> Panel:
        """创建面板

        Args:
            position: 面板位置 (x, y)
            size: 面板大小 (width, height)
            color: 面板颜色

        Returns:
            创建的面板对象
        """
        panel = Panel(position, size, color)
        self.add_element(panel)
        return panel

    def create_label(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        text: str,
        font: pygame.font.Font,
    ) -> Label:
        """创建标签

        Args:
            position: 标签位置 (x, y)
            size: 标签大小 (width, height)
            text: 标签文本
            font: 字体对象

        Returns:
            创建的标签对象
        """
        label = Label(position, size, text, font)
        self.add_element(label)
        return label
