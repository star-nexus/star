import pygame
import random
from engine.entity import Entity
from engine.components import (
    SpriteComponent,
    MovementComponent,
    CollisionComponent,
    AnimationComponent,
)


class EntityFactory:
    """实体工厂，负责创建各种游戏实体"""

    def __init__(self, engine):
        """初始化实体工厂

        Args:
            engine: 游戏引擎实例
        """
        self.engine = engine

    def create_player(self, x=400, y=300):
        """创建玩家实体

        Args:
            x: 玩家x坐标
            y: 玩家y坐标

        Returns:
            创建的玩家实体
        """
        player = Entity(x, y, tag="player")

        # 创建玩家图像
        player_image = pygame.Surface((30, 30))
        player_image.fill((255, 0, 0))

        # 创建玩家动画帧
        player_frames = []
        for color in [(255, 0, 0), (255, 100, 100), (255, 50, 50), (255, 150, 150)]:
            frame = pygame.Surface((30, 30))
            frame.fill(color)
            player_frames.append(frame)

        # 添加组件到玩家
        sprite_component = SpriteComponent(player, player_image)
        player.add_component("sprite", sprite_component)
        player.add_component("movement", MovementComponent(player, 200))
        player.add_component("collision", CollisionComponent(player, 30, 30))

        # 添加动画组件
        anim_component = AnimationComponent(player, sprite_component)
        anim_component.add_animation("idle", player_frames)
        player.add_component("animation", anim_component)

        return player

    def create_enemy(self, x=None, y=None, min_distance=300, max_distance=1200):
        """创建敌人实体

        Args:
            x: 敌人x坐标，如果为None则随机生成
            y: 敌人y坐标，如果为None则随机生成
            min_distance: 距离玩家的最小距离
            max_distance: 距离玩家的最大距离

        Returns:
            创建的敌人实体
        """
        # 如果没有指定坐标，生成在范围内的随机坐标
        if x is None:
            x = random.randint(min_distance, max_distance)
        if y is None:
            y = random.randint(min_distance, max_distance)

        enemy = Entity(x, y, tag="enemy")

        # 创建敌人图像
        enemy_image = pygame.Surface((30, 30))
        enemy_image.fill((0, 0, 255))

        # 添加组件
        enemy.add_component("sprite", SpriteComponent(enemy, enemy_image))
        enemy.add_component("movement", MovementComponent(enemy, 100))
        enemy.add_component("collision", CollisionComponent(enemy, 30, 30))

        return enemy
