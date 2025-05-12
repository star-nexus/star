"""
配置模块

包含游戏中使用的所有配置信息。
"""

# 导入各配置子模块
from .units.unit_configs import UNIT_CONFIGS
from .combat.combat_configs import ATTACK_CONFIGS, DAMAGE_CONFIGS, COMBAT_EFFECTS_CONFIGS

__all__ = [
    'UNIT_CONFIGS',
    'ATTACK_CONFIGS',
    'DAMAGE_CONFIGS',
    'COMBAT_EFFECTS_CONFIGS',
]
