"""
事件管理器模块

实现事件发布-订阅机制，用于系统间通信
"""

from typing import Dict, List, Callable, Any, Optional
from enum import Enum, auto
import logging
import time
from dataclasses import dataclass, field

"""
事件类型定义

定义系统间通信使用的标准事件类型
"""


class EventType(Enum):
    """事件类型枚举"""

    # 外设输入
    KEY_DOWN = auto()
    KEY_UP = auto()
    MOUSEBUTTON_DOWN = auto()
    MOUSEBUTTON_UP = auto()
    MOUSE_MOTION = auto()
    MOUSE_WHEEL = auto()

    # 系统事件
    SYSTEM_INITIALIZED = auto()
    SYSTEM_SHUTDOWN = auto()

    # 实体事件
    ENTITY_CREATED = auto()
    ENTITY_DESTROYED = auto()
    COMPONENT_ADDED = auto()
    COMPONENT_REMOVED = auto()
    COMPONENT_CHANGED = auto()

    # 游戏事件
    GAME_STARTED = auto()
    GAME_PAUSED = auto()
    GAME_RESUMED = auto()
    GAME_ENDED = auto()
    TURN_STARTED = auto()
    TURN_ENDED = auto()

    # 战争迷雾事件
    FOG_OF_WAR_TOGGLED = auto()
    PLAYER_SWITCHED = auto()

    # 战斗事件
    ATTACK = auto()
    COMBAT_STARTED = auto()
    COMBAT_ENDED = auto()
    COMBAT_HIT = auto()
    COMBAT_MISS = auto()
    UNIT_ATTACKED = auto()
    UNIT_DAMAGED = auto()
    UNIT_KILLED = auto()
    UNIT_ROUTED = auto()
    UNIT_RALLIED = auto()

    # 移动事件
    UNIT_MOVED = auto()
    UNIT_MOVE_STARTED = auto()
    UNIT_MOVE_ENDED = auto()
    UNIT_PATH_BLOCKED = auto()
    UNIT_DIED = auto()

    # 单位状态事件
    UNIT_CREATED = auto()
    UNIT_DESTROYED = auto()
    UNIT_STATE_CHANGED = auto()

    # 交互事件
    UNIT_SELECTED = auto()
    UNIT_DESELECTED = auto()
    SELECTION_BOX_RENDERING = auto()
    SELECTION_BOX_CANCELED = auto()
    SELECTION_BOX_COMPLETED = auto()
    TILE_SELECTED = auto()
    TILE_DESELECTED = auto()

    # 指令事件
    COMMAND_ISSUED = auto()
    COMMAND_COMPLETED = auto()
    COMMAND_FAILED = auto()

    # 资源事件
    RESOURCE_CHANGED = auto()
    SUPPLY_CHANGED = auto()
    MORALE_CHANGED = auto()

    # 天气和环境事件
    WEATHER_CHANGED = auto()
    TIME_OF_DAY_CHANGED = auto()
    SEASON_CHANGED = auto()

    # 特殊事件
    OFFICER_CAPTURED = auto()
    OFFICER_DEFECTED = auto()
    CITY_CAPTURED = auto()
    FACTION_DESTROYED = auto()

    # 地图
    MAP_CREATED = auto()

    # 战争迷雾
    # FOG_OF_WAR_UPDATED = auto()
    FOG_OF_WAR_OPENED = auto()
    FOG_OF_WAR_CLOSED = auto()

    # 自定义事件类型
    CUSTOM = auto()

    # 退出
    QUIT = auto()

    @classmethod
    def get_name(cls, event_type):
        """获取事件类型的名称字符串"""
        return event_type.name


@dataclass
class EventMessage:
    """事件数据类"""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    sender: str = None


class EventSubscription:
    """事件订阅信息"""

    def __init__(self, handler: Callable[[EventMessage], None], priority: int = 0):
        """
        初始化事件订阅

        Args:
            handler: 事件处理函数
            priority: 优先级（值越高越先执行）
        """
        self.handler = handler
        self.priority = priority


