import pygame
from typing import Tuple, Callable, Dict, Any, List
from framework.managers.events import EventManager, Message
from framework.core.ecs.world import World
from .components.ui_components import *
from .systems.ui_systems import UIRenderSystem, UIEventSystem


class UIManager:
    """UI管理器，负责创建和管理UI实体"""

    def __init__(self, event_manager: EventManager):
        """初始化UI管理器

        Args:
            event_manager: 事件管理器
        """
        # 创建专用的UI World
        self.world = World()
        self.event_manager = event_manager
        self.root_elements = []

        # 注册UI系统
        self.ui_render_system = UIRenderSystem(self.world)
        self.ui_event_system = UIEventSystem(self.world, event_manager)

        self.world.add_system(self.ui_render_system)
        self.world.add_system(self.ui_event_system)

    def update(self, delta_time: float) -> None:
        """更新UI世界

        Args:
            delta_time: 帧间隔时间
        """
        self.world.update(delta_time)

    def create_entity(
        self, position: Tuple[int, int], size: Tuple[int, int], z_index: int = 0
    ) -> int:
        """创建基础UI实体

        Args:
            position: 位置 (x, y)
            size: 大小 (width, height)
            z_index: Z轴索引，用于控制渲染顺序

        Returns:
            创建的实体ID
        """
        entity = self.world.create_entity()

        # 添加基础UI组件
        self.world.add_component(entity, UITransformComponent(position, size, z_index))
        self.world.add_component(entity, UIRenderComponent())
        self.world.add_component(entity, UIInteractiveComponent())
        self.world.add_component(entity, UIParentComponent())

        self.root_elements.append(entity)
        return entity

    def _process_event(self, message: Message) -> None:
        """事件处理由UIEventSystem负责，此方法保留为兼容现有代码"""
        pass

    def add_element(self, entity) -> None:
        """添加UI元素到根列表

        Args:
            entity: UI实体
        """
        if entity not in self.root_elements:
            self.root_elements.append(entity)

    def remove_element(self, entity) -> None:
        """从根列表中移除UI元素

        Args:
            element: UI实体
        """
        if entity in self.root_elements:
            self.root_elements.remove(entity)
            self.world.remove_entity(entity)

    def clear(self) -> None:
        """清空所有UI元素"""
        for entity in self.root_elements:
            self.world.remove_entity(entity)
        self.root_elements.clear()

    def create_button(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        text: str,
        font: pygame.font.Font,
        on_click: Callable = None,
        z_index: int = 0,
    ) -> int:
        """创建按钮

        Args:
            position: 按钮位置 (x, y)
            size: 按钮大小 (width, height)
            text: 按钮文本
            font: 字体对象
            on_click: 点击回调函数
            z_index: Z轴索引

        Returns:
            创建的按钮实体ID
        """
        entity = self.create_entity(position, size, z_index)

        # 添加按钮特定组件
        self.world.add_component(entity, UIButtonComponent())
        self.world.add_component(entity, UILabelComponent(text, font))

        # 设置点击回调
        if on_click:
            interactive = self.world.get_component(entity, UIInteractiveComponent)
            interactive.on_click = on_click

        return entity

    def create_panel(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        color: Tuple[int, int, int] = (80, 80, 80),
        z_index: int = 0,
        border_color: Tuple[int, int, int] = None,
        border_width: int = 0,
    ) -> int:
        """创建面板

        Args:
            position: 面板位置 (x, y)
            size: 面板大小 (width, height)
            color: 面板颜色
            z_index: Z轴索引
            border_color: 边框颜色
            border_width: 边框宽度

        Returns:
            创建的面板实体ID
        """
        entity = self.create_entity(position, size, z_index)

        # 设置面板渲染属性
        render_comp = self.world.get_component(entity, UIRenderComponent)
        render_comp.color = color
        render_comp.border_color = border_color
        render_comp.border_width = border_width

        return entity

    def create_label(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        text: str,
        font: pygame.font.Font,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        background_color: Tuple[int, int, int] = None,
        z_index: int = 0,
    ) -> int:
        """创建标签

        Args:
            position: 标签位置 (x, y)
            size: 标签大小 (width, height)
            text: 标签文本
            font: 字体对象
            text_color: 文本颜色
            background_color: 背景颜色
            z_index: Z轴索引

        Returns:
            创建的标签实体ID
        """
        entity = self.create_entity(position, size, z_index)

        # 添加标签特定组件
        self.world.add_component(entity, UILabelComponent(text, font, text_color))

        # 设置背景颜色
        if background_color:
            render_comp = self.world.get_component(entity, UIRenderComponent)
            render_comp.color = background_color

        return entity

    def add_child(self, parent_entity, child_entity) -> None:
        """添加子元素

        Args:
            parent_entity: 父实体ID
            child_entity: 子实体ID
        """
        # 更新父子关系
        parent_component = self.world.get_component(parent_entity, UIParentComponent)
        child_component = self.world.get_component(child_entity, UIParentComponent)

        if parent_component and child_component:
            # 从根元素中移除子元素
            if child_entity in self.root_elements:
                self.root_elements.remove(child_entity)

            # 更新父子关系
            parent_component.children.append(child_entity)
            child_component.parent = parent_entity

    def set_text(self, entity, text: str) -> None:
        """设置实体的文本

        Args:
            entity: 实体ID
            text: 文本内容
        """
        label_comp = self.world.get_component(entity, UILabelComponent)
        if label_comp:
            label_comp.text = text

    def set_visible(self, entity, visible: bool) -> None:
        """设置实体的可见性

        Args:
            entity: 实体ID
            visible: 是否可见
        """
        render_comp = self.world.get_component(entity, UIRenderComponent)
        if render_comp:
            render_comp.visible = visible

    def set_enabled(self, entity, enabled: bool) -> None:
        """设置实体的交互性

        Args:
            entity: 实体ID
            enabled: 是否启用交互
        """
        interactive_comp = self.world.get_component(entity, UIInteractiveComponent)
        if interactive_comp:
            interactive_comp.enabled = enabled
