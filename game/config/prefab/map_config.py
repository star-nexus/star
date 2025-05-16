from typing import Dict, Any
import numpy as np

# 地图组件配置
MAP_CONFIG = {
    "default": {
        "width": 10,
        "height": 10,
        "tile_size": 32,
    },
    "tiny": {
        "width": 3,
        "height": 3,
        "tile_size": 32,
    },
    "tiny2": {
        "width": 3,
        "height": 3,
        "tile_size": 8,
    },
    "tiny3": {
        "width": 10,
        "height": 10,
        "tile_size": 20,
    },
    "small": {
        "width": 8,
        "height": 8,
        "tile_size": 32,
    },
    "medium": {
        "width": 15,
        "height": 15,
        "tile_size": 32,
    },
    "large": {
        "width": 20,
        "height": 20,
        "tile_size": 32,
    },
    "huge": {
        "width": 50,
        "height": 50,
        "tile_size": 32,
    },
}

# 地形属性配置
TERRAIN_PROPERTIES = {
    # 地形类型: (移动成本, 防御加成)
    0: {"movement_cost": 1.0, "defense_bonus": 0.0},  # 平原
    1: {"movement_cost": 2.0, "defense_bonus": 0.1},  # 丘陵
    2: {"movement_cost": 3.0, "defense_bonus": 0.2},  # 山地
    3: {"movement_cost": 1.5, "defense_bonus": 0.05},  # 森林
    4: {"movement_cost": 4.0, "defense_bonus": -0.1},  # 沼泽
    5: {"movement_cost": 99.0, "defense_bonus": 0.0},  # 水域
    6: {"movement_cost": 1.0, "defense_bonus": 0.3},  # 城市
    7: {"movement_cost": 1.0, "defense_bonus": 0.15},  # 村庄
}

# 地图生成配置
MAP_GENERATION_CONFIG = {
    "default": {
        "seed": 12345,
        "noise_scale": 0.1,
        "elevation_octaves": 4,
        "moisture_octaves": 2,
    }
}


def get_map_config(config_name: str = "default") -> Dict[str, Any]:
    """获取指定名称的地图配置"""
    return MAP_CONFIG.get(config_name, MAP_CONFIG["default"])


def get_terrain_properties(terrain_type: int) -> Dict[str, float]:
    """获取地形属性"""
    return TERRAIN_PROPERTIES.get(
        terrain_type, {"movement_cost": 1.0, "defense_bonus": 0.0}
    )


def get_map_generation_config(config_name: str = "default") -> Dict[str, Any]:
    """获取地图生成配置"""
    return MAP_GENERATION_CONFIG.get(config_name, MAP_GENERATION_CONFIG["default"])
