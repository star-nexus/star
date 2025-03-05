import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message
from game.components import Position, Collider, Obstacle, Player, Enemy, Velocity


class CollisionSystem(System):
    """碰撞检测系统，只负责检测碰撞并处理碰撞事件"""

    def __init__(self, event_manager: EventManager):
        super().__init__([Position, Collider], priority=4)
        self.event_manager = event_manager

    def update(self, world: World, delta_time: float) -> None:
        # 检测碰撞
        entities = world.get_entities_with_components(Position, Collider)

        # 检查所有实体对之间的碰撞
        for i, entity1 in enumerate(entities):

            pos1 = world.get_component(entity1, Position)
            col1 = world.get_component(entity1, Collider)
            if not pos1 or not col1:
                print(f"{entity1} missing Position or Collider component")
                continue

            for entity2 in entities[i + 1 :]:

                pos2 = world.get_component(entity2, Position)
                col2 = world.get_component(entity2, Collider)
                if not pos2 or not col2:
                    print(f"{entity2} missing Position or Collider component")
                    continue

                # 计算距离
                dx = pos2.x - pos1.x
                dy = pos2.y - pos1.y
                distance = math.sqrt(dx * dx + dy * dy)

                # 检查碰撞
                if distance < col1.radius + col2.radius:
                    # 处理障碍物碰撞
                    if world.has_component(entity1, Obstacle) or world.has_component(
                        entity2, Obstacle
                    ):
                        # 计算碰撞反弹
                        overlap = (col1.radius + col2.radius - distance) / 2
                        if overlap > 0:
                            # 计算碰撞法线
                            nx = dx / distance
                            ny = dy / distance

                            # 分开两个物体
                            if not world.has_component(entity1, Obstacle):
                                pos1.x -= overlap * nx
                                pos1.y -= overlap * ny
                                # 如果有速度组件，反弹
                                if world.has_component(entity1, Velocity):
                                    vel1 = world.get_component(entity1, Velocity)
                                    vel1.x = -vel1.x
                                    vel1.y = -vel1.y

                            if not world.has_component(entity2, Obstacle):
                                pos2.x += overlap * nx
                                pos2.y += overlap * ny
                                # 如果有速度组件，反弹
                                if world.has_component(entity2, Velocity):
                                    vel2 = world.get_component(entity2, Velocity)
                                    vel2.x = -vel2.x
                                    vel2.y = -vel2.y

                            if world.has_component(entity1, Obstacle):
                                self.event_manager.publish(
                                    "obstacle_collision", {"entity": entity1}
                                )
                            if world.has_component(entity2, Obstacle):
                                self.event_manager.publish(
                                    "obstacle_collision", {"entity": entity2}
                                )

                    # 检测玩家和敌人碰撞，发布碰撞事件，并附加更多信息
                    if (
                        world.has_component(entity1, Player)
                        and world.has_component(entity2, Enemy)
                    ) or (
                        world.has_component(entity1, Enemy)
                        and world.has_component(entity2, Player)
                    ):
                        # 获取玩家和敌人实体
                        player_entity = (
                            entity1 if world.has_component(entity1, Player) else entity2
                        )
                        enemy_entity = (
                            entity1 if world.has_component(entity1, Enemy) else entity2
                        )

                        player_vel = world.get_component(player_entity, Velocity)
                        player_speed = math.sqrt(player_vel.x**2 + player_vel.y**2)

                        # 发布玩家与敌人碰撞事件
                        self.event_manager.publish(
                            "player_enemy_collision",
                            Message(
                                topic="player_enemy_collision",
                                data_type="collision_event",
                                data={
                                    "player_entity": player_entity,
                                    "enemy_entity": enemy_entity,
                                    "player_speed": player_speed,
                                },
                            ),
                        )
