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
    """Base class for systems (game logic over component data).

    ``required_components`` declares the component signature this system
    operates on. It is not enforced automatically -- systems still write their
    own queries -- but ``matched_entities()`` runs the declared query, so the
    declaration is executable rather than decorative.

    ``enabled`` is honoured by ``World.update``: a disabled system is skipped.
    """

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

    def matched_entities(self) -> Set["Entity"]:
        """Entities satisfying ``required_components``.

        Empty when nothing is declared or the system is not attached to a
        world -- callers get a signature-driven query without each system
        rebuilding the same ``with_component`` chain by hand.
        """
        if not self.required_components or self.world is None:
            return set()
        query = self.world.query()
        for component_type in self.required_components:
            query = query.with_component(component_type)
        return query.entities()
