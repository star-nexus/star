from framework.ecs import System
from framework.engine.events import EventMessage


class HumanControlSystem(System):
    def __init__(self, priority: int = 25):
        super().__init__(required_components=[], priority=priority)
        pass

    def initialize(self, context):
        self.context = context

    def subscribe_events(self):
        pass

    def handle_event(self, event: EventMessage):
        pass
