from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager
from game.components import Collider


class GlowSystem(System):
    """发光效果系统，处理实体的发光效果"""

    def __init__(self, event_manager):
        super().__init__([Collider], priority=4)
        self.event_manager = event_manager
        # 删除了直接存储world引用的做法

    def setup(self, world: World):
        """系统初始化时调用，订阅相关事件"""
        self.event_manager.subscribe(
            "obstacle_collision",
            lambda message: self._handle_obstacle_collision(world, message),
        )

    def _handle_obstacle_collision(self, world, message):
        """处理障碍物碰撞事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message
        entity = event_data.get("entity")
        if entity is not None and world.has_component(entity, Collider):
            collider = world.get_component(entity, Collider)
            collider.is_glowing = True
            collider.glow_timer = 0.0

    def update(self, world: World, delta_time: float) -> None:
        # 更新发光计时器
        entities = world.get_entities_with_components(Collider)
        for entity in entities:
            collider = world.get_component(entity, Collider)
            if collider.is_glowing:
                collider.glow_timer += delta_time
                if collider.glow_timer >= 0.5:  # 发光持续0.5秒
                    collider.is_glowing = False
                    collider.glow_timer = 0.0
