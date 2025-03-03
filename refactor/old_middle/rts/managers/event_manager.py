class EventManager:
    """
    Event manager for handling game events
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EventManager()
        return cls._instance

    def __init__(self):
        if EventManager._instance is not None:
            raise Exception("EventManager is a singleton!")

        self._listeners = {}
        EventManager._instance = self

    def add_listener(self, event_type, callback):
        """
        Register a callback for a specific event type
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []

        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def remove_listener(self, event_type, callback):
        """
        Remove a callback for a specific event type
        """
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    def emit(self, event):
        """
        Emit an event to all registered listeners
        """
        event_type = type(event)
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                callback(event)
