# ECS 核心

from abc import ABC, abstractmethod
from typing import TypeVar, Set, Type

# 实体类型定义
Entity = int

# 查询缓存相关类型
QueryKey = str  # 查询缓存键类型

# 组件类型定义
ComponentType = TypeVar("ComponentType", bound="Component")


class Component(ABC):
    """
    组件基类 - 纯数据容器

    所有组件都应该继承此类，并使用dataclass装饰器
    组件只包含数据，不包含逻辑
    """

    pass


class SingletonComponent(Component):
    """
    单例组件基类 - 全局唯一的组件

    单例组件不属于任何特定实体，在整个世界中只有一个实例
    """

    pass


# 系统基类 - 包含游戏逻辑


class System(ABC):
    def __init__(
        self, required_components: Set[Type[Component]] = None, priority: int = 100
    ):
        self.required_components = required_components or set()
        self.priority = priority
        self.enabled = True
        self.world = None

    @abstractmethod
    def initialize(self, world: "World") -> None:  # type: ignore
        """初始化系统，设置世界引用"""
        pass

    @abstractmethod
    def subscribe_events(self) -> None:
        """订阅事件"""
        pass

    @abstractmethod
    def update(self, delta_time: float) -> None:
        """更新系统逻辑"""
        pass
