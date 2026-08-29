"""
Framework - ECS core (Entity-Component-System).

This package is deliberately pygame-free: importing it must not touch SDL or
open a display, so headless rule tests and analysis scripts can use `World`
without a graphics stack. Runtime/engine symbols (`GameEngine`, `RMS`, `EBS`,
`SMS`, `IPS`, input events) live in `framework.engine` and pull in pygame.
"""

from .ecs.core import Entity, Component, System, SingletonComponent
from .ecs.world import World
from .ecs.builder import EntityBuilder, QueryBuilder
from .ecs.profiling import set_profiler

__all__ = [
    "World",
    "Entity",
    "Component",
    "System",
    "SingletonComponent",
    "EntityBuilder",
    "QueryBuilder",
    "set_profiler",
]
