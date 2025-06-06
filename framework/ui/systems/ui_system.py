import pygame
from typing import List, Type
from framework.ecs.system import System
from framework.ui.components.ui_components import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
    ScrollableListComponent,
)
from framework.engine.events import EventMessage, EventType
from framework.utils.logging_tool import get_logger


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
        self.font_lang = "zh"  # 默认字体语言为中文
        self.font_dict = {
            "zh": "pingfang",  # 中文字体
            "en": "arial",  # 英文字体
            "jp": "meiryo",  # 日文字体
            "kr": "nanumgothic",  # 韩文字体
        }
        # UI元素渲染层级
        self.ui_layer = 1000  # 使用较高的层级确保UI显示在游戏内容上方
        self.logger.debug("UI渲染系统已创建，渲染层级：{}".format(self.ui_layer))

    @property
    def lang(self) -> str:
        """获取当前UI语言"""
        return self.font_lang

    @lang.setter
    def lang(self, lang: str) -> None:
        """设置UI语言"""
        if lang in self.font_dict:
            self.logger.info(f"设置UI语言为: {lang}")
            self.font_lang = lang
        else:
            self.logger.warning(f"不支持的UI语言: {lang}，使用默认中文字体")
            self.font_lang = "zh"

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
        panel_entites = context.with_all(UITransformComponent, PanelComponent).result()
        self.logger.debug(f"找到 {len(panel_entites)} 个面板实体待渲染")
        for entity in panel_entites:
            transform = context.get_component(entity, UITransformComponent)
            panel = context.get_component(entity, PanelComponent)

            if not transform.visible:
                continue
            self._render_panel(transform, panel)

        # 处理滚动列表组件
        scrollable_entities = context.with_all(
            UITransformComponent, ScrollableListComponent
        ).result()
        for entity in scrollable_entities:
            transform = context.get_component(entity, UITransformComponent)
            scrollable_list = context.get_component(entity, ScrollableListComponent)

            if not transform.visible:
                continue
            self._render_scrollable_list(transform, scrollable_list)

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
                [
                    EventType.MOUSEBUTTON_DOWN,
                    EventType.KEY_DOWN,
                    EventType.MOUSE_MOTION,
                    EventType.MOUSE_WHEEL,
                ],
                self.handle_event,
            )
            self.logger.debug("UI事件订阅成功")
        else:
            self.logger.error("无法订阅UI事件：事件管理器未设置")

    def handle_event(self, event: EventMessage) -> None:
        """
        处理UI事件（如点击、滚动）

        参数:
            event: 事件消息对象
        """
        try:
            if (
                event.type == EventType.MOUSEBUTTON_DOWN and event.data["button"] == 1
            ):  # 左键点击
                self.logger.debug(f"接收到鼠标左键点击事件 - 位置: {event.data['pos']}")
                self._handle_button_click(event.data["pos"])

            elif event.type == EventType.MOUSE_WHEEL:  # 鼠标滚轮
                self._handle_scroll_wheel(event.data["pos"], event.data["y"])

        except Exception as e:
            self.logger.error(f"处理UI事件时发生错误: {e}")

    def _handle_button_click(self, mouse_pos):
        """处理按钮点击事件"""
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
            if rect.collidepoint(mouse_pos):
                self.logger.info(f"按钮被点击 - 文本: '{button.text}'")
                if button.callback:
                    self.logger.info("执行按钮回调函数")
                    button.callback()
                else:
                    self.logger.debug("按钮没有回调函数")

    def _handle_scroll_wheel(self, mouse_pos, scroll_y):
        """处理鼠标滚轮事件"""
        context = self.context
        scrollable_entities = context.with_all(
            UITransformComponent, ScrollableListComponent
        ).result()

        for entity in scrollable_entities:
            transform = context.get_component(entity, UITransformComponent)
            scrollable_list = context.get_component(entity, ScrollableListComponent)

            if not transform.visible:
                continue

            # 检查鼠标是否在滚动列表区域内
            rect = pygame.Rect(
                transform.x, transform.y, transform.width, transform.height
            )
            if rect.collidepoint(mouse_pos):
                # 计算可滚动的范围
                max_scroll = max(
                    0,
                    len(scrollable_list.messages)
                    - scrollable_list.max_visible_messages,
                )

                # 更新滚动偏移量
                scrollable_list.scroll_offset -= scroll_y  # 负值向上滚动，正值向下滚动
                scrollable_list.scroll_offset = max(
                    0, min(scrollable_list.scroll_offset, max_scroll)
                )

                # 如果滚动到底部，关闭自动滚动
                if scrollable_list.scroll_offset < max_scroll:
                    scrollable_list.auto_scroll = False
                else:
                    scrollable_list.auto_scroll = True

                self.logger.debug(
                    f"滚动列表滚动 - 偏移量: {scrollable_list.scroll_offset}/{max_scroll}"
                )

    def _render_scrollable_list(
        self, transform: UITransformComponent, scrollable_list: ScrollableListComponent
    ) -> None:
        """渲染可滚动列表"""
        if not self.context.render_manager:
            self.context.logger.warning("尝试渲染滚动列表，但渲染管理器未设置")
            return

        self.logger.debug(f"渲染滚动列表 - 消息数量: {len(scrollable_list.messages)}")

        # 创建列表表面
        list_surface = pygame.Surface(
            (transform.width, transform.height), pygame.SRCALPHA
        )

        # 绘制背景
        pygame.draw.rect(
            list_surface,
            scrollable_list.background_color,
            pygame.Rect(0, 0, transform.width, transform.height),
        )
        pygame.draw.rect(
            list_surface,
            (100, 100, 100),
            pygame.Rect(0, 0, transform.width, transform.height),
            1,
        )

        # 如果自动滚动且有新消息，滚动到底部
        if scrollable_list.auto_scroll and scrollable_list.messages:
            max_scroll = max(
                0, len(scrollable_list.messages) - scrollable_list.max_visible_messages
            )
            scrollable_list.scroll_offset = max_scroll

        # 计算显示的消息范围
        start_idx = scrollable_list.scroll_offset
        end_idx = min(
            start_idx + scrollable_list.max_visible_messages,
            len(scrollable_list.messages),
        )

        # 渲染可见的消息
        font = self._get_font(scrollable_list.font_size)
        for i, msg_idx in enumerate(range(start_idx, end_idx)):
            if msg_idx >= len(scrollable_list.messages):
                break

            message = scrollable_list.messages[msg_idx]
            y_pos = 5 + i * scrollable_list.line_height

            # 构建显示文本
            display_text = message.get("text", "")
            if scrollable_list.show_timestamps and "timestamp" in message:
                display_text = f"[{message['timestamp']}] {display_text}"

            # 渲染消息文本
            text_color = message.get("color", scrollable_list.text_color)
            text_surface = font.render(display_text, True, text_color)

            # 裁剪文本以适应宽度
            if text_surface.get_width() > transform.width - 20:
                # 简单的文本裁剪
                max_chars = int(
                    (transform.width - 20) / (scrollable_list.font_size * 0.6)
                )
                if len(display_text) > max_chars:
                    display_text = display_text[: max_chars - 3] + "..."
                    text_surface = font.render(display_text, True, text_color)

            list_surface.blit(text_surface, (5, y_pos))

        # 绘制滚动条
        if len(scrollable_list.messages) > scrollable_list.max_visible_messages:
            self._render_scrollbar(list_surface, transform, scrollable_list)

        # 添加到渲染队列
        self.context.render_manager.set_layer(self.ui_layer)
        self.context.render_manager.draw_surface(
            list_surface, (transform.x, transform.y)
        )

    def _render_scrollbar(
        self,
        surface,
        transform: UITransformComponent,
        scrollable_list: ScrollableListComponent,
    ):
        """绘制滚动条"""
        scrollbar_width = 10
        scrollbar_x = transform.width - scrollbar_width - 2

        # 计算滚动条高度和位置
        total_messages = len(scrollable_list.messages)
        visible_messages = scrollable_list.max_visible_messages

        if total_messages <= visible_messages:
            return

        scrollbar_height = int(
            (visible_messages / total_messages) * (transform.height - 10)
        )
        max_scroll = total_messages - visible_messages
        scroll_pos = int(
            (scrollable_list.scroll_offset / max_scroll)
            * (transform.height - 10 - scrollbar_height)
        )

        # 绘制滚动条背景
        pygame.draw.rect(
            surface,
            (60, 60, 60),
            pygame.Rect(scrollbar_x, 5, scrollbar_width, transform.height - 10),
        )

        # 绘制滚动条
        pygame.draw.rect(
            surface,
            scrollable_list.scroll_bar_color,
            pygame.Rect(scrollbar_x, 5 + scroll_pos, scrollbar_width, scrollbar_height),
        )

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
            self.font_cache[size] = pygame.font.SysFont(
                self.font_dict.get(self.font_lang), size
            )
        return self.font_cache[size]
