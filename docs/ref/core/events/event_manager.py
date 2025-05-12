"""
事件管理器模块

实现事件发布-订阅机制，用于系统间通信
"""

from typing import Dict, List, Callable, Any, Optional, Tuple
import logging
import time
from dataclasses import dataclass, field
from .event_types import EventType


@dataclass
class Event:
    """事件数据类"""
    
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    sender: str = None


class EventSubscription:
    """事件订阅信息"""
    
    def __init__(self, handler: Callable[[Event], None], priority: int = 0):
        """
        初始化事件订阅
        
        Args:
            handler: 事件处理函数
            priority: 优先级（值越高越先执行）
        """
        self.handler = handler
        self.priority = priority


class EventManager:
    """事件管理器，实现事件发布-订阅机制"""
    
    def __init__(self):
        """初始化事件管理器"""
        # 事件类型 -> 订阅列表
        self._subscribers: Dict[EventType, List[EventSubscription]] = {}
        # 事件历史记录，用于调试
        self._event_history: List[Event] = []
        # 最大历史记录数
        self._max_history_size = 100
        # 是否记录历史
        self._record_history = True
        # 日志
        self.logger = logging.getLogger("EventManager")
        
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None], priority: int = 0) -> bool:
        """
        订阅事件
        
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
                self._subscribers[event_type].sort(key=lambda s: s.priority, reverse=True)
                return False
                
        # 添加新订阅
        subscription = EventSubscription(handler, priority)
        self._subscribers[event_type].append(subscription)
        # 按优先级排序
        self._subscribers[event_type].sort(key=lambda s: s.priority, reverse=True)
        
        return True
        
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> bool:
        """
        取消订阅事件
        
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
        
    def publish(self, event: Event) -> None:
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
                self.logger.error(f"Error handling event {event.type} by {subscription.handler}: {e}")
                
    def publish_immediate(self, event_type: EventType, data: Dict[str, Any] = None, sender: str = None) -> None:
        """
        立即发布事件，无需创建Event对象
        
        Args:
            event_type: 事件类型
            data: 事件数据
            sender: 发送者
        """
        event = Event(
            type=event_type,
            data=data or {},
            timestamp=time.time(),
            sender=sender
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
            
    def get_event_history(self, limit: int = None) -> List[Event]:
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