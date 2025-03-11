import pygame
import math
from framework.ecs.system import System
from examples.components import (
    PositionComponent,
    VelocityComponent,
    SpriteComponent,
    InputComponent,
    ColliderComponent,
    EnemyComponent,
    ObstacleComponent,
    HealthComponent,
)


class InputSystem(System):
    def __init__(self, input_manager):
        super().__init__([InputComponent, VelocityComponent])
        self.input_manager = input_manager

    def update(self, delta_time):
        for entity in self.entities:
            input_comp = entity.get_component(InputComponent)
            velocity = entity.get_component(VelocityComponent)

            # 更新输入状态 - 只使用方向键
            input_comp.up = self.input_manager.is_key_pressed(pygame.K_UP)
            input_comp.down = self.input_manager.is_key_pressed(pygame.K_DOWN)
            input_comp.left = self.input_manager.is_key_pressed(pygame.K_LEFT)
            input_comp.right = self.input_manager.is_key_pressed(pygame.K_RIGHT)

            # 根据输入更新速度
            velocity.x = 0
            velocity.y = 0

            if input_comp.up:
                velocity.y = -100
            if input_comp.down:
                velocity.y = 100
            if input_comp.left:
                velocity.x = -100
            if input_comp.right:
                velocity.x = 100


class MovementSystem(System):
    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent])

    def update(self, delta_time):
        for entity in self.entities:
            position = entity.get_component(PositionComponent)
            velocity = entity.get_component(VelocityComponent)

            position.x += velocity.x * delta_time
            position.y += velocity.y * delta_time


class RenderSystem(System):
    def __init__(self, screen, resource_manager):
        super().__init__([PositionComponent, SpriteComponent])
        self.screen = screen
        self.resource_manager = resource_manager
        self.flash_colors = [
            (255, 255, 0),  # 明亮的黄色
            (150, 255, 0),  # 黄绿色
        ]
        self.flash_index = 0
        self.flash_timer = 0
        self.flash_speed = 0.1  # 闪烁速度

    def update(self, delta_time):
        # 更新闪烁计时器
        self.flash_timer += delta_time
        if self.flash_timer >= self.flash_speed:
            self.flash_timer = 0
            self.flash_index = (self.flash_index + 1) % len(self.flash_colors)

        for entity in self.entities:
            position = entity.get_component(PositionComponent)
            sprite = entity.get_component(SpriteComponent)

            # 处理发光效果
            if sprite.is_glowing:
                sprite.glow_timer -= delta_time
                if sprite.glow_timer <= 0:
                    sprite.is_glowing = False

            image = self.resource_manager.get_image(sprite.image_name)
            if image:
                # 先渲染发光效果（如果有的话）
                if sprite.is_glowing and entity.has_component(ObstacleComponent):
                    # 创建闪烁矩形
                    current_color = self.flash_colors[self.flash_index]
                    glow_rect = pygame.Rect(
                        position.x - 3,
                        position.y - 3,
                        sprite.width + 6,
                        sprite.height + 6,
                    )
                    pygame.draw.rect(
                        self.screen, current_color, glow_rect, 3, border_radius=8
                    )

                # 然后渲染图像
                self.screen.blit(image, (position.x, position.y))
            else:
                # 如果图像不存在，绘制一个占位符矩形
                pygame.draw.rect(
                    self.screen,
                    (255, 0, 255),
                    pygame.Rect(position.x, position.y, sprite.width, sprite.height),
                )


