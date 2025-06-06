"""
简单游戏示例 - 使用Framework V2
展示如何构建一个基本的游戏原型
"""

import sys

sys.path.append(".")
import time
import random
from dataclasses import dataclass

from framework_v2 import World, System, EntityBuilder
from examples.data_components import Position, Velocity, Health, Name
from framework_v2.engine.events import EventBus, event_bus, Event


@dataclass
class EntityDestroyedEvent(Event):
    """实体销毁事件"""

    entity_id: int


# 自定义组件
@dataclass
class Player:
    """玩家标记组件"""

    score: int = 0


@dataclass
class Enemy:
    """敌人标记组件"""

    damage: float = 10.0


@dataclass
class Bullet:
    """子弹组件"""

    damage: float = 25.0
    lifetime: float = 3.0  # 3秒后消失


# 自定义事件
@dataclass
class CollisionEvent(Event):
    """碰撞事件"""

    entity1: int
    entity2: int


@dataclass
class ScoreEvent(Event):
    """得分事件"""

    points: int


# 游戏系统
class PlayerControlSystem(System):
    """玩家控制系统（简化版）"""

    def update(self, delta_time: float) -> None:
        # 简单的自动控制逻辑
        for entity in self.world.query(Player, Position, Velocity):
            pos = self.world.get_component(entity, Position)
            vel = self.world.get_component(entity, Velocity)

            # 简单的边界检查
            if pos.x < 0 or pos.x > 100:
                vel.x *= -1
            if pos.y < 0 or pos.y > 100:
                vel.y *= -1


class EnemySpawnSystem(System):
    """敌人生成系统"""

    def __init__(self):
        super().__init__()
        self.spawn_timer = 0.0
        self.spawn_interval = 2.0  # 每2秒生成一个敌人

    def update(self, delta_time: float) -> None:
        self.spawn_timer += delta_time

        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0.0
            self._spawn_enemy()

    def _spawn_enemy(self):
        """生成敌人"""
        x = random.uniform(0, 100)
        y = random.uniform(0, 100)

        EntityBuilder(self.world).with_components(
            Position(x, y, 0),
            Velocity(random.uniform(-10, 10), random.uniform(-10, 10), 0),
            Health(50, 50),
            Enemy(damage=random.uniform(5, 15)),
            Name(f"敌人{random.randint(1000, 9999)}"),
        ).build()


class BulletSystem(System):
    """子弹系统"""

    def update(self, delta_time: float) -> None:
        to_destroy = []

        for entity in self.world.query(Bullet):
            bullet = self.world.get_component(entity, Bullet)
            bullet.lifetime -= delta_time

            if bullet.lifetime <= 0:
                to_destroy.append(entity)

        # 销毁过期的子弹
        for entity in to_destroy:
            self.world.destroy_entity(entity)


class CollisionSystem(System):
    """碰撞检测系统"""

    def update(self, delta_time: float) -> None:
        # 获取所有有位置的实体
        entities_with_pos = list(self.world.query(Position).with_components())

        # 简单的碰撞检测
        for i, (entity1, pos1) in enumerate(entities_with_pos):
            for entity2, pos2 in entities_with_pos[i + 1 :]:
                distance = ((pos1.x - pos2.x) ** 2 + (pos1.y - pos2.y) ** 2) ** 0.5

                if distance < 3.0:  # 碰撞距离
                    # 发布碰撞事件
                    EventBus().publish(CollisionEvent(entity1, entity2))


class CombatSystem(System):
    """战斗系统"""

    def __init__(self):
        super().__init__()
        # 订阅碰撞事件
        EventBus().subscribe(CollisionEvent, self._on_collision)

    def _on_collision(self, event: CollisionEvent):
        """处理碰撞事件"""
        entity1, entity2 = event.entity1, event.entity2

        # 检查子弹与敌人的碰撞
        bullet_entity = None
        enemy_entity = None

        if self.world.has_component(entity1, Bullet) and self.world.has_component(
            entity2, Enemy
        ):
            bullet_entity, enemy_entity = entity1, entity2
        elif self.world.has_component(entity2, Bullet) and self.world.has_component(
            entity1, Enemy
        ):
            bullet_entity, enemy_entity = entity2, entity1

        if bullet_entity and enemy_entity:
            self._handle_bullet_enemy_collision(bullet_entity, enemy_entity)

    def _handle_bullet_enemy_collision(self, bullet_entity: int, enemy_entity: int):
        """处理子弹与敌人的碰撞"""
        bullet = self.world.get_component(bullet_entity, Bullet)
        enemy_health = self.world.get_component(enemy_entity, Health)

        if bullet and enemy_health:
            # 造成伤害
            enemy_health.current -= bullet.damage

            # 销毁子弹
            self.world.destroy_entity(bullet_entity)

            # 检查敌人是否死亡
            if enemy_health.current <= 0:
                # 发布得分事件
                EventBus().publish(ScoreEvent(10))
                self.world.destroy_entity(enemy_entity)

    def update(self, delta_time: float) -> None:
        pass  # 主要逻辑在事件处理中


