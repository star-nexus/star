import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from game.components import Position, Velocity, Enemy, Player, MapTile


class EnemyAISystem(System):
    """敌人AI系统，控制敌人的行为"""

    def __init__(self):
        super().__init__([Position, Velocity, Enemy], priority=3)
        self.tile_size = 32  # 与地图系统使用相同的格子大小
        self.map_width = 20  # 默认地图宽度
        self.map_height = 15  # 默认地图高度

    def update(self, world: World, delta_time: float) -> None:

        # 计算地图像素尺寸
        map_pixel_width = self.map_width * self.tile_size
        map_pixel_height = self.map_height * self.tile_size

        # 获取玩家位置
        player_entities = world.get_entities_with_components(Player, Position)
        if not player_entities:
            return  # 如果没有找到玩家，什么都不做

        player_entity = player_entities[0]  # 假设只有一个玩家
        player_pos = world.get_component(player_entity, Position)

        # 对每个敌人实体应用AI
        enemy_entities = world.get_entities_with_components(Enemy, Position, Velocity)

        for entity in enemy_entities:
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)
            enemy = world.get_component(entity, Enemy)

            # 根据敌人状态更新行为
            if enemy.state == "idle":
                # 有一定概率开始移动
                if random.random() < 0.02:  # 每一帧有2%概率改变状态
                    # 在地图范围内选择一个随机目标点
                    entity_radius = self.tile_size / 2  # 假设实体半径
                    target_x = random.uniform(
                        entity_radius, map_pixel_width - entity_radius
                    )
                    target_y = random.uniform(
                        entity_radius, map_pixel_height - entity_radius
                    )

                    # 设置新的目标和状态
                    enemy.target_x = target_x
                    enemy.target_y = target_y
                    enemy.state = "moving"

                    # 计算移动方向
                    dx = target_x - pos.x
                    dy = target_y - pos.y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance > 0:
                        # 设置速度 (normalized * speed)
                        speed = enemy.speed
                        vel.x = dx / distance * speed
                        vel.y = dy / distance * speed

            elif enemy.state == "moving":
                # 计算与目标的距离
                dx = enemy.target_x - pos.x
                dy = enemy.target_y - pos.y
                distance = math.sqrt(dx * dx + dy * dy)

                # 如果已经非常接近目标，就进入闲置状态
                if distance < 5.0:  # 足够接近目标
                    enemy.state = "idle"
                    vel.x = 0
                    vel.y = 0
                else:
                    # 继续朝目标移动
                    speed = enemy.speed
                    vel.x = dx / distance * speed
                    vel.y = dy / distance * speed

                # 检测是否即将离开地图边界，防止AI控制单位离开地图
                entity_radius = self.tile_size / 2
                next_x = pos.x + vel.x * delta_time
                next_y = pos.y + vel.y * delta_time

                # 如果下一步会超出地图边界，重新选择目标
                if (
                    next_x < entity_radius
                    or next_x > map_pixel_width - entity_radius
                    or next_y < entity_radius
                    or next_y > map_pixel_height - entity_radius
                ):

                    # 重置目标到地图内部安全位置
                    enemy.target_x = random.uniform(
                        entity_radius * 2, map_pixel_width - entity_radius * 2
                    )
                    enemy.target_y = random.uniform(
                        entity_radius * 2, map_pixel_height - entity_radius * 2
                    )

                    # 重新计算移动方向
                    dx = enemy.target_x - pos.x
                    dy = enemy.target_y - pos.y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance > 0:
                        speed = enemy.speed
                        vel.x = dx / distance * speed
                        vel.y = dy / distance * speed

            # 敌人检测玩家位置并追逐
            if random.random() < 0.01:  # 每一帧有1%的概率检测玩家
                # 计算与玩家的距离
                dx = player_pos.x - pos.x
                dy = player_pos.y - pos.y
                distance_to_player = math.sqrt(dx * dx + dy * dy)

                # 如果玩家在可感知范围内，敌人会追逐
                perception_range = 200  # 敌人感知范围
                if distance_to_player < perception_range:
                    enemy.state = "chasing"
                    enemy.target_x = player_pos.x
                    enemy.target_y = player_pos.y

                    # 计算追逐速度，可以略快于平时移动
                    chase_speed = enemy.speed * 1.2  # 追逐速度比正常快20%
                    vel.x = dx / distance_to_player * chase_speed
                    vel.y = dy / distance_to_player * chase_speed
