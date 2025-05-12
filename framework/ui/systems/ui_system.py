import pygame
from typing import List, Type
from framework.ecs.system import System
from framework.ui.components.ui_components import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.engine.events import EventMessage, EventType
from framework.utils.logging import get_logger


class UISystem(System):
    """
    UI渲染系统，负责渲染和处理所有UI元素
    """

    def __init__(self, priority: int = 100):
        # UI系统通常应该在其他系统之后运行，所以给它较高的优先级数值
        super().__init__(
            required_components=[UITransformComponent],
            priority=priority,
        )
        # 初始化日志记录器
        self.logger = get_logger("UISystem")
        # 初始化pygame字体
        pygame.font.init()
        self.font_cache = {}  # 字体缓存
        # UI元素渲染层级
        self.ui_layer = 1000  # 使用较高的层级确保UI显示在游戏内容上方
        self.logger.debug("UI渲染系统已创建，渲染层级：{}".format(self.ui_layer))

    def initialize(self, context):
        """初始化UI系统"""
        self.logger.info("初始化UI渲染系统")
        self.context = context

        # 记录初始化状态信息
        self.logger.info(
            f"UI系统初始化 - 优先级: {self.priority}, UI层级: {self.ui_layer}"
        )

        self.subscribe_events()

        # 检查渲染管理器
        if self.context.render_manager:
            self.logger.info("成功获取渲染管理器")
        else:
            self.logger.error("无法获取渲染管理器，UI可能无法正常显示")

    def update(self, delta_time: float) -> None:
        """
        更新并渲染所有UI元素

        参数:
            delta_time: 上一帧到当前帧的时间差（秒）
        """
        if not self.context:
            return

        self.logger.debug(f"UI渲染系统更新 - delta_time: {delta_time:.4f}秒")
        context = self.context

        # 处理面板组件
        # 使用context的查询接口找到同时拥有UITransformComponent和PanelComponent的实体
        panel_entites = context.with_all(UITransformComponent, PanelComponent).result()
        self.logger.debug(f"找到 {len(panel_entites)} 个面板实体待渲染")
        for entity in panel_entites:
            transform = context.get_component(entity, UITransformComponent)
            panel = context.get_component(entity, PanelComponent)

            if not transform.visible:
                continue
            self._render_panel(transform, panel)

        # 处理文本组件
        text_entites = context.with_all(UITransformComponent, TextComponent).result()
        for entity in text_entites:
            transform = context.get_component(entity, UITransformComponent)
            text = context.get_component(entity, TextComponent)

            if not transform.visible:
                continue
            self._render_text(transform, text)

        # 处理和更新按钮组件
        button_entites = context.with_all(
            UITransformComponent, ButtonComponent
        ).result()
        for entity in button_entites:
            transform = context.get_component(entity, UITransformComponent)
            button = context.get_component(entity, ButtonComponent)

            if not transform.visible:
                continue
            self._update_button(transform, button, delta_time)
            self._render_button(transform, button)

    def subscribe_events(self) -> None:
        """订阅事件"""
        self.logger.debug("正在订阅UI事件")
        if self.context.event_manager:
            self.context.event_manager.subscribe(
                [EventType.MOUSEBUTTON_DOWN, EventType.KEY_DOWN], self.handle_event
            )
            self.logger.debug("UI事件订阅成功")
        else:
            self.logger.error("无法订阅UI事件：事件管理器未设置")

    def handle_event(self, event: EventMessage) -> None:
        """
        处理UI事件（如点击）

        参数:
            event: 事件消息对象
        """
        try:
            if (event.type == EventType.MOUSEBUTTON_DOWN and event.data["button"] == 1):  # 左键点击
                self.logger.debug(f"接收到鼠标左键点击事件 - 位置: {event.data['pos']}")
                context = self.context
                button_entites = context.with_all(
                    UITransformComponent, ButtonComponent
                ).result()

                if not button_entites:
                    self.logger.debug("没有找到可点击的按钮实体")
                    return

                self.logger.debug(f"检查 {len(button_entites)} 个按钮实体是否被点击")

                for entity in button_entites:
                    transform = context.get_component(entity, UITransformComponent)
                    button = context.get_component(entity, ButtonComponent)

                    if transform is None:
                        self.logger.warning(f"实体 {entity} 没有UITransformComponent，跳过")
                        continue

                    if not transform.visible or not transform.enabled:
                        continue

                    # 计算按钮的矩形区域
                    rect = pygame.Rect(
                        transform.x - transform.width // 2,
                        transform.y - transform.height // 2,
                        transform.width,
                        transform.height,
                    )

                    # 检查点击是否在按钮区域内
                    if rect.collidepoint(event.data["pos"]):
                        self.logger.info(f"按钮被点击 - 文本: '{button.text}'")
                        if button.callback:
                            self.logger.info("执行按钮回调函数")
                            button.callback()
                        else:
                            self.logger.debug("按钮没有回调函数")
        except Exception as e:
            self.logger.error(f"处理UI事件时发生错误: {e}")

    def _update_button(
        self,
        transform: UITransformComponent,
        button: ButtonComponent,
        delta_time: float,
    ) -> None:
        """更新按钮状态（如hover效果）"""
        # 检查鼠标是否悬停在按钮上
        mouse_pos = pygame.mouse.get_pos()
        rect = pygame.Rect(
            transform.x - transform.width // 2,
            transform.y - transform.height // 2,
            transform.width,
            transform.height,
        )
        was_hovered = button.hovered
        button.hovered = rect.collidepoint(mouse_pos)

        # 当悬停状态改变时记录日志
        if was_hovered != button.hovered:
            self.logger.debug(
                f"按钮悬停状态变更 - 文本: '{button.text}', 状态: {button.hovered}"
            )

    def _render_button(
        self, transform: UITransformComponent, button: ButtonComponent
    ) -> None:
        """渲染按钮"""
        # 检查是否有渲染管理器
        if not self.context.render_manager:
            self.context.logger.warning("尝试渲染按钮，但渲染管理器未设置")
            return

        self.logger.debug(
            f"渲染按钮 - 文本: '{button.text}', 位置: ({transform.x}, {transform.y}), 悬停状态: {button.hovered}"
        )

        # 创建一个临时的表面来绘制按钮
        button_surface = pygame.Surface(
            (transform.width, transform.height), pygame.SRCALPHA
        )

        # 计算按钮矩形（相对于按钮表面）
        rect = pygame.Rect(0, 0, transform.width, transform.height)

        # 绘制按钮背景
        color = button.hover_color if button.hovered else button.color
        pygame.draw.rect(button_surface, color, rect)
        pygame.draw.rect(button_surface, (255, 255, 255), rect, 2)  # 边框

        # 绘制按钮文本
        font = self._get_font(button.font_size)
        text_surface = font.render(button.text, True, button.text_color)
        text_rect = text_surface.get_rect(
            center=(transform.width // 2, transform.height // 2)
        )
        button_surface.blit(text_surface, text_rect)

        # 设置UI层级并添加到渲染队列
        self.context.render_manager.set_layer(self.ui_layer)
        self.context.render_manager.draw_surface(
            button_surface,
            (transform.x - transform.width // 2, transform.y - transform.height // 2),
        )

    def _render_panel(
        self, transform: UITransformComponent, panel: PanelComponent
    ) -> None:
        """渲染面板"""
        # 检查是否有渲染管理器
        if not self.context.render_manager:
            self.context.logger.warning("尝试渲染面板，但渲染管理器未设置")
            return

        self.logger.debug(
            f"渲染面板 - 位置: ({transform.x}, {transform.y}), 尺寸: {transform.width}x{transform.height}"
        )

        # 创建一个临时的表面来绘制面板
        panel_surface = pygame.Surface(
            (transform.width, transform.height), pygame.SRCALPHA
        )

        # 绘制面板背景
        pygame.draw.rect(
            panel_surface,
            panel.color,
            pygame.Rect(0, 0, transform.width, transform.height),
        )

        # 如果有边框，绘制边框
        if panel.border_width > 0:
            pygame.draw.rect(
                panel_surface,
                panel.border_color,
                pygame.Rect(0, 0, transform.width, transform.height),
                panel.border_width,
            )

        # 设置UI层级并添加到渲染队列（使用比按钮低一级的层级，确保面板在按钮下方）
        self.context.render_manager.set_layer(self.ui_layer - 1)
        # 计算绘制位置 - 对于背景面板这类从(0,0)开始的元素需要特殊处理
        position = (transform.x, transform.y)
        self.context.render_manager.draw_surface(panel_surface, position)

    def _render_text(
        self, transform: UITransformComponent, text_comp: TextComponent
    ) -> None:
        """渲染文本"""
        # 检查是否有渲染管理器
        if not self.context.render_manager:
            self.context.logger.warning("尝试渲染文本，但渲染管理器未设置")
            return

        self.logger.debug(
            f"渲染文本 - 内容: '{text_comp.text}', 位置: ({transform.x}, {transform.y})"
        )

        # 创建文本表面
        font = self._get_font(text_comp.font_size)
        text_surface = font.render(text_comp.text, True, text_comp.color)

        # 根据是否居中，确定文本位置
        if text_comp.centered:
            position = (
                transform.x - text_surface.get_width() // 2,
                transform.y - text_surface.get_height() // 2,
            )
        else:
            position = (transform.x, transform.y)

        # 设置UI层级并添加到渲染队列（使用比按钮高一级的层级，确保文本在所有UI元素上方）
        self.context.render_manager.set_layer(self.ui_layer + 1)
        self.context.render_manager.draw_surface(text_surface, position)
        self.logger.debug(
            f"添加文本到渲染队列 - 位置: {position}, 层级: {self.ui_layer + 1}"
        )

    def _get_font(self, size: int) -> pygame.font.Font:
        """获取或缓存指定大小的字体"""
        if size not in self.font_cache:
            self.logger.debug(f"缓存新字体 - 大小: {size}")
            self.font_cache[size] = pygame.font.Font(None, size)
        return self.font_cache[size]
