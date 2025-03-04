from typing import Dict, Any
import pygame
from .events import EventManager, Message


class InputManager:
    """输入管理器，负责处理用户输入事件"""

    def __init__(self, event_manager: EventManager):
        """初始化输入管理器

        Args:
            event_manager: 事件管理器实例
        """
        self.event_manager = event_manager
        self._key_states: Dict[int, bool] = {}
        self._mouse_states: Dict[int, bool] = {}
        self._mouse_pos = (0, 0)

    def process_event(self, event) -> None:
        """处理输入事件

        Args:
            event: Pygame事件对象
        """
        # 处理键盘事件
        if event.type == pygame.KEYDOWN:
            self._key_states[event.key] = True
            self.publisher(
                "KEYDOWN",
                Message(topic="KEYDOWN", data_type="key_event", data=event.key),
            )
        elif event.type == pygame.KEYUP:
            self._key_states[event.key] = False
            self.publisher(
                "KEYUP", Message(topic="KEYUP", data_type="key_event", data=event.key)
            )

        # 处理鼠标事件
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._mouse_states[event.button] = True
            self.publisher(
                "MOUSEBUTTONDOWN",
                Message(
                    topic="MOUSEBUTTONDOWN",
                    data_type="mouse_event",
                    data={"button": event.button, "pos": event.pos},
                ),
            )
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_states[event.button] = False
            self.publisher(
                "MOUSEBUTTONUP",
                Message(
                    topic="MOUSEBUTTONUP",
                    data_type="mouse_event",
                    data={"button": event.button, "pos": event.pos},
                ),
            )
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_pos = event.pos
            self.publisher(
                "MOUSEMOTION",
                Message(
                    topic="MOUSEMOTION",
                    data_type="mouse_event",
                    data={"pos": event.pos, "rel": event.rel},
                ),
            )

    def publisher(self, topic: str, message: Any) -> None:
        """发布事件

        Args:
            topic: 事件类型
            message: 事件数据
        """
        self.event_manager.publish(topic, message)

    def is_key_pressed(self, key: int) -> bool:
        """检查指定键是否被按下

        Args:
            key: 键码

        Returns:
            bool: 如果键被按下返回True，否则返回False
        """
        return self._key_states.get(key, False)

    def is_mouse_button_pressed(self, button: int) -> bool:
        """检查指定鼠标按键是否被按下

        Args:
            button: 鼠标按键编号

        Returns:
            bool: 如果按键被按下返回True，否则返回False
        """
        return self._mouse_states.get(button, False)

    def get_mouse_position(self) -> tuple[int, int]:
        """获取当前鼠标位置

        Returns:
            tuple[int, int]: 鼠标位置坐标 (x, y)
        """
        return self._mouse_pos
