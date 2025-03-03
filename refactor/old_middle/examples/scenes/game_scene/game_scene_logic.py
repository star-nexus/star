import pygame
from examples.components import (
    PositionComponent,
    VelocityComponent,
    ColliderComponent,
    ObstacleComponent,
    HealthComponent,
)


class GameSceneLogic:
    """
    处理游戏核心逻辑，如碰撞检测、胜利/失败条件等
    """

    def __init__(self, game, collision_system):
        self.game = game
        self.collision_system = collision_system
        self.enemies = []
        self.obstacles = []
        self.player = None
        self.score = 0
        self.game_state = "playing"  # playing, won, lost

    def check_collisions(self):
        """检查碰撞并处理游戏逻辑"""
        if not self.player or not self.collision_system:
            return

        player_collider = self.player.get_component(ColliderComponent)
        player_health = self.player.get_component(HealthComponent)
        player_position = self.player.get_component(PositionComponent)
        player_velocity = self.player.get_component(VelocityComponent)

        if not player_collider or not player_health:
            return

        # 检查玩家与障碍物的碰撞 - 障碍物阻挡玩家移动
        for obstacle in self.obstacles:
            if obstacle in player_collider.colliding_entities:
                # 障碍物会发光，且阻挡玩家移动
                obstacle_pos = obstacle.get_component(PositionComponent)
                obstacle_collider = obstacle.get_component(ColliderComponent)

                # 简单的碰撞后退处理
                dx = player_position.x - obstacle_pos.x
                dy = player_position.y - obstacle_pos.y

                # 确定碰撞方向并调整位置
                if abs(dx) > abs(dy):  # 主要是水平碰撞
                    if dx > 0:  # 玩家在障碍物右边
                        player_position.x = obstacle_pos.x + obstacle_collider.width + 1
                    else:  # 玩家在障碍物左边
                        player_position.x = obstacle_pos.x - player_collider.width - 1
                    player_velocity.x = 0  # 停止水平移动
                else:  # 主要是垂直碰撞
                    if dy > 0:  # 玩家在障碍物下方
                        player_position.y = (
                            obstacle_pos.y + obstacle_collider.height + 1
                        )
                    else:  # 玩家在障碍物上方
                        player_position.y = obstacle_pos.y - player_collider.height - 1
                    player_velocity.y = 0  # 停止垂直移动

        # 检查玩家与敌人的碰撞
        for enemy in list(self.enemies):  # 使用列表副本遍历，因为可能会删除元素
            if enemy in player_collider.colliding_entities:
                enemy_health = enemy.get_component(HealthComponent)
                if enemy_health:
                    # 玩家碰到敌人，减少敌人血量
                    damage_to_enemy = 20  # 玩家对敌人的伤害量
                    is_dead = enemy_health.take_damage(damage_to_enemy)

                    # 玩家也会受到伤害，但更少
                    damage_to_player = 10  # 敌人对玩家的伤害量
                    player_dead = player_health.take_damage(damage_to_player)

                    if player_dead:
                        # 玩家死亡，游戏结束
                        return "game_over"

                    if is_dead:
                        # 敌人死亡，移除敌人并加分
                        self.enemies.remove(enemy)
                        self.game.world.destroy_entity(enemy.id)
                        self.score += 100  # 干掉一个敌人加100分

        return None  # 继续游戏

    def check_out_of_bounds(self, game_width, game_height):
        """检查玩家是否超出边界"""
        if not self.player:
            return False

        position = self.player.get_component(PositionComponent)
        if position:
            if (
                position.x < -50
                or position.x > game_width + 50
                or position.y < -50
                or position.y > game_height + 50
            ):
                return True

        return False
