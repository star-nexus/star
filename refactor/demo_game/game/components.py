from dataclasses import dataclass
from framework.core.ecs.component import Component
from typing import Tuple

@dataclass
class Position(Component):
    """位置组件"""
    x: float = 0.0
    y: float = 0.0

@dataclass
class Velocity(Component):
    """速度组件"""
    x: float = 0.0
    y: float = 0.0

@dataclass
class Collider(Component):
    """碰撞组件"""
    radius: float = 20.0  # 使用圆形碰撞盒
    is_glowing: bool = False  # 是否发光
    glow_timer: float = 0.0  # 发光计时器

@dataclass
class Renderable(Component):
    """渲染组件"""
    color: Tuple[int, int, int] = (255, 255, 255)  # 默认白色
    radius: float = 20.0  # 渲染半径

@dataclass
class Player(Component):
    """玩家组件，标记实体为玩家"""
    speed: float = 200.0  # 玩家移动速度

@dataclass
class Enemy(Component):
    """敌人组件，标记实体为敌人"""
    speed: float = 150.0  # 敌人移动速度

@dataclass
class Obstacle(Component):
    """障碍物组件，标记实体为障碍物"""
    pass