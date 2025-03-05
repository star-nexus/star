import pygame
from typing import List, Dict, Any
from framework.core.ecs.system import System
from framework.core.ecs.entity import Entity
from framework.core.ecs.world import World
from ..components.ui_components import *
from framework.managers.events import EventManager, Message


class UIRenderSystem(System):
    """UI渲染系统，负责渲染具有UI组件的实体"""

    def __init__(
        self,
    ):
        super().__init__([UITransformComponent, UIRenderComponent], priority=100)

    def update(self, world: World, delta_time: float) -> None:
        # 在更新方法中更新按钮状态
        for entity in world.get_entities_with_components(
            UITransformComponent, UIRenderComponent, UIButtonComponent
        ):
            button = world.get_component(entity, UIButtonComponent)
            if button.is_pressed:
                button.current_color = button.pressed_color
            elif button.is_hovered:
                button.current_color = button.hover_color
            else:
                button.current_color = button.normal_color

    def render(self, world, render_manager):
        # 设置UI渲染层级
        render_manager.set_layer(100)

        # 获取所有UI实体并按z_index排序
        ui_entities = world.get_entities_with_components(
            UITransformComponent, UIRenderComponent
        )
        ui_entities.sort(
            key=lambda e: world.get_component(e, UITransformComponent).z_index
        )

        # 渲染UI元素
        for entity in ui_entities:
            transform = world.get_component(entity, UITransformComponent)
            render_comp = world.get_component(entity, UIRenderComponent)

            if not render_comp.visible:
                continue

            # 渲染基础矩形
            render_manager.draw_rect(render_comp.color, transform.rect)

            # 渲染边框
            if render_comp.border_color and render_comp.border_width > 0:
                render_manager.draw_rect(
                    render_comp.border_color, transform.rect, render_comp.border_width
                )

            # 渲染按钮
            button = world.get_component(entity, UIButtonComponent)
            if button:
                render_manager.draw_rect(button.current_color, transform.rect)

            # 渲染标签
            label = world.get_component(entity, UILabelComponent)
            if label:
                text_surface = label.font.render(label.text, True, label.text_color)
                text_rect = text_surface.get_rect(center=transform.rect.center)
                render_manager.draw_surface(text_surface, text_rect.topleft)


class UIEventSystem(System):
    """UI事件系统，处理UI相关的输入事件"""

    def __init__(
        self,
    ):
        super().__init__([UITransformComponent, UIInteractiveComponent], priority=10)
        self.focused_entity = None

    def setup(self, world: World, event_manager: EventManager):
        """系统初始化时调用，订阅相关事件"""
        self.event_manager = event_manager
        # 注册事件处理
        self.event_manager.subscribe(
            "MOUSEMOTION",
            lambda message: self._process_event(world, message),
        )
        self.event_manager.subscribe(
            "MOUSEBUTTONDOWN",
            lambda message: self._process_event(world, message),
        )
        self.event_manager.subscribe(
            "MOUSEBUTTONUP",
            lambda message: self._process_event(world, message),
        )
        self.event_manager.subscribe(
            "KEYDOWN",
            lambda message: self._process_event(world, message),
        )
        self.event_manager.subscribe(
            "KEYUP",
            lambda message: self._process_event(world, message),
        )

    def _process_event(self, world, message: Message) -> None:
        # 处理事件
        if not world:
            return

        event_type = message.topic
        event_data = message.data

        if event_type == "MOUSEMOTION":
            mouse_pos = event_data.get("pos")
            if not mouse_pos:
                return

            # 获取所有可交互UI元素并按照z_index倒序排列（从上到下）
            ui_entities = world.get_entities_with_components(
                UITransformComponent, UIInteractiveComponent
            )
            ui_entities.sort(
                key=lambda e: -world.get_component(e, UITransformComponent).z_index
            )

            # 处理悬停事件
            for entity in ui_entities:
                transform = world.get_component(entity, UITransformComponent)
                interactive = world.get_component(entity, UIInteractiveComponent)

                if not interactive.enabled:
                    continue

                rect = transform.rect
                is_hovered = rect.collidepoint(mouse_pos)

                # 检查是否有按钮组件并更新其状态
                button = world.get_component(entity, UIButtonComponent)
                if button:
                    if is_hovered != button.is_hovered:
                        button.is_hovered = is_hovered
                        if is_hovered and interactive.on_hover:
                            interactive.on_hover()
                        elif not is_hovered and interactive.on_leave:
                            interactive.on_leave()

                if is_hovered:
                    break  # 找到第一个被悬停的元素后停止

        elif event_type == "MOUSEBUTTONDOWN" and event_data.get("button") == 1:  # 左键
            mouse_pos = event_data.get("pos")
            if not mouse_pos:
                return

            ui_entities = world.get_entities_with_components(
                UITransformComponent, UIInteractiveComponent
            )
            ui_entities.sort(
                key=lambda e: -world.get_component(e, UITransformComponent).z_index
            )

            for entity in ui_entities:
                transform = world.get_component(entity, UITransformComponent)
                interactive = world.get_component(entity, UIInteractiveComponent)

                if not interactive.enabled:
                    continue

                if transform.rect.collidepoint(mouse_pos):
                    self.focused_entity = entity

                    # 如果有按钮组件，设置为按下状态
                    button = world.get_component(entity, UIButtonComponent)
                    if button:
                        button.is_pressed = True

                    break

        elif event_type == "MOUSEBUTTONUP" and event_data.get("button") == 1:  # 左键
            mouse_pos = event_data.get("pos")
            if not mouse_pos or not self.focused_entity:
                return

            entity = self.focused_entity
            if not world.has_component(
                entity, UITransformComponent
            ) or not world.has_component(entity, UIInteractiveComponent):
                self.focused_entity = None
                return

            transform = world.get_component(entity, UITransformComponent)
            interactive = world.get_component(entity, UIInteractiveComponent)

            # 检查是否有按钮组件
            button = world.get_component(entity, UIButtonComponent)
            if button:
                was_pressed = button.is_pressed
                button.is_pressed = False

                # 如果点击结束位置仍在按钮上，触发点击事件
                if (
                    was_pressed
                    and transform.rect.collidepoint(mouse_pos)
                    and interactive.on_click
                ):
                    interactive.on_click()

            self.focused_entity = None

    def update(self, world: World, delta_time: float) -> None:
        # 系统每帧更新逻辑，可根据需要添加
        pass
