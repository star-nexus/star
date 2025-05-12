from dataclasses import dataclass
from framework_v2.ecs.component import Component

@dataclass
class CityComponent(Component):
    """城市组件"""
    name: str = "未命名"
    force: str = "中立"
    population: int = 1000
    max_population: int = 2000
    food: int = 500
    gold: int = 200
    defense: int = 50