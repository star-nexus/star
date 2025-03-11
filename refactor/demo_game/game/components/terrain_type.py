from enum import Enum, auto


class TerrainType(Enum):
    """地形类型枚举"""

    PLAIN = auto()  # 平原
    MOUNTAIN = auto()  # 山地
    RIVER = auto()  # 河流
    FOREST = auto()  # 森林
    LAKE = auto()  # 湖泊
