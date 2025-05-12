"""
核心模块

提供游戏引擎的核心功能，包括ECS架构、事件系统和配置管理
"""

from .ecs import World, System, SystemManager, QueryBuilder, SystemScheduler, SystemGroup
from .events import EventManager, Event, EventType
from .config import ConfigManager

__all__ = [
    # ECS
    'World',
    'System',
    'SystemManager',
    'QueryBuilder',
    'SystemScheduler',
    'SystemGroup',
    
    # 事件
    'EventManager',
    'Event',
    'EventType',
    
    # 配置
    'ConfigManager'
] 