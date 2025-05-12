"""
实体组件系统模块

提供ECS架构的核心组件，包括世界、系统、查询构建器和系统调度器
"""

from .world import World
from .system import System, SystemManager
from .query_builder import QueryBuilder
from .system_scheduler import SystemScheduler, SystemGroup

__all__ = [
    'World',
    'System',
    'SystemManager',
    'QueryBuilder',
    'SystemScheduler',
    'SystemGroup'
] 