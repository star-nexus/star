"""
Framework - Simplified ECS Architecture
实体-组件-系统架构

主要特点：
- 简化的组件查询
- 更清晰的系统接口
- 优化的性能
"""

from .ecs.core import Entity, Component, System, SingletonComponent
from .ecs.world import World
from .ecs.builder import EntityBuilder, QueryBuilder
from .engine.game_engine import GameEngine
from .engine.events import EventBus, Event, EBS
from .engine.scenes import SceneManager, SMS
from .engine.renders import RenderEngine, RMS
from .engine.inputs import InputSystem, IPS
from .engine.engine_event import (
    QuitEvent,
    KeyDownEvent,
    KeyUpEvent,
    MouseButtonDownEvent,
    MouseButtonUpEvent,
    MouseMotionEvent,
    MouseWheelEvent,
)

__all__ = [
    "World",
    "Entity",
    "Component",
    "System",
    "SingletonComponent",
    "EntityBuilder",
    "QueryBuilder",
    "GameEngine",
    "EventBus",
    "Event",
    "SceneManager",
    "RenderEngine",
    "InputSystem",
    "QuitEvent",
    "KeyDownEvent",
    "KeyUpEvent",
    "MouseButtonDownEvent",
    "MouseButtonUpEvent",
    "MouseMotionEvent",
    "MouseWheelEvent",
    # 全局访问函数
    "EBS",
    "SMS",
    "RMS",
    "IPS",
]
