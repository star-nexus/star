"""
简化的事件系统
"""

from typing import Dict, List, Callable, Any, Type
from dataclasses import dataclass
from abc import ABC


class Event(ABC):
    """事件基类"""

    pass


class EventBus:
    """
    事件总线 - 单例模式

    负责事件的发布和订阅
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._listeners: Dict[Type[Event], List[Callable]] = {}

    def subscribe(
        self, event_type: Type[Event], callback: Callable[[Event], None]
    ) -> None:
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(
        self, event_type: Type[Event], callback: Callable[[Event], None]
    ) -> None:
        """取消订阅事件"""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(callback)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """发布事件"""
        event_type = type(event)
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"事件处理错误: {e}")

    def clear(self) -> None:
        """清空所有监听器"""
        self._listeners.clear()


EBS = EventBus()
