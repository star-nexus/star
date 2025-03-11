import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager
from game.components import Position, Velocity, Obstacle


class CollisionResponseSystem(System):
    """碰撞响应系统，处理实体间碰撞后的物理响应"""

    def __init__(self, event_manager: EventManager):
        super().__init__([], priority=3.5)  # 不需要特定组件，在碰撞检测之后执行
        self.event_manager = event_manager
        self.collision_events = []

    def setup(self, world: World):
        """系统初始化，订阅碰撞事件"""
        self.event_manager.subscribe("collision_detected", self._store_collision)

    def _store_collision(self, message):
        """存储碰撞事件，等待下一次系统更新时处理"""
        data = message.data if hasattr(message, "data") else message
        self.collision_events.append(data)

    def update(self, world: World, delta_time: float) -> None:
        """处理所有收集到的碰撞事件"""
        for collision in self.collision_events:
            entity1 = collision.get("entity1")
            entity2 = collision.get("entity2")
            normal_x = collision.get("normal_x", 0)
            normal_y = collision.get("normal_y", 0)
            overlap = collision.get("overlap", 0)

            # 处理障碍物碰撞
            self._handle_obstacle_collision(
                world, entity1, entity2, normal_x, normal_y, overlap
            )

        # 处理完所有碰撞后清空列表
        self.collision_events.clear()

    def _handle_obstacle_collision(
        self, world, entity1, entity2, normal_x, normal_y, overlap
    ):
        """处理与障碍物的碰撞"""
        has_obstacle1 = world.has_component(entity1, Obstacle)
        has_obstacle2 = world.has_component(entity2, Obstacle)

        # 如果两个实体都是障碍物，不处理碰撞
        if has_obstacle1 and has_obstacle2:
            return

        # 处理非障碍物实体与障碍物的碰撞
        if has_obstacle1 or has_obstacle2:
            # 确定哪个是障碍物，哪个是移动实体
            obstacle_entity = entity1 if has_obstacle1 else entity2
            movable_entity = entity2 if has_obstacle1 else entity1

            # 修正法线方向（必须从障碍物指向移动实体）
            if has_obstacle2:  # 如果entity2是障碍物，需要反转法线
                normal_x = -normal_x
                normal_y = -normal_y

            # 只有当实体有Position组件时才处理位置
            if world.has_component(movable_entity, Position):
                pos = world.get_component(movable_entity, Position)

                # 将实体推出障碍物
                pos.x += normal_x * overlap
                pos.y += normal_y * overlap

                # 如果实体有速度组件，处理反弹
                if world.has_component(movable_entity, Velocity):
                    vel = world.get_component(movable_entity, Velocity)

                    # 计算速度在法线方向上的分量
                    dot_product = vel.x * normal_x + vel.y * normal_y

                    # 只有当实体朝障碍物移动时才反弹
                    if dot_product < 0:
                        # 反弹计算（对法线方向的速度取反）
                        vel.x -= 2 * dot_product * normal_x
                        vel.y -= 2 * dot_product * normal_y

            # 发布障碍物碰撞事件
            self.event_manager.publish(
                "obstacle_collision", {"entity": obstacle_entity}
            )