class ScoreSystem(System):
    """得分系统"""

    def __init__(self):
        super().__init__()
        EventBus().subscribe(ScoreEvent, self._on_score)
        EventBus().subscribe(EntityDestroyedEvent, self._on_entity_destroyed)

    def _on_score(self, event: ScoreEvent):
        """处理得分事件"""
        # 给玩家加分
        for entity in self.world.query(Player):
            player = self.world.get_component(entity, Player)
            if player:
                player.score += event.points
                print(f"💰 得分 +{event.points}! 总分: {player.score}")

    def _on_entity_destroyed(self, event: EntityDestroyedEvent):
        """实体销毁时的处理"""
        pass

    def update(self, delta_time: float) -> None:
        pass


def create_player(world):
    """创建玩家"""
    return (
        EntityBuilder(world)
        .with_components(
            Position(50, 50, 0),
            Velocity(5, 3, 0),
            Health(100, 100),
            Player(score=0),
            Name("玩家"),
        )
        .build()
    )


def create_bullet(world, x: float, y: float, vel_x: float, vel_y: float):
    """创建子弹"""
    return (
        EntityBuilder(world)
        .with_components(
            Position(x, y, 0),
            Velocity(vel_x, vel_y, 0),
            Bullet(damage=25.0, lifetime=3.0),
            Name("子弹"),
        )
        .build()
    )


def main():
    print("=== 简单游戏示例 ===")

    # 初始化
    world = World()
    world.reset()
    EventBus().clear()

    # 创建玩家
    player = create_player(world)
    print("✓ 玩家创建完成")

    # 创建一些初始子弹
    for i in range(3):
        create_bullet(
            world,
            random.uniform(20, 80),
            random.uniform(20, 80),
            random.uniform(-20, 20),
            random.uniform(-20, 20),
        )
    print("✓ 初始子弹创建完成")

    world.add_system(MovementSystem(priority=1))
    world.add_system(PlayerControlSystem(priority=2))
    world.add_system(EnemySpawnSystem())
    world.add_system(BulletSystem())
    world.add_system(CollisionSystem())
    world.add_system(CombatSystem())
    world.add_system(ScoreSystem())

    print("✓ 游戏系统初始化完成")

    # 游戏主循环
    print("\n🎮 游戏开始! (运行10秒)")
    start_time = time.time()
    frame_time = 1.0 / 60.0  # 60 FPS

    frame_count = 0
    while time.time() - start_time < 10.0:
        # 更新游戏
        world.update(frame_time)

        # 每隔一段时间显示状态
        frame_count += 1
        if frame_count % 120 == 0:  # 每2秒
            print(f"\n--- 游戏状态 (第{frame_count//60}秒) ---")

            # 显示实体统计
            enemies = len(world.query(Enemy).entities())
            bullets = len(world.query(Bullet).entities())
            print(f"敌人数量: {enemies}, 子弹数量: {bullets}")

            # 显示玩家状态
            player_comp = world.get_component(player, Player)
            player_health = world.get_component(player, Health)
            if player_comp and player_health:
                print(
                    f"玩家得分: {player_comp.score}, 生命值: {player_health.current:.1f}"
                )

        # 控制帧率
        time.sleep(frame_time)

    print(f"\n🎯 游戏结束!")

    # 最终统计
    player_comp = world.get_component(player, Player)
    if player_comp:
        print(f"最终得分: {player_comp.score}")

    print(f"最终实体数量: {len(world._entities)}")


if __name__ == "__main__":
    main()
