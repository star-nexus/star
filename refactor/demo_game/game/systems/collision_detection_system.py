import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message
from game.components import Position, Collider, Player, Enemy


class CollisionDetectionSystem(System):
    """碰撞检测系统，只负责检测碰撞并发布碰撞事件"""

    def __init__(self, event_manager: EventManager):
        super().__init__([Position, Collider], priority=3)
        self.event_manager = event_manager

    def update(self, world: World, delta_time: float) -> None:
        # 检测碰撞
        entities = world.get_entities_with_components(Position, Collider)

        # 检查所有实体对之间的碰撞
        for i, entity1 in enumerate(entities):
            pos1 = world.get_component(entity1, Position)
            col1 = world.get_component(entity1, Collider)

            for entity2 in entities[i + 1 :]:
                pos2 = world.get_component(entity2, Position)
                col2 = world.get_component(entity2, Collider)

                # 计算距离
                dx = pos2.x - pos1.x
                dy = pos2.y - pos1.y
                distance = math.sqrt(dx * dx + dy * dy)

                # 检查碰撞
                if distance < col1.radius + col2.radius:
                    # 发布通用碰撞事件
                    collision_data = {
                        "entity1": entity1,
                        "entity2": entity2,
                        "distance": distance,
                        "normal_x": dx / distance if distance > 0 else 0,
                        "normal_y": dy / distance if distance > 0 else 0,
                        "overlap": col1.radius + col2.radius - distance,
                    }

                    self.event_manager.publish(
                        "collision_detected",
                        Message("collision_detected", "collision_data", collision_data),
                    )

                    # 检测特殊类型的碰撞
                    self._check_special_collisions(world, entity1, entity2)

    def _check_special_collisions(self, world, entity1, entity2):
        """检查特殊类型的碰撞（如玩家与敌人、实体与障碍物等）"""
        # 检查玩家与敌人的碰撞
        if (
            world.has_component(entity1, Player) and world.has_component(entity2, Enemy)
        ) or (
            world.has_component(entity1, Enemy) and world.has_component(entity2, Player)
        ):

            player_entity = entity1 if world.has_component(entity1, Player) else entity2
            enemy_entity = entity1 if world.has_component(entity1, Enemy) else entity2

            self.event_manager.publish(
                "player_enemy_collision",
                Message(
                    "player_enemy_collision",
                    "collision_event",
                    {"player_entity": player_entity, "enemy_entity": enemy_entity},
                ),
            )
