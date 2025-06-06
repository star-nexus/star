from turtle import Screen
from typing import (
    Type,
    Optional,
    Callable,
    Any,
    TypeVar,
    # TYPE_CHECKING,
)
import logging

from framework.ecs.entity import Entity
from framework.ecs.component import Component
from framework.ecs.query import QueryManager, QueryBuilder, Query
from framework.ecs.manager import EntityManager, ComponentManager, SystemManager

# Avoid circular imports by importing these only when needed
# from framework.engine.events import EventManager
# from framework.engine.inputs import InputManager
# from framework.engine.renders import RenderManager
# from framework.engine.scenes import SceneManager

# if TYPE_CHECKING:
from framework.engine.events import EventManager, EventMessage
from framework.engine.inputs import InputManager
from framework.engine.renders import RenderManager
from framework.engine.scenes import SceneManager

C = TypeVar("C", bound=Component)


class ECSContext:
    """
    ECS上下文，包含所有管理器的引用，用于系统间通信和资源共享
    """

    def __init__(self, world=None):
        # 基础管理器
        self.entity_manager: Optional[EntityManager] = None
        self.component_manager: Optional[ComponentManager] = None
        self.system_manager: Optional[SystemManager] = None
        self.query_manager: Optional[QueryManager] = None

        # 扩展管理器
        self.event_manager: Optional["EventManager"] = None
        self.input_manager: Optional["InputManager"] = None
        self.render_manager: Optional["RenderManager"] = None
        self.scene_manager: Optional["SceneManager"] = None
        # self.resource_manager = None

        self.executor = None

        # 日志记录器
        self.logger = logging.getLogger("ECSContext")

    @property
    def screen(self) -> Screen:
        """获取屏幕对象"""
        if self.render_manager:
            return self.render_manager.screen
        self.logger.warning("尝试获取屏幕对象，但渲染管理器未设置")
        return None

    def init_ecs_managers(
        self, entity_manager, component_manager, system_manager, query_manager
    ):
        """
        初始化基础管理器

        参数:
            entity_manager: 实体管理器
            component_manager: 组件管理器
            system_manager: 系统管理器
            query_manager: 查询管理器
        """
        self.entity_manager = entity_manager
        self.component_manager = component_manager
        self.system_manager = system_manager
        self.query_manager = query_manager

    def init_engine_managers(
        self, event_manager, input_manager, render_manager, scene_manager
    ):
        """
        初始化引擎管理器

        参数:
            event_manager: 事件管理器
            input_manager: 输入管理器
            render_manager: 渲染管理器
            scene_manager: 场景管理器
        """
        self.event_manager = event_manager
        self.input_manager = input_manager
        self.render_manager = render_manager
        self.scene_manager = scene_manager

    # EntityManager 统一接口
    def entity_exists(self, entity: Entity) -> bool:
        """检查实体是否存在"""
        return (
            self.entity_manager.is_entity_exists(entity)
            if self.entity_manager
            else False
        )

    def has_component(self, entity: Entity, component_type: Type[C]) -> bool:
        """检查实体是否拥有指定组件"""
        if self.component_manager:
            return self.component_manager.has_component(entity, component_type)
        self.logger.error("尝试检查组件，但组件管理器未设置")
        return False

    def add_component(self, entity: Entity, component: C) -> None:
        """添加组件到实体"""
        if self.component_manager:
            self.component_manager.add_component(entity, component)
        else:
            self.logger.error("尝试添加组件，但组件管理器未设置")

    def get_component(self, entity: Entity, component_type: Type[C]) -> Optional[C]:
        """获取实体的指定组件"""
        if self.component_manager:
            return self.component_manager.get_component(entity, component_type)
        self.logger.error("尝试获取组件，但组件管理器未设置")
        return None

    # QueryManager 统一接口
    def query(self) -> QueryBuilder:
        """创建一个查询构建器"""
        if self.query_manager:
            return self.query_manager.query()
        self.logger.error("尝试创建查询，但查询管理器未设置")
        return None

    def with_all(self, *component_types: Type[Component]) -> QueryBuilder:
        """查询包含所有指定组件的实体"""
        if self.query_manager:
            return self.query_manager.with_all(*component_types)
        self.logger.error("尝试创建查询，但查询管理器未设置")
        return None

    def without(self, *component_types: Type[Component]) -> QueryBuilder:
        """查询不包含指定组件的实体"""
        if self.query_manager:
            return self.query_manager.without(*component_types)
        self.logger.error("尝试创建查询，但查询管理器未设置")
        return None

    def with_any(self, *component_types: Type[Component]) -> QueryBuilder:
        """查询包含任意一个指定组件的实体"""
        if self.query_manager:
            return self.query_manager.with_any(*component_types)
        self.logger.error("尝试创建查询，但查询管理器未设置")
        return None

    def where(self, predicate: Callable) -> QueryBuilder:
        """使用自定义条件查询实体"""
        if self.query_manager:
            return self.query_manager.where(predicate)
        self.logger.error("尝试创建查询，但查询管理器未设置")
        return None

    def get_cached_query(self, cache_key: str) -> Optional[Query]:
        """获取缓存的查询"""
        if self.query_manager:
            return self.query_manager.get_cached_query(cache_key)
        self.logger.error("尝试获取缓存查询，但查询管理器未设置")
        return None

    def cache_query(self, cache_key: str, query: Query) -> None:
        """缓存查询"""
        if self.query_manager:
            self.query_manager.cache_query(cache_key, query)
        else:
            self.logger.error("尝试缓存查询，但查询管理器未设置")

    def invalidate_all_query_caches(self) -> None:
        """使所有查询缓存失效"""
        if self.query_manager:
            self.query_manager.invalidate_all_caches()
        else:
            self.logger.error("尝试使查询缓存失效，但查询管理器未设置")

    def clear_query_cache(self) -> None:
        """清除所有查询缓存"""
        if self.query_manager:
            self.query_manager.clear_cache()
        else:
            self.logger.error("尝试清除查询缓存，但查询管理器未设置")

    # EventManager 统一接口
    def publish(self, event: "EventMessage") -> None:
        """发送事件"""
        if self.event_manager:
            self.event_manager.publish(event)
        else:
            self.logger.warning("尝试发送事件，但事件管理器未设置")

    def subscribe(self, event_type: str, listener: Callable) -> None:
        """注册事件监听器"""
        if self.event_manager:
            self.event_manager.subscribe(event_type, listener)
        else:
            self.logger.warning("尝试注册事件监听器，但事件管理器未设置")

    def unsubscribe(self, event_type: str, listener: Callable) -> None:
        """注销事件监听器"""
        if self.event_manager:
            self.event_manager.unsubscribe(event_type, listener)
        else:
            self.logger.warning("尝试注销事件监听器，但事件管理器未设置")

    # RenderManager 统一接口
    def render(self) -> None:
        """执行渲染"""
        if self.render_manager:
            self.render_manager.render()
        else:
            self.logger.warning("尝试执行渲染，但渲染管理器未设置")

    # SceneManager 统一接口
    def load_scene(self, scene_name: str, kwargs) -> None:
        """加载场景"""
        if self.scene_manager:
            self.scene_manager.load_scene(scene_name, kwargs)
        else:
            self.logger.warning("尝试加载场景，但场景管理器未设置")

    def get_current_scene(self) -> Any:
        """获取当前场景"""
        if self.scene_manager:
            return self.scene_manager.get_current_scene()
        self.logger.warning("尝试获取当前场景，但场景管理器未设置")
        return None
