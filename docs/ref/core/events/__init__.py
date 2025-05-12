"""
事件模块

提供事件驱动架构的核心组件，包括事件管理器和事件类型定义
"""

from .event_manager import EventManager, Event
from .event_types import EventType

__all__ = ['EventManager', 'Event', 'EventType'] 