class EventManager:
    """事件发布/订阅系统"""

    def __init__(self):
        self.listeners = {}

    def add_listener(self, event_type, callback):
        """添加事件监听器"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def remove_listener(self, event_type, callback):
        """移除事件监听器"""
        if event_type in self.listeners and callback in self.listeners[event_type]:
            self.listeners[event_type].remove(callback)

    def dispatch(self, event_type, *args, **kwargs):
        """触发事件"""
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                callback(*args, **kwargs)
