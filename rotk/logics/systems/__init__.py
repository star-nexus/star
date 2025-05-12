"""
系统模块

包含游戏中使用的所有系统实现。
"""

# 导入所有系统
from .map_system import MapSystem
from .faction_system import FactionSystem
from .unit_system import UnitSystem
from .render_system import RenderSystem
from .human_control_system import HumanControlSystem
from .victory_system import VictorySystem
from .ai_control_system import AIControlSystem

# 导入战斗相关系统
from .combat_system import CombatSystem
# from .attack_system import AttackSystem
# from .damage_system import DamageSystem
# from .combat_effects_system import CombatEffectsSystem

__all__ = [
    'MapSystem',
    'FactionSystem',
    'UnitSystem',
    'CombatSystem',
    'RenderSystem',
    'HumanControlSystem',
    'VictorySystem',
    'AIControlSystem',
    # 'AttackSystem',
    # 'DamageSystem',
    # 'CombatEffectsSystem',
]
