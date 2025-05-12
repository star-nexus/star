from dataclasses import dataclass
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
