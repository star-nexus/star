"""
移动系统示例 - 展示2D空间中的移动和碰撞检测

这个示例演示了：
1. 位置和速度组件
2. 移动系统的实现
3. 边界碰撞检测
4. 简单的AI寻路
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from dataclasses import dataclass
from framework.ecs.world import World
from framework.ecs.component import Component
from framework.ecs.system import System
import math
import random
import time


# 定义组件
@dataclass
class PositionComponent(Component):
    """位置组件"""

    x: float = 0.0
    y: float = 0.0

    def distance_to(self, other) -> float:
        """计算到另一个位置的距离"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass
class VelocityComponent(Component):
    """速度组件"""

    x: float = 0.0
    y: float = 0.0
    max_speed: float = 100.0

    def set_velocity(self, vx: float, vy: float):
        """设置速度，限制在最大速度内"""
        speed = math.sqrt(vx**2 + vy**2)
        if speed > self.max_speed:
            factor = self.max_speed / speed
            self.x = vx * factor
            self.y = vy * factor
        else:
            self.x = vx
            self.y = vy


@dataclass
class NameComponent(Component):
    """名称组件"""

    name: str = "Unknown"


@dataclass
class TargetComponent(Component):
    """目标组件 - 用于AI移动"""

    target_x: float = 0.0
    target_y: float = 0.0
    arrival_threshold: float = 5.0  # 到达阈值

    def set_target(self, x: float, y: float):
        self.target_x = x
        self.target_y = y


@dataclass
class BoundsComponent(Component):
    """边界组件 - 定义移动边界"""

    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 800.0
    max_y: float = 600.0


# 定义系统
class MovementSystem(System):
    """移动系统 - 根据速度更新位置"""

    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )

            # 更新位置
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time


class BoundarySystem(System):
    """边界系统 - 处理边界碰撞"""

    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent, BoundsComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )
            bounds = self.context.component_manager.get_component(
                entity, BoundsComponent
            )

            # 检查X边界
            if pos.x <= bounds.min_x:
                pos.x = bounds.min_x
                vel.x = abs(vel.x)  # 反弹
            elif pos.x >= bounds.max_x:
                pos.x = bounds.max_x
                vel.x = -abs(vel.x)  # 反弹

            # 检查Y边界
            if pos.y <= bounds.min_y:
                pos.y = bounds.min_y
                vel.y = abs(vel.y)  # 反弹
            elif pos.y >= bounds.max_y:
                pos.y = bounds.max_y
                vel.y = -abs(vel.y)  # 反弹


class AIMovementSystem(System):
    """AI移动系统 - 自动寻路到目标"""

    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent, TargetComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )
            target = self.context.component_manager.get_component(
                entity, TargetComponent
            )

            # 计算到目标的距离
            dx = target.target_x - pos.x
            dy = target.target_y - pos.y
            distance = math.sqrt(dx**2 + dy**2)

            # 如果已经到达目标，设置新的随机目标
            if distance <= target.arrival_threshold:
                target.set_target(random.uniform(50, 750), random.uniform(50, 550))
                continue

            # 归一化方向向量并设置速度
            if distance > 0:
                direction_x = dx / distance
                direction_y = dy / distance
                vel.set_velocity(
                    direction_x * vel.max_speed, direction_y * vel.max_speed
                )


class StatusSystem(System):
    """状态系统 - 显示实体状态"""

    def __init__(self):
        super().__init__([PositionComponent, NameComponent])
        self.update_timer = 0.0

    def update(self, delta_time: float):
        if not self.context:
            return

        self.update_timer += delta_time
        if self.update_timer < 2.0:  # 每2秒更新一次
            return

        self.update_timer = 0.0
        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

        print("\n=== 实体状态 ===")
        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            name = self.context.component_manager.get_component(entity, NameComponent)
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )
            target = self.context.component_manager.get_component(
                entity, TargetComponent
            )

            speed = math.sqrt(vel.x**2 + vel.y**2) if vel else 0

            status = f"[{entity}] {name.name} - 位置:({pos.x:.1f}, {pos.y:.1f}) - 速度:{speed:.1f}"

            if target:
                distance = pos.distance_to(
                    PositionComponent(target.target_x, target.target_y)
                )
                status += f" - 目标:({target.target_x:.1f}, {target.target_y:.1f}) - 距离:{distance:.1f}"

            print(status)


def main():
    print("=== 移动系统示例 ===")
    print("这个示例展示了2D空间中的移动、碰撞检测和AI寻路")
    print("观察实体如何在边界内移动并自动寻找新目标")
    print("按 Ctrl+C 退出\n")

    # 创建世界
    world = World()

    # 添加系统
    world.add_system(AIMovementSystem())
    world.add_system(MovementSystem())
    world.add_system(BoundarySystem())
    world.add_system(StatusSystem())

    # 创建移动实体
    entities_data = [
        ("游侠", 100, 100, 80),
        ("骑兵", 200, 150, 120),
        ("弓箭手", 300, 200, 60),
        ("法师", 400, 250, 40),
    ]

    for name, start_x, start_y, max_speed in entities_data:
        entity = world.create_entity()
        world.add_component(entity, NameComponent(name=name))
        world.add_component(entity, PositionComponent(x=start_x, y=start_y))
        world.add_component(entity, VelocityComponent(max_speed=max_speed))
        world.add_component(entity, BoundsComponent())
        world.add_component(
            entity,
            TargetComponent(
                target_x=random.uniform(50, 750), target_y=random.uniform(50, 550)
            ),
        )
        print(
            f"创建实体: {name} - 起始位置:({start_x}, {start_y}) - 最大速度:{max_speed}"
        )

    # 创建一个纯移动实体（无AI）
    bouncing_entity = world.create_entity()
    world.add_component(bouncing_entity, NameComponent(name="弹跳球"))
    world.add_component(bouncing_entity, PositionComponent(x=400, y=300))
    world.add_component(bouncing_entity, VelocityComponent(x=150, y=100, max_speed=200))
    world.add_component(bouncing_entity, BoundsComponent())
    print("创建弹跳球 - 在边界内随机弹跳")

    print(f"\n创建了 {len(entities_data) + 1} 个移动实体")

    # 游戏循环
    try:
        last_time = time.time()
        while True:
            current_time = time.time()
            delta_time = current_time - last_time
            last_time = current_time

            # 更新世界
            world.update(delta_time)

            # 控制更新频率
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\n游戏结束!")


if __name__ == "__main__":
    main()
