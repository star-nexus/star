"""
游戏配置模块
定义游戏的各种配置参数和枚举类型
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, Any


# 六边形方向枚举
class HexOrientation(Enum):
    POINTY_TOP = "pointy"  # 尖顶向上
    FLAT_TOP = "flat"  # 平顶向上


# 游戏模式枚举
class GameMode(Enum):
    TURN_BASED = "turn_based"  # 回合制
    REAL_TIME = "real_time"  # 实时制


# 玩家类型枚举
class PlayerType(Enum):
    HUMAN = "human"
    AI = "ai"
    LLM = "agent"  # 大语言模型代理


# 地形类型枚举
class TerrainType(Enum):
    PLAIN = "plain"  # 平原
    FOREST = "forest"  # 森林
    MOUNTAIN = "mountain"  # 山地
    WATER = "water"  # 水域
    URBAN = "urban"  # 城池
    HILL = "hill"  # 丘陵


# 单位类型枚举
class UnitType(Enum):
    INFANTRY = "infantry"  # 步兵
    CAVALRY = "cavalry"  # 骑兵
    ARCHER = "archer"  # 弓兵
    SIEGE = "siege"  # 攻城器械


# 阵营枚举
class Faction(Enum):
    WEI = "wei"  # 魏
    SHU = "shu"  # 蜀
    WU = "wu"  # 吴


@dataclass
class TerrainEffect:
    """地形效果配置"""

    attack_bonus: float = 0.0  # 攻击加成
    defense_bonus: float = 0.0  # 防御加成
    range_bonus: int = 0  # 射程加成
    movement_cost: float = 1.0  # 移动消耗
    vision_bonus: int = 0  # 视野加成
    stealth_bonus: float = 0.0  # 隐蔽加成


@dataclass
class UnitStats:
    """单位基础属性"""

    max_hp: int = 100
    attack: int = 20
    defense: int = 10
    movement: int = 3
    vision_range: int = 2
    attack_range: int = 1


@dataclass
class PlayerConfig:
    """玩家配置"""

    player_type: PlayerType
    faction: Faction
    color: Tuple[int, int, int]  # RGB颜色


class GameConfig:
    """游戏总配置类"""

    # 显示配置
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    FPS = 60

    # 地图配置
    MAP_WIDTH = 50
    MAP_HEIGHT = 50
    HEX_SIZE = 50
    HEX_ORIENTATION = HexOrientation.FLAT_TOP  # 六边形方向：尖顶向上或平顶向上

    # 游戏配置
    MAX_TURNS = 100  # 最大回合数
    VISION_FADE_ALPHA = 128  # 战争迷雾透明度

    # 战争迷雾颜色配置
    FOG_UNEXPLORED_COLOR = (0, 0, 0, 255)  # 未探索区域：黑色
    FOG_EXPLORED_COLOR = (0, 0, 0, 128)  # 已探索但非视野：半透明黑色
    CURRENT_VISION_OUTLINE_COLOR = (0, 255, 0)  # 当前视野轮廓：绿色
    VISION_OUTLINE_WIDTH = 2  # 视野轮廓线宽度

    # 地形效果配置
    TERRAIN_EFFECTS: Dict[TerrainType, TerrainEffect] = {
        TerrainType.PLAIN: TerrainEffect(
            attack_bonus=0.0, defense_bonus=0.0, movement_cost=1.0, vision_bonus=0
        ),
        TerrainType.FOREST: TerrainEffect(
            attack_bonus=-0.1,
            defense_bonus=0.2,
            movement_cost=1.5,
            vision_bonus=-1,
            stealth_bonus=0.3,
        ),
        TerrainType.MOUNTAIN: TerrainEffect(
            attack_bonus=0.2,
            defense_bonus=0.3,
            movement_cost=2.0,
            vision_bonus=2,
            range_bonus=1,
        ),
        TerrainType.HILL: TerrainEffect(
            attack_bonus=0.1, defense_bonus=0.1, movement_cost=1.2, vision_bonus=1
        ),
        TerrainType.WATER: TerrainEffect(
            attack_bonus=-0.3, defense_bonus=-0.2, movement_cost=3.0, vision_bonus=0
        ),
        TerrainType.URBAN: TerrainEffect(
            attack_bonus=0.0, defense_bonus=0.5, movement_cost=1.0, vision_bonus=1
        ),
    }

    # 单位属性配置
    UNIT_STATS: Dict[UnitType, UnitStats] = {
        UnitType.INFANTRY: UnitStats(
            max_hp=120,
            attack=25,
            defense=20,
            movement=3,
            vision_range=2,
            attack_range=1,
        ),
        UnitType.CAVALRY: UnitStats(
            max_hp=100,
            attack=30,
            defense=15,
            movement=5,
            vision_range=3,
            attack_range=1,
        ),
        UnitType.ARCHER: UnitStats(
            max_hp=80, attack=20, defense=10, movement=2, vision_range=3, attack_range=3
        ),
        UnitType.SIEGE: UnitStats(
            max_hp=150,
            attack=40,
            defense=25,
            movement=1,
            vision_range=1,
            attack_range=2,
        ),
    }

    # 阵营颜色配置
    FACTION_COLORS: Dict[Faction, Tuple[int, int, int]] = {
        Faction.WEI: (0, 0, 255),  # 蓝色
        Faction.SHU: (255, 0, 0),  # 红色
        Faction.WU: (0, 255, 0),  # 绿色
    }

    # 地形颜色配置
    TERRAIN_COLORS: Dict[TerrainType, Tuple[int, int, int]] = {
        TerrainType.PLAIN: (144, 238, 144),  # 浅绿色
        TerrainType.FOREST: (34, 139, 34),  # 深绿色
        TerrainType.MOUNTAIN: (139, 69, 19),  # 褐色
        TerrainType.HILL: (160, 82, 45),  # 浅褐色
        TerrainType.WATER: (135, 206, 250),  # 浅蓝色
        TerrainType.URBAN: (169, 169, 169),  # 灰色
    }

    @classmethod
    def get_default_players(cls) -> Dict[Faction, PlayerConfig]:
        """获取默认玩家配置"""
        return {
            Faction.WEI: PlayerConfig(
                player_type=PlayerType.HUMAN,
                faction=Faction.WEI,
                color=cls.FACTION_COLORS[Faction.WEI],
            ),
            Faction.SHU: PlayerConfig(
                player_type=PlayerType.AI,
                faction=Faction.SHU,
                color=cls.FACTION_COLORS[Faction.SHU],
            ),
        }
