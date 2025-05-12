from dataclasses import dataclass
from framework_v2.ecs.component import Component
from typing import List

@dataclass
class CombatComponent(Component):
    """战斗组件"""
    attack_range: int = 100       # 攻击范围（像素）
    base_attack: int = 10         # 基础攻击力
    base_defense: int = 5         # 基础防御力
    attack_types: List[str] = None  # 攻击类型 ["melee", "range"]
    cooldown: float = 1.0         # 攻击冷却时间（秒）
    current_cooldown: float = 0.0 # 当前冷却剩余时间
    is_in_combat: bool = False    # 是否处于战斗状态