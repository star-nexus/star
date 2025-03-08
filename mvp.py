import pygame
import random
from dataclasses import dataclass
from typing import Dict, List, Set


# ECS 基础结构
@dataclass
class Component:
    pass


class Entity:
    _id = 0

    def __init__(self):
        self.id = Entity._id
        Entity._id += 1
        self.components: Dict[type, Component] = {}


class System:
    def __init__(self):
        self.entities: Set[Entity] = set()


# 组件定义
@dataclass
class Position(Component):
    x: float
    y: float


@dataclass
class Velocity(Component):
    dx: float
    dy: float


@dataclass
class Render(Component):
    color: tuple
    size: int = 20


@dataclass
class Combat(Component):
    health: int = 100
    attack: int = 20
    ammo: int = 50


@dataclass
class AI(Component):
    target_id: int = -1


@dataclass
class Projectile(Component):
    lifespan: int = 60  # 帧数


# 系统定义
class MovementSystem(System):
    def update(self):
        for entity in self.entities:
            pos = entity.components.get(Position)
            vel = entity.components.get(Velocity)
            if pos and vel:
                pos.x += vel.dx
                pos.y += vel.dy


class AISystem(System):
    def update(self, player_entity):
        for entity in self.entities:
            ai = entity.components.get(AI)
            pos = entity.components.get(Position)
            vel = entity.components.get(Velocity)

            if ai and pos and vel:
                # 简单AI：朝玩家移动
                player_pos = player_entity.components[Position]
                dx = player_pos.x - pos.x
                dy = player_pos.y - pos.y
                distance = (dx**2 + dy**2) ** 0.5

                if distance > 0:
                    speed = 1.5
                    vel.dx = (dx / distance) * speed
                    vel.dy = (dy / distance) * speed


class CombatSystem(System):
    def update(self, entities):
        projectiles = [e for e in entities if Projectile in e.components]
        enemies = [e for e in entities if AI in e.components]

        for proj in projectiles:
            p_pos = proj.components[Position]
            for enemy in enemies:
                e_pos = enemy.components[Position]
                distance = ((p_pos.x - e_pos.x) ** 2 + (p_pos.y - e_pos.y) ** 2) ** 0.5
                if distance < 20:
                    enemy.components[Combat].health -= 10
                    proj.components[Projectile].lifespan = 0  # 销毁子弹


class RenderSystem(System):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen

    def update(self):
        self.screen.fill((30, 30, 30))  # 深灰色背景

        for entity in self.entities:
            render = entity.components.get(Render)
            pos = entity.components.get(Position)

            if render and pos:
                # 绘制实体
                pygame.draw.circle(
                    self.screen,
                    render.color,
                    (int(pos.x), int(pos.y)),
                    render.size // 2,
                )

                # 绘制健康条
                if Combat in entity.components:
                    health = entity.components[Combat].health
                    pygame.draw.rect(
                        self.screen, (255, 0, 0), (pos.x - 20, pos.y - 30, 40, 5)
                    )
                    pygame.draw.rect(
                        self.screen,
                        (0, 255, 0),
                        (pos.x - 20, pos.y - 30, 40 * (health / 100), 5),
                    )


# 初始化 Pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# 创建 ECS 实体
player = Entity()
player.components.update(
    {
        Position: Position(400, 300),
        Velocity: Velocity(0, 0),
        Render: Render((0, 120, 200)),
        Combat: Combat(),
    }
)

enemies = [Entity() for _ in range(3)]
for i, e in enumerate(enemies):
    e.components.update(
        {
            Position: Position(random.randint(100, 700), random.randint(100, 500)),
            Velocity: Velocity(0, 0),
            Render: Render((200, 50, 50), 15),
            Combat: Combat(50, 10),
            AI: AI(player.id),
        }
    )

projectiles = []

# 创建系统
movement_system = MovementSystem()
ai_system = AISystem()
combat_system = CombatSystem()
render_system = RenderSystem(screen)

# 注册实体到系统
all_entities = [player] + enemies
movement_system.entities.update(all_entities)
ai_system.entities.update(enemies)
render_system.entities.update(all_entities)

# 主循环
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # 射击控制
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if player.components[Combat].ammo > 0:
                bullet = Entity()
                pos = player.components[Position]
                bullet.components.update(
                    {
                        Position: Position(pos.x, pos.y),
                        Velocity: Velocity(0, -5),
                        Render: Render((255, 255, 0), 5),
                        Projectile: Projectile(),
                    }
                )
                projectiles.append(bullet)
                player.components[Combat].ammo -= 1

    # 玩家移动控制
    keys = pygame.key.get_pressed()
    speed = 3
    player_vel = player.components[Velocity]
    player_vel.dx = (keys[pygame.K_d] - keys[pygame.K_a]) * speed
    player_vel.dy = (keys[pygame.K_s] - keys[pygame.K_w]) * speed

    # 更新系统
    ai_system.update(player)
    movement_system.update()

    # 更新子弹
    all_entities += projectiles
    movement_system.entities.update(projectiles)
    render_system.entities.update(projectiles)

    combat_system.update(all_entities)

    # 清理被销毁的子弹
    projectiles = [p for p in projectiles if p.components[Projectile].lifespan > 0]
    for p in projectiles:
        p.components[Projectile].lifespan -= 1

    # 清理死亡的敌人
    enemies = [e for e in enemies if e.components[Combat].health > 0]

    # 渲染
    render_system.update()

    # 显示弹药和血量
    font = pygame.font.Font(None, 24)
    text = font.render(
        f"Ammo: {player.components[Combat].ammo}  Health: {player.components[Combat].health}",
        True,
        (255, 255, 255),
    )
    screen.blit(text, (10, 10))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
