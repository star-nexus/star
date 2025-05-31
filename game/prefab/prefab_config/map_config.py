from typing import Dict, Any
import numpy as np

# 地图组件配置
MAP_CONFIG = {
    "default": {
        "map_type": "square",
        "width": 5,
        "height": 5,
        "tile_size": 32,
    },
}
HEX_MAP_CONFIG = {
    "default": {
        "map_type": "hexagonal",  # 新增：地图类型
        "orientation": "flat_top",  # 新增：六边形方向 (flat_top, pointy_top)
        "radius": 3,  # 六边形地图半径
        "hex_size": 30,  # 增加六边形大小以避免重叠
        "width": 7,  # 计算得出的宽度 (2*radius + 1)
        "height": 7,  # 计算得出的高度
        "tile_size": 16,  # 保持兼容性
    },
    "tiny": {
        "map_type": "hexagonal",
        "orientation": "flat_top",
        "radius": 2,
        "hex_size": 35,  # 增加尺寸
        "width": 5,
        "height": 5,
        "tile_size": 32,
    },
    "tiny2": {
        "map_type": "hexagonal",
        "orientation": "pointy_top",  # 测试尖顶布局
        "radius": 2,
        "hex_size": 35,
        "width": 5,
        "height": 5,
        "tile_size": 8,
    },
    "tiny3": {
        "map_type": "hexagonal",
        "orientation": "pointy_top",
        "radius": 2,
        "hex_size": 35,
        "width": 5,
        "height": 5,
        "tile_size": 20,
    },
    "small": {
        "map_type": "hexagonal",
        "orientation": "flat_top",
        "radius": 4,
        "hex_size": 28,  # 调整尺寸
        "width": 9,
        "height": 9,
        "tile_size": 32,
    },
    "medium": {
        "map_type": "hexagonal",
        "orientation": "flat_top",
        "radius": 6,
        "hex_size": 25,  # 调整尺寸
        "width": 13,
        "height": 13,
        "tile_size": 32,
    },
    "large": {
        "map_type": "hexagonal",
        "orientation": "flat_top",
        "radius": 8,
        "hex_size": 22,  # 调整尺寸
        "width": 17,
        "height": 17,
        "tile_size": 32,
    },
    "huge": {
        "width": 50,
        "height": 50,
        "tile_size": 32,
    },
    # 保留方形地图选项
    "square_tiny": {
        "map_type": "square",
        "width": 3,
        "height": 3,
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
    config = MAP_CONFIG.get(config_name, MAP_CONFIG["default"])

    # 为六边形地图计算实际尺寸
    if config.get("map_type") == "hexagonal" and "radius" in config:
        radius = config["radius"]
        config["width"] = 2 * radius + 1
        config["height"] = 2 * radius + 1

    return config


def get_terrain_properties(terrain_type: int) -> Dict[str, float]:
    """获取地形属性"""
    return TERRAIN_PROPERTIES.get(
        terrain_type, {"movement_cost": 1.0, "defense_bonus": 0.0}
    )


def get_map_generation_config(config_name: str = "default") -> Dict[str, Any]:
    """获取地图生成配置"""
    return MAP_GENERATION_CONFIG.get(config_name, MAP_GENERATION_CONFIG["default"])