class EventManager:
    """事件管理器，实现事件发布-订阅机制（单例模式）"""

    # 单例实例
    _instance = None

    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(EventManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化事件管理器"""
        # 避免重复初始化
        if self._initialized:
            return

        # 事件类型 -> 订阅列表
        self._subscribers: Dict[EventType, List[EventSubscription]] = {}
        # 事件历史记录，用于调试
        self._event_history: List[EventMessage] = []
        # 最大历史记录数
        self._max_history_size = 100
        # 是否记录历史
        self._record_history = True
        # 日志
        self.logger = logging.getLogger("EventManager")
        # 标记为已初始化
        self._initialized = True

    def subscribe(
        self,
        event_type: EventType | List[EventType],
        handler: Callable[[EventMessage], None],
        priority: int = 0,
    ) -> bool:
        """
        订阅事件，支持订阅单个事件类型或多个事件类型

        Args:
            event_type: 单个事件类型或事件类型列表
            handler: 事件处理函数
            priority: 处理优先级（值越高越先执行）

        Returns:
            bool: 是否成功订阅（至少有一个事件类型成功订阅）
        """
        # 处理多个事件类型的情况
        if isinstance(event_type, list):
            success = False
            for et in event_type:
                if self._subscribe_single(et, handler, priority):
                    success = True
            return success
        else:
            # 处理单个事件类型的情况
            return self._subscribe_single(event_type, handler, priority)

    def _subscribe_single(
        self,
        event_type: EventType,
        handler: Callable[[EventMessage], None],
        priority: int = 0,
    ) -> bool:
        """
        订阅单个事件类型（内部方法）

        Args:
            event_type: 事件类型
            handler: 事件处理函数
            priority: 处理优先级（值越高越先执行）

        Returns:
            bool: 是否成功订阅
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        # 检查是否已经订阅
        for subscription in self._subscribers[event_type]:
            if subscription.handler == handler:
                # 已经订阅，更新优先级
                subscription.priority = priority
                # 重新排序
                self._subscribers[event_type].sort(
                    key=lambda s: s.priority, reverse=True
                )
                return False

        # 添加新订阅
        subscription = EventSubscription(handler, priority)
        self._subscribers[event_type].append(subscription)
        # 按优先级排序
        self._subscribers[event_type].sort(key=lambda s: s.priority, reverse=True)

        return True

    def unsubscribe(
        self,
        event_type: EventType | List[EventType],
        handler: Callable[[EventMessage], None],
    ) -> bool:
        """
        取消订阅事件，支持取消订阅单个事件类型或多个事件类型

        Args:
            event_type: 单个事件类型或事件类型列表
            handler: 事件处理函数

        Returns:
            bool: 是否成功取消订阅（至少有一个事件类型成功取消订阅）
        """
        # 处理多个事件类型的情况
        if isinstance(event_type, list):
            success = False
            for et in event_type:
                if self._unsubscribe_single(et, handler):
                    success = True
            return success
        else:
            # 处理单个事件类型的情况
            return self._unsubscribe_single(event_type, handler)

    def _unsubscribe_single(
        self, event_type: EventType, handler: Callable[[EventMessage], None]
    ) -> bool:
        """
        取消订阅单个事件类型（内部方法）

        Args:
            event_type: 事件类型
            handler: 事件处理函数

        Returns:
            bool: 是否成功取消订阅
        """
        if event_type not in self._subscribers:
            return False

        # 查找并移除订阅
        for i, subscription in enumerate(self._subscribers[event_type]):
            if subscription.handler == handler:
                self._subscribers[event_type].pop(i)
                return True

        return False

    def publish(self, event: EventMessage) -> None:
        """
        发布事件

        Args:
            event: 事件对象
        """
        # 记录历史
        if self._record_history:
            self._event_history.append(event)
            # 限制历史记录大小
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)

        # 如果没有订阅者，直接返回
        if event.type not in self._subscribers or not self._subscribers[event.type]:
            return

        # 调用所有订阅者的处理函数
        for subscription in self._subscribers[event.type]:
            try:
                subscription.handler(event)
            except Exception as e:
                self.logger.error(
                    f"Error handling event {event.type} by {subscription.handler}: {e}"
                )

    def publish_immediate(
        self, event_type: EventType, data: Dict[str, Any] = None, sender: str = None
    ) -> None:
        """
        立即发布事件，无需创建Event对象

        Args:
            event_type: 事件类型
            data: 事件数据
            sender: 发送者
        """
        event = EventMessage(
            type=event_type, data=data or {}, timestamp=time.time(), sender=sender
        )

        self.publish(event)

    def clear_subscribers(self, event_type: Optional[EventType] = None) -> None:
        """
        清除指定事件类型的所有订阅者，如果event_type为None则清除所有订阅者

        Args:
            event_type: 事件类型，为None则清除所有
        """
        if event_type is None:
            self._subscribers.clear()
        elif event_type in self._subscribers:
            self._subscribers[event_type].clear()

    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        """
        获取指定事件类型的订阅者数量，如果event_type为None则返回所有订阅者数量

        Args:
            event_type: 事件类型，为None则返回所有

        Returns:
            int: 订阅者数量
        """
        if event_type is None:
            # 计算所有订阅者数量
            return sum(len(subscribers) for subscribers in self._subscribers.values())
        elif event_type in self._subscribers:
            return len(self._subscribers[event_type])
        else:
            return 0

    def get_event_history(self, limit: int = None) -> List[EventMessage]:
        """
        获取事件历史记录

        Args:
            limit: 最大返回数量，为None则返回全部

        Returns:
            List[Event]: 事件历史记录
        """
        if limit is None or limit >= len(self._event_history):
            return self._event_history.copy()
        else:
            return self._event_history[-limit:]

    def set_history_size(self, size: int) -> None:
        """
        设置历史记录大小

        Args:
            size: 最大历史记录数量
        """
        self._max_history_size = max(1, size)
        # 如果当前历史记录超过新大小，裁剪
        while len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)

    def enable_history(self, enable: bool = True) -> None:
        """
        启用或禁用历史记录

        Args:
            enable: 是否启用
        """
        self._record_history = enable

    def clear_history(self) -> None:
        """清除历史记录"""
        self._event_history.clear()

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
