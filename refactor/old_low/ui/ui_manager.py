import pygame
from typing import List, Dict, Callable, Tuple, Optional, Any
import os


class UIElement:
    """UI元素基类"""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.visible = True
        self.enabled = True
        self.parent = None

    def set_position(self, x: int, y: int) -> None:
        """设置元素位置"""
        self.x = x
        self.y = y

    def set_size(self, width: int, height: int) -> None:
        """设置元素大小"""
        self.width = width
        self.height = height

    def get_absolute_position(self) -> Tuple[int, int]:
        """获取元素在屏幕上的绝对位置，考虑父元素位置"""
        if self.parent:
            parent_x, parent_y = self.parent.get_absolute_position()
            return parent_x + self.x, parent_y + self.y
        return self.x, self.y

    def contains_point(self, x: int, y: int) -> bool:
        """检查点(x,y)是否在元素范围内"""
        if not self.visible or not self.enabled:
            return False

        abs_x, abs_y = self.get_absolute_position()
        return abs_x <= x <= abs_x + self.width and abs_y <= y <= abs_y + self.height

    def update(self, delta_time: float) -> None:
        """更新元素状态"""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """渲染元素"""
        if self.visible:
            self._render(surface)

    def _render(self, surface: pygame.Surface) -> None:
        """实际渲染逻辑，子类重写此方法"""
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理事件，返回是否处理了事件"""
        if not self.visible or not self.enabled:
            return False
        return False


class TextLabel(UIElement):
    """文本标签UI元素"""

    def __init__(
        self,
        x: int,
        y: int,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int] = (255, 255, 255),
        align: str = "left",
    ):
        self.text = text
        self.font = font
        self.color = color
        self.align = align  # left, center, right

        # 计算文本大小
        text_surface = font.render(text, True, color)
        super().__init__(x, y, text_surface.get_width(), text_surface.get_height())

    def set_text(self, text: str) -> None:
        """设置文本内容"""
        self.text = text
        # 更新大小
        text_surface = self.font.render(text, True, self.color)
        self.width = text_surface.get_width()
        self.height = text_surface.get_height()

    def _render(self, surface: pygame.Surface) -> None:
        """渲染文本"""
        text_surface = self.font.render(self.text, True, self.color)

        # 获取绝对位置
        abs_x, abs_y = self.get_absolute_position()

        # 根据对齐方式调整位置
        if self.align == "center":
            abs_x -= text_surface.get_width() // 2
        elif self.align == "right":
            abs_x -= text_surface.get_width()

        surface.blit(text_surface, (abs_x, abs_y))


class Button(UIElement):
    """按钮UI元素"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        font: pygame.font.Font,
        normal_color: Tuple[int, int, int] = (100, 100, 100),
        hover_color: Tuple[int, int, int] = (150, 150, 150),
        press_color: Tuple[int, int, int] = (80, 80, 80),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(x, y, width, height)
        self.text = text
        self.font = font
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.press_color = press_color
        self.text_color = text_color
        self.on_click = on_click
        self.state = "normal"  # normal, hover, press

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理按钮事件"""
        if not self.enabled or not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            # 鼠标移动，更新hover状态
            if self.contains_point(*event.pos):
                if self.state == "normal":
                    self.state = "hover"
                return True
            else:
                if self.state != "normal":
                    self.state = "normal"

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 鼠标左键按下
            if self.contains_point(*event.pos):
                self.state = "press"
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # 鼠标左键释放
            was_pressed = self.state == "press"
            self.state = "hover" if self.contains_point(*event.pos) else "normal"

            # 如果按钮被点击（按下后释放）
            if was_pressed and self.state == "hover" and self.on_click:
                self.on_click()
                return True

        return False

    def _render(self, surface: pygame.Surface) -> None:
        """渲染按钮"""
        abs_x, abs_y = self.get_absolute_position()

        # 选择颜色
        if self.state == "normal":
            color = self.normal_color
        elif self.state == "hover":
            color = self.hover_color
        else:  # press
            color = self.press_color

        # 绘制按钮矩形
        pygame.draw.rect(
            surface,
            color,
            pygame.Rect(abs_x, abs_y, self.width, self.height),
            border_radius=5,
        )

        # 绘制按钮文本
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(
            center=(abs_x + self.width // 2, abs_y + self.height // 2)
        )
        surface.blit(text_surface, text_rect)


class Panel(UIElement):
    """面板UI元素，可以包含其他UI元素"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Optional[Tuple[int, int, int]] = None,
        alpha: int = 255,
    ):
        super().__init__(x, y, width, height)
        self.color = color
        self.alpha = alpha
        self.children: List[UIElement] = []

    def add(self, element: UIElement) -> None:
        """添加子UI元素"""
        self.children.append(element)
        element.parent = self

    def remove(self, element: UIElement) -> None:
        """移除子UI元素"""
        if element in self.children:
            self.children.remove(element)
            element.parent = None

    def update(self, delta_time: float) -> None:
        """更新所有子元素"""
        for child in self.children:
            child.update(delta_time)

    def _render(self, surface: pygame.Surface) -> None:
        """渲染面板及其子元素"""
        abs_x, abs_y = self.get_absolute_position()

        # 如果设置了颜色，绘制面板背景
        if self.color:
            if self.alpha < 255:
                # 创建透明表面
                panel_surface = pygame.Surface(
                    (self.width, self.height), pygame.SRCALPHA
                )
                panel_surface.fill((*self.color, self.alpha))
                surface.blit(panel_surface, (abs_x, abs_y))
            else:
                pygame.draw.rect(
                    surface,
                    self.color,
                    pygame.Rect(abs_x, abs_y, self.width, self.height),
                )

        # 渲染所有子元素
        for child in self.children:
            child.render(surface)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理事件，将事件传递给子元素"""
        if not self.enabled or not self.visible:
            return False

        # 从后往前处理，这样更上层的UI元素先收到事件
        for child in reversed(self.children):
            if child.handle_event(event):
                return True

        return False


class UIManager:
    """UI管理器，负责管理和渲染所有UI元素"""

    def __init__(self, engine: Any):
        self.engine = engine
        self.root_panel = Panel(0, 0, 0, 0)  # 根面板，不绘制
        self.panels: Dict[str, Panel] = {}  # 命名面板字典
        self.fonts: Dict[str, pygame.font.Font] = {}  # 字体缓存

        # 设置根面板大小为屏幕大小
        if hasattr(engine, "screen"):
            self.root_panel.width, self.root_panel.height = engine.screen.get_size()

        # 预加载一些默认字体
        self._load_default_fonts()

    def _load_default_fonts(self) -> None:
        """加载默认字体"""
        self.fonts["default"] = pygame.font.Font(None, 24)
        self.fonts["default_small"] = pygame.font.Font(None, 16)
        self.fonts["default_large"] = pygame.font.Font(None, 32)
        self.fonts["title"] = pygame.font.Font(None, 48)

    def load_font(self, name: str, font_path: str, size: int) -> pygame.font.Font:
        """加载字体并缓存

        Args:
            name: 字体名称，用于后续获取
            font_path: 字体文件路径
            size: 字体大小

        Returns:
            加载的字体对象
        """
        key = f"{name}_{size}"
        if key not in self.fonts:
            try:
                # 检查字体路径
                if not os.path.exists(font_path):
                    print(f"字体文件不存在: {font_path}")
                    return self.get_font("default", size)

                self.fonts[key] = pygame.font.Font(font_path, size)
            except Exception as e:
                print(f"加载字体失败: {e}")
                return self.get_font("default", size)
        return self.fonts[key]

    def get_font(
        self, name: str = "default", size: Optional[int] = None
    ) -> pygame.font.Font:
        """获取已加载的字体

        Args:
            name: 字体名称
            size: 字体大小，如果指定则返回指定大小的字体

        Returns:
            字体对象
        """
        if size is not None:
            key = f"{name}_{size}"
            if key not in self.fonts:
                # 尝试根据基础字体创建不同大小的字体
                base_font_name = name
                if base_font_name in self.fonts:
                    base_font = self.fonts[base_font_name]
                    try:
                        if hasattr(base_font, "path"):
                            self.fonts[key] = pygame.font.Font(base_font.path, size)
                        else:
                            self.fonts[key] = pygame.font.Font(None, size)
                    except Exception as e:
                        print(f"创建字体大小失败: {e}")
                        self.fonts[key] = pygame.font.Font(None, size)
                else:
                    # 如果找不到基础字体，使用默认字体
                    self.fonts[key] = pygame.font.Font(None, size)
            return self.fonts[key]
        else:
            return self.fonts.get(
                name, self.fonts.get("default", pygame.font.Font(None, 24))
            )

    def create_panel(
        self,
        name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Optional[Tuple[int, int, int]] = None,
        alpha: int = 255,
    ) -> Panel:
        """创建并注册一个命名面板"""
        panel = Panel(x, y, width, height, color, alpha)
        self.panels[name] = panel
        self.root_panel.add(panel)
        return panel

    def get_panel(self, name: str) -> Optional[Panel]:
        """获取命名面板"""
        return self.panels.get(name)

    def remove_panel(self, name: str) -> None:
        """移除命名面板"""
        if name in self.panels:
            panel = self.panels[name]
            self.root_panel.remove(panel)
            del self.panels[name]
        # 即使面板不存在也不抛出异常，提高容错性

    def add_element(self, panel_name: str, element: UIElement) -> None:
        """添加UI元素到指定面板"""
        panel = self.get_panel(panel_name)
        if panel:
            panel.add(element)

    def create_text_label(
        self,
        panel_name: str,
        x: int,
        y: int,
        text: str,
        font_name: str = "default",
        size: Optional[int] = None,
        color: Tuple[int, int, int] = (255, 255, 255),
        align: str = "left",
    ) -> Optional[TextLabel]:
        """便捷方法：创建文本标签并添加到面板

        Args:
            panel_name: 面板名称
            x, y: 标签位置
            text: 文本内容
            font_name: 字体名称
            size: 字体大小
            color: 文本颜色
            align: 对齐方式 (left, center, right)

        Returns:
            创建的文本标签
        """
        panel = self.get_panel(panel_name)
        if not panel:
            return None

        font = self.get_font(font_name, size)
        label = TextLabel(x, y, text, font, color, align)
        panel.add(label)
        return label

    def create_button(
        self,
        panel_name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        font_name: str = "default",
        size: Optional[int] = None,
        normal_color: Tuple[int, int, int] = (100, 100, 100),
        hover_color: Tuple[int, int, int] = (150, 150, 150),
        press_color: Tuple[int, int, int] = (80, 80, 80),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        on_click: Optional[Callable[[], None]] = None,
    ) -> Optional[Button]:
        """便捷方法：创建按钮并添加到面板

        Args:
            panel_name: 面板名称
            x, y: 按钮位置
            width, height: 按钮大小
            text: 按钮文本
            font_name: 字体名称
            size: 字体大小
            normal_color: 正常状态颜色
            hover_color: 悬停状态颜色
            press_color: 按下状态颜色
            text_color: 文本颜色
            on_click: 点击回调函数

        Returns:
            创建的按钮
        """
        panel = self.get_panel(panel_name)
        if not panel:
            return None

        font = self.get_font(font_name, size)
        button = Button(
            x,
            y,
            width,
            height,
            text,
            font,
            normal_color,
            hover_color,
            press_color,
            text_color,
            on_click,
        )
        panel.add(button)
        return button

    def update(self, delta_time: float) -> None:
        """更新所有UI元素"""
        self.root_panel.update(delta_time)

    def render(self, surface: pygame.Surface) -> None:
        """渲染所有UI元素"""
        self.root_panel.render(surface)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理UI事件"""
        return self.root_panel.handle_event(event)