class CollisionSystem(System):
    def __init__(self):
        super().__init__([PositionComponent, ColliderComponent])
        self.collisions = []

    def update(self, delta_time):
        # 重置所有碰撞状态
        for entity in self.entities:
            collider = entity.get_component(ColliderComponent)
            collider.is_colliding = False
            collider.colliding_entities.clear()

        # 检测碰撞
        self.collisions = []
        entities = list(self.entities)

        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                entity1 = entities[i]
                entity2 = entities[j]

                if self.check_collision(entity1, entity2):
                    self.collisions.append((entity1, entity2))

                    # 更新碰撞状态
                    collider1 = entity1.get_component(ColliderComponent)
                    collider2 = entity2.get_component(ColliderComponent)

                    collider1.is_colliding = True
                    collider2.is_colliding = True

                    collider1.colliding_entities.add(entity2)
                    collider2.colliding_entities.add(entity1)

    def check_collision(self, entity1, entity2):
        """检查两个实体之间是否发生碰撞"""
        pos1 = entity1.get_component(PositionComponent)
        col1 = entity1.get_component(ColliderComponent)

        pos2 = entity2.get_component(PositionComponent)
        col2 = entity2.get_component(ColliderComponent)

        # 使用矩形碰撞检测
        rect1 = pygame.Rect(pos1.x, pos1.y, col1.width, col1.height)
        rect2 = pygame.Rect(pos2.x, pos2.y, col2.width, col2.height)

        return rect1.colliderect(rect2)


class GlowSystem(System):
    def __init__(self):
        super().__init__([SpriteComponent, ColliderComponent])

    def update(self, delta_time):
        for entity in self.entities:
            sprite = entity.get_component(SpriteComponent)
            collider = entity.get_component(ColliderComponent)

            if collider.is_colliding and not sprite.is_glowing:
                # 只有障碍物才发光
                if entity.has_component(ObstacleComponent):
                    sprite.is_glowing = True
                    sprite.glow_timer = 1.0  # 发光持续时间改为1秒


class EnemySystem(System):
    def __init__(self, player_entity):
        super().__init__(
            [PositionComponent, VelocityComponent, EnemyComponent, ColliderComponent]
        )
        self.player_entity = player_entity

    def update(self, delta_time):
        # 确保player_entity存在且有效
        if (
            not self.player_entity
            or self.player_entity.id not in self.player_entity.world.entities
        ):
            return

        player_pos = self.player_entity.get_component(PositionComponent)
        if not player_pos:
            return

        for entity in self.entities:
            enemy_pos = entity.get_component(PositionComponent)
            enemy_vel = entity.get_component(VelocityComponent)
            enemy = entity.get_component(EnemyComponent)
            enemy_collider = entity.get_component(ColliderComponent)

            # 如果敌人正在发生碰撞，处理碰撞响应
            if enemy_collider.is_colliding:
                # 检查是否与障碍物碰撞
                for colliding_entity in enemy_collider.colliding_entities:
                    if colliding_entity.has_component(ObstacleComponent):
                        # 简单碰撞响应：停止向障碍物方向移动
                        obstacle_pos = colliding_entity.get_component(PositionComponent)

                        # 计算推力方向(从障碍物到敌人)
                        push_x = enemy_pos.x - obstacle_pos.x
                        push_y = enemy_pos.y - obstacle_pos.y

                        # 标准化并施加推力
                        length = max(1, (push_x**2 + push_y**2) ** 0.5)
                        push_x /= length
                        push_y /= length

                        # 调整位置，避免卡住
                        enemy_pos.x += push_x * 2
                        enemy_pos.y += push_y * 2

                        # 根据碰撞调整速度
                        if abs(push_x) > abs(push_y):
                            enemy_vel.x = 0
                        else:
                            enemy_vel.y = 0

            # 计算与玩家的距离
            dx = player_pos.x - enemy_pos.x
            dy = player_pos.y - enemy_pos.y
            distance = math.sqrt(dx * dx + dy * dy)

            # 简化逻辑，始终追逐玩家
            enemy.state = "chase"
            enemy.target = self.player_entity

            if enemy.state == "chase" and enemy.target:
                # 追逐玩家
                if distance > 0:
                    # 归一化方向向量
                    dx /= distance
                    dy /= distance

                    # 设置速度
                    enemy_vel.x = dx * enemy.speed
                    enemy_vel.y = dy * enemy.speed
                else:
                    enemy_vel.x = 0
                    enemy_vel.y = 0


class HealthSystem(System):
    def __init__(self):
        super().__init__([HealthComponent])

    def update(self, delta_time):
        for entity in self.entities:
            health = entity.get_component(HealthComponent)
            # 处理自动回复
            health.regenerate(delta_time)
