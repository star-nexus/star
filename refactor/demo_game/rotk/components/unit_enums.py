from enum import Enum, auto


class UnitType(Enum):
    """单位类型枚举"""

    SHIELD_INFANTRY = "刀盾兵"  # 近战步兵
    SPEAR_INFANTRY = "长戟兵"  # 长兵器步兵
    SCOUT_CAVALRY = "斥候骑兵"  # 轻骑兵
    MOUNTED_ARCHER = "骑射手"  # 骑射手
    ARCHER = "弓箭手"  # 弓箭手
    CROSSBOWMAN = "弩手"  # 弩手
    NAVY = "水军"  # 水军
    HEAVY_CAVALRY = "虎豹骑"  # 重装骑兵
    MOUNTAIN_INFANTRY = "无当飞军"  # 山地步兵


class UnitCategory(Enum):
    """单位类别枚举"""

    INFANTRY = "步兵"
    CAVALRY = "骑兵"
    RANGED = "远程"
    SPECIAL = "特殊"


class UnitState(Enum):
    """单位状态枚举"""

    IDLE = "空闲"
    MOVING = "移动中"
    ATTACKING = "攻击中"
    DEFENDING = "防御中"
    GARRISONED = "驻扎中"
    ROUTED = "溃逃中"
    DEAD = "阵亡"


class TerrainAdaptability(Enum):
    """地形适应性枚举"""

    EXCELLENT = 1.5  # 极佳 (移动消耗降低50%)
    GOOD = 1.0  # 良好 (正常移动消耗)
    AVERAGE = 0.75  # 一般 (移动消耗增加25%)
    POOR = 0.5  # 较差 (移动消耗增加50%)
    VERY_POOR = 0.25  # 极差 (移动消耗增加75%)


class SupplyStatus(Enum):
    """补给状态枚举"""

    FULL = "补给充足"
    ADEQUATE = "补给良好"
    LOW = "补给不足"
    CRITICAL = "补给危急"
    DEPLETED = "补给耗尽"
