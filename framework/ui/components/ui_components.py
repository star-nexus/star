from dataclasses import dataclass, field
from typing import List
from framework.ecs.component import Component


@dataclass
class UITransformComponent(Component):
    """基础UI组件，存储UI元素通用属性"""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    enabled: bool = True


@dataclass
class ButtonComponent(Component):
    """按钮组件，存储按钮特定属性"""

    text: str = ""
    color: tuple = (100, 100, 200)
    hover_color: tuple = (120, 120, 220)
    text_color: tuple = (255, 255, 255)
    font_size: int = 20
    callback: callable = None
    hovered: bool = False


@dataclass
class PanelComponent(Component):
    """面板组件，存储面板特定属性"""

    color: tuple = (50, 50, 50, 200)
    border_color: tuple = (255, 255, 255)
    border_width: int = 0


@dataclass
class TextComponent(Component):
    """文本组件，存储文本特定属性"""

    text: str = ""
    color: tuple = (255, 255, 255)
    font_size: int = 20
    centered: bool = False


@dataclass
class ScrollableListComponent(Component):
    """可滚动列表组件，用于显示消息记录等"""

    messages: List[dict] = field(
        default_factory=list
    )  # 消息列表，每个消息包含{text, color, timestamp}
    max_visible_messages: int = 5  # 最多显示的消息数量
    max_stored_messages: int = 50  # 最多存储的消息数量
    scroll_offset: int = 0  # 滚动偏移量
    line_height: int = 25  # 每行高度
    font_size: int = 16  # 字体大小
    text_color: tuple = (255, 255, 255)  # 默认文本颜色
    background_color: tuple = (40, 40, 60, 200)  # 背景颜色
    scroll_bar_color: tuple = (100, 100, 100)  # 滚动条颜色
    show_timestamps: bool = True  # 是否显示时间戳
    auto_scroll: bool = True  # 新消息时自动滚动到底部
