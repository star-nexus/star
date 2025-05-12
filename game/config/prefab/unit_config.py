from typing import Dict, Any, List
from game.utils.game_types import UnitType, UnitState

# 单位类型配置
UNIT_TYPE_CONFIG = {
    UnitType.INFANTRY: {
        "name": "步兵",
        "max_health": 100,
        "attack": 10,
        "defense": 5,
        "range": 5,
        "base_speed": 2.0,
        "movement": 5,
        "unit_size": 1.0,
        "abilities": [],
    },
    UnitType.CAVALRY: {
        "name": "骑兵",
        "max_health": 120,
        "attack": 12,
        "defense": 3,
        "range": 5,
        "base_speed": 10.0,
        "movement": 7,
        "unit_size": 1.2,
        "abilities": ["charge"],
    },
    UnitType.ARCHER: {
        "name": "弓箭手",
        "max_health": 80,
        "attack": 2,
        "defense": 2,
        "range": 20,
        "base_speed": 3.0,
        "movement": 4,
        "unit_size": 0.9,
        "abilities": ["ranged_attack"],
    },
    UnitType.SIEGE: {
        "name": "攻城单位",
        "max_health": 150,
        "attack": 20,
        "defense": 1,
        "range": 4,
        "base_speed": 1.0,
        "movement": 3,
        "unit_size": 1.5,
        "abilities": ["siege_attack"],
    },
    UnitType.HERO: {
        "name": "英雄单位",
        "max_health": 200,
        "attack": 25,
        "defense": 10,
        "range": 2,
        "base_speed": 2.5,
        "movement": 6,
        "unit_size": 1.3,
        "abilities": ["leadership", "special_attack"],
    },
}

# 阵营配置
FACTION_CONFIG = {
    0: {
        "name": "玩家",
        "color": (0, 0, 255),  # 蓝色
        "unit_modifier": {"attack": 1.0, "defense": 1.0},
    },
    1: {
        "name": "敌军",
        "color": (255, 0, 0),  # 红色
        "unit_modifier": {"attack": 1.0, "defense": 1.0},
    },
    2: {
        "name": "中立",
        "color": (200, 200, 200),  # 灰色
        "unit_modifier": {"attack": 0.8, "defense": 0.8},
    },
}

# 预设单位配置
PREDEFINED_UNITS = {
    "player_infantry": {
        "unit_type": UnitType.INFANTRY,
        "faction": 0,
        "level": 1,
    },
    "enemy_cavalry": {
        "unit_type": UnitType.CAVALRY,
        "faction": 1,
        "level": 1,
    },
    "neutral_archer": {
        "unit_type": UnitType.ARCHER,
        "faction": 2,
        "level": 1,
    },
    "player_hero": {
        "unit_type": UnitType.HERO,
        "faction": 0,
        "level": 3,
    },
}


def get_unit_config(unit_type: UnitType) -> Dict[str, Any]:
    """获取指定类型的单位配置"""
    return UNIT_TYPE_CONFIG.get(unit_type, UNIT_TYPE_CONFIG[UnitType.INFANTRY])


def get_faction_config(faction_id: int) -> Dict[str, Any]:
    """获取指定阵营的配置"""
    return FACTION_CONFIG.get(faction_id, FACTION_CONFIG[0])


def get_predefined_unit(unit_id: str) -> Dict[str, Any]:
    """获取预设单位配置"""
    if unit_id not in PREDEFINED_UNITS:
        return None

    unit_config = PREDEFINED_UNITS[unit_id].copy()
    # 合并单位类型的基础属性
    base_config = get_unit_config(unit_config["unit_type"]).copy()
    base_config.update(unit_config)
    return base_config


def create_unit_config(
    unit_type: UnitType, faction: int, level: int = 1, **kwargs
) -> Dict[str, Any]:
    """创建自定义单位配置"""
    # 获取基础配置
    config = get_unit_config(unit_type).copy()

    # 应用等级加成
    if level > 1:
        config["max_health"] = int(config["max_health"] * (1 + 0.1 * (level - 1)))
        config["attack"] = int(config["attack"] * (1 + 0.1 * (level - 1)))
        config["defense"] = int(config["defense"] * (1 + 0.1 * (level - 1)))

    # 设置阵营
    config["faction"] = faction
    config["level"] = level

    # 应用自定义属性
    config.update(kwargs)

    # 确保当前生命值等于最大生命值
    config["current_health"] = config["max_health"]

    # 确保剩余移动力等于总移动力
    config["movement_left"] = config["movement"]

    return config
