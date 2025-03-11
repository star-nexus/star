import os
import pygame
import random
import math
from examples.components import (
    PositionComponent,
    VelocityComponent,
    SpriteComponent,
    InputComponent,
    ColliderComponent,
    ObstacleComponent,
    EnemyComponent,
    HealthComponent,
)


class EntityFactory:
    """
    负责创建游戏中各种实体（玩家、障碍物、敌人）的工厂类
    """

    def __init__(self, game, world):
        self.game = game
        self.world = world

    def create_player(self, x=400, y=300):
        """创建玩家实体"""
        player = self.world.create_entity()

        # 加载玩家图像
        player_image = "player"
        try:
            assets_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
            image_path = os.path.join(assets_path, "player.png")
            self.game.resources.load_image(player_image, image_path)
        except:
            img = pygame.Surface((32, 32))
            img.fill((0, 255, 0))
            self.game.resources.images[player_image] = img

        # 添加组件
        player.add_component(PositionComponent(x, y))
        player.add_component(VelocityComponent())
        player.add_component(SpriteComponent(player_image))
        player.add_component(InputComponent())
        player.add_component(ColliderComponent(32, 32))
        # 健康组件，玩家有100点生命值，每秒回复2点
        player.add_component(HealthComponent(max_health=100, regeneration_rate=2))

        return player

    def create_obstacles(self, count=5):
        """创建多个障碍物"""
        obstacles = []

        # 加载障碍物图像
        obstacle_image = "obstacle"
        try:
            assets_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
            image_path = os.path.join(assets_path, "obstacle.png")
            self.game.resources.load_image(obstacle_image, image_path)
        except:
            img = pygame.Surface((40, 40))
            img.fill((200, 100, 50))
            self.game.resources.images[obstacle_image] = img

        # 创建多个障碍物
        for i in range(count):
            # 随机位置，确保不在玩家附近
            while True:
                x = random.randint(50, self.game.width - 50)
                y = random.randint(50, self.game.height - 50)

                # 确保与玩家距离足够远
                dx = x - 400  # 玩家初始x位置
                dy = y - 300  # 玩家初始y位置
                distance = math.sqrt(dx * dx + dy * dy)

                if distance > 100:
                    break

            obstacle = self.world.create_entity()
            obstacle.add_component(PositionComponent(x, y))
            obstacle.add_component(SpriteComponent(obstacle_image))
            obstacle.add_component(ColliderComponent(40, 40, False))  # 实体碰撞体
            obstacle.add_component(ObstacleComponent())

            obstacles.append(obstacle)

        return obstacles

    def create_enemy(self, game_width, game_height):
        """创建敌人"""
        enemy = self.world.create_entity()

        # 加载敌人图像
        enemy_image = "enemy"
        try:
            assets_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
            image_path = os.path.join(assets_path, "enemy.png")
            self.game.resources.load_image(enemy_image, image_path)
        except:
            img = pygame.Surface((30, 30))
            img.fill((255, 0, 0))
            self.game.resources.images[enemy_image] = img

        # 随机位置，确保在屏幕边缘
        edge = random.choice(["top", "right", "bottom", "left"])
        if edge == "top":
            x = random.randint(0, game_width)
            y = -30
        elif edge == "right":
            x = game_width + 30
            y = random.randint(0, game_height)
        elif edge == "bottom":
            x = random.randint(0, game_width)
            y = game_height + 30
        else:  # left
            x = -30
            y = random.randint(0, game_height)

        # 添加组件
        enemy.add_component(PositionComponent(x, y))
        enemy.add_component(VelocityComponent())
        enemy.add_component(SpriteComponent(enemy_image))
        enemy.add_component(ColliderComponent(30, 30))
        enemy.add_component(EnemyComponent(speed=100, detection_radius=800))
        # 健康组件，敌人有40点生命值，不会自动回复
        enemy.add_component(HealthComponent(max_health=40, regeneration_rate=0))

        return enemy
