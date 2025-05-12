from enum import Enum, auto


class RenderLayer(Enum):
    MAP = 0  # 地图
    MAP_EFFECT = 1  # 地图特效
    UNIT = 2  # 单位
    UNIT_EFFECT = 3  # 特效
    UI = 4  # UI
    FOW = 5  # 战争迷雾


class UnitType(Enum):
    """单位类型枚举"""

    INFANTRY = auto()  # 步兵
    CAVALRY = auto()  # 骑兵
    ARCHER = auto()  # 弓箭手
    SIEGE = auto()  # 攻城单位
    HERO = auto()  # 英雄单位


class UnitState(Enum):
    """单位状态枚举"""

    IDLE = auto()  # 空闲
    MOVING = auto()  # 移动中
    ATTACKING = auto()  # 攻击中
    DEFENDING = auto()  # 防御中
    DEAD = auto()  # 已阵亡


class TerrainType(Enum):
    """地形类型枚举"""

    # 基本地形类型
    PLAIN = auto()  # 平原
    HILL = auto()  # 丘陵
    MOUNTAIN = auto()  # 山地
    PLATEAU = auto()  # 高原
    BASIN = auto()  # 盆地

    # 植被类型
    FOREST = auto()  # 森林
    GRASSLAND = auto()  # 草地

    # 水系
    RIVER = auto()  # 河流
    LAKE = auto()  # 湖泊
    OCEAN = auto()  # 海洋
    WETLAND = auto()  # 湿地

    # 特殊地形
    ROAD = auto()  # 道路
    BRIDGE = auto()  # 桥梁
    CITY = auto()  # 城市
    VILLAGE = auto()  # 村庄
    CASTLE = auto()  # 城堡
    PASS = auto()  # 关隘/隘口


class ViewMode(Enum):
    """游戏统计视图模式"""

    GLOBAL = 0  # 全局模式，显示所有信息
    PLAYER = 1  # 玩家视角模式，只显示已知信息


class FOWType:
    """
    未知区域类型
    """

    UNKNOWN = 0  # 未知区域
    FOG = 1  # 迷雾
    EXPLORATION = 2  # 探索区域
