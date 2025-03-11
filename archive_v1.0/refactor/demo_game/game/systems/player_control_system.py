import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.inputs import InputManager
from game.components import Position, Velocity, Player, MapTile


class PlayerControlSystem(System):
    """玩家控制系统，处理玩家输入并控制玩家角色"""

    def __init__(self, input_manager: InputManager):
        super().__init__([Player, Position, Velocity], priority=3)
        # self.input_manager = input_manager
        self.player_speed = 150  # 玩家速度
        self.tile_size = 32  # 默认格子大小
        self.map_width = 20  # 默认地图宽度
        self.map_height = 15  # 默认地图高度

    def update(self, world: World, delta_time: float) -> None:
        # 获取地图尺寸

        # 计算地图的像素大小
        map_pixel_width = self.map_width * self.tile_size
        map_pixel_height = self.map_height * self.tile_size

        # 处理玩家输入
        keys = pygame.key.get_pressed()

        # 获取所有玩家实体
        player_entities = world.get_entities_with_components(Player, Position, Velocity)

        for entity in player_entities:
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)

            # 初始化速度为零
            new_vel_x = 0
            new_vel_y = 0

            # 根据按键更新速度
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                new_vel_x -= self.player_speed
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                new_vel_x += self.player_speed
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                new_vel_y -= self.player_speed
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                new_vel_y += self.player_speed

            # 根据对角线移动进行标准化
            if new_vel_x != 0 and new_vel_y != 0:
                # 对角线移动，标准化速度
                diagonal_factor = 0.7071  # 约等于 1/sqrt(2)
                new_vel_x *= diagonal_factor
                new_vel_y *= diagonal_factor

            # 检测是否即将离开地图边界
            entity_radius = self.tile_size / 2
            next_x = pos.x + new_vel_x * delta_time
            next_y = pos.y + new_vel_y * delta_time

            # 如果下一步会超出边界，禁止该方向移动
            if next_x < entity_radius or next_x > map_pixel_width - entity_radius:
                new_vel_x = 0
            if next_y < entity_radius or next_y > map_pixel_height - entity_radius:
                new_vel_y = 0

            # 更新实体速度
            vel.x = new_vel_x
            vel.y = new_vel_y
