class EventManager:
    """事件管理器，负责处理游戏中的各种事件"""
    
    def __init__(self):
        """初始化事件管理器"""
        self._bus = {}
    
    def subscribe(self, topic: str, subscriber) -> None:
        """添加主题监听器
        
        Args:
            topic: 主题类型
            subscriber: 订阅者函数
        """
        if topic not in self._bus:
            self._bus[topic] = set()
        self._bus[topic].add(subscriber)
    
    def unsubscribe(self, topic: str, subscriber) -> None:
        """移除主题监听器
        
        Args:
            topic: 主题类型
            subscriber: 订阅者函数
        """
        if topic in self._bus:
            self._bus[topic].discard(subscriber)
    
    def publish(self, topic: str, message=None) -> None:
        """发布事件
        
        Args:
            topic: 主题类型
            message: 消息
        """
        if topic in self._bus:
            for subscriber in self._bus[topic]:
                subscriber(message)