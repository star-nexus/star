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
    WATER = "water"  # 水域/湖泊
    URBAN = "urban"  # 城池
    CITY = "city"  # 大城市
    HILL = "hill"  # 丘陵


# 单位类型枚举
class UnitType(Enum):
    INFANTRY = "infantry"  # 步兵
    CAVALRY = "cavalry"  # 骑兵
    ARCHER = "archer"  # 弓兵


# 阵营枚举
class Faction(Enum):
    WEI = "wei"  # 魏
    SHU = "shu"  # 蜀
    WU = "wu"  # 吴


# 单位状态枚举
class UnitState(Enum):
    NORMAL = "normal"  # 正常
    FATIGUE = "fatigue"  # 疲劳
    CONFUSION = "confusion"  # 混乱
    HIGH_MORALE = "high_morale"  # 士气高昂
    HIDDEN = "hidden"  # 隐蔽


# 行动类型枚举
class ActionType(Enum):
    MOVE = "move"  # 移动
    ATTACK = "attack"  # 攻击
    GARRISON = "garrison"  # 驻扎
    WAIT = "wait"  # 待命
    SKILL = "skill"  # 技能
    CAPTURE = "capture"  # 占领
    FORTIFY = "fortify"  # 建设工事


@dataclass
class TerrainEffect:
    """地形效果配置"""

    movement_cost: int = 1  # 通行消耗
    defense_bonus: int = 0  # 基础防御修正
    special_rules: str = ""  # 额外规则描述


@dataclass
class UnitBaseStats:
    """单位基础属性（满编状态）"""

    max_count: int = 100  # 满编人数
    movement: int = 3  # 基础移动力
    base_attack: int = 10  # 基础攻击（中）
    base_defense: int = 8  # 基础防御（中）
    attack_range: int = 1  # 攻击范围
    vision_range: int = 2  # 视野范围
    keywords: str = ""  # 关键词技能


@dataclass
class TerrainCoefficient:
    """地形系数配置"""

    infantry: float = 1.0
    cavalry: float = 1.0
    archer: float = 1.0


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
    FOG_EXPLORED_COLOR = (0, 0, 0, 200)  # 已探索但非视野：深色半透明黑色 (从128改为200)
    CURRENT_VISION_OUTLINE_COLOR = (0, 255, 0)  # 当前视野轮廓：绿色
    VISION_OUTLINE_WIDTH = 2  # 视野轮廓线宽度

    # 地形基础属性（按规则手册v1.2）
    TERRAIN_EFFECTS: Dict[TerrainType, TerrainEffect] = {
        TerrainType.PLAIN: TerrainEffect(
            movement_cost=1, defense_bonus=0, special_rules="无"
        ),
        TerrainType.MOUNTAIN: TerrainEffect(
            movement_cost=3, defense_bonus=2, special_rules="远程单位射程-1"
        ),
        TerrainType.URBAN: TerrainEffect(
            movement_cost=2,
            defense_bonus=4,
            special_rules="被围攻时每回合自动恢复5%耐久",
        ),
        TerrainType.WATER: TerrainEffect(
            movement_cost=999,
            defense_bonus=0,
            special_rules="仅「船只」或「飞行」单位可通过",
        ),
        TerrainType.FOREST: TerrainEffect(
            movement_cost=2, defense_bonus=1, special_rules="远程命中率-20%"
        ),
        TerrainType.HILL: TerrainEffect(
            movement_cost=2, defense_bonus=1, special_rules="近战先攻权+1"
        ),
    }

    # 兵种基础属性（按规则手册v1.2）
    UNIT_BASE_STATS: Dict[UnitType, UnitBaseStats] = {
        UnitType.INFANTRY: UnitBaseStats(
            max_count=100,
            movement=3,
            base_attack=10,  # 中
            base_defense=8,  # 中
            attack_range=1,
            vision_range=2,
        ),
        UnitType.CAVALRY: UnitBaseStats(
            max_count=100,
            movement=5,
            base_attack=12,  # 高
            base_defense=6,  # 低
            attack_range=1,
            vision_range=3,
        ),
        UnitType.ARCHER: UnitBaseStats(
            max_count=100,
            movement=3,
            base_attack=8,  # 低
            base_defense=4,  # 极低
            attack_range=3,
            vision_range=4,
        ),
    }

    # 保留旧的UNIT_STATS字典以兼容现有代码
    UNIT_STATS: Dict[UnitType, UnitBaseStats] = UNIT_BASE_STATS

    # 状态系数表（按规则手册v1.2）
    STATE_COEFFICIENTS: Dict[UnitState, float] = {
        UnitState.NORMAL: 1.0,
        UnitState.FATIGUE: 0.85,
        UnitState.CONFUSION: 0.7,
        UnitState.HIGH_MORALE: 1.15,
        UnitState.HIDDEN: 1.0,  # 隐蔽不影响攻防
    }

    # 地形系数表（按规则手册v1.2）
    TERRAIN_COEFFICIENTS: Dict[TerrainType, TerrainCoefficient] = {
        TerrainType.PLAIN: TerrainCoefficient(infantry=1.0, cavalry=1.0, archer=1.0),
        TerrainType.MOUNTAIN: TerrainCoefficient(infantry=1.1, cavalry=0.8, archer=0.9),
        TerrainType.URBAN: TerrainCoefficient(infantry=1.2, cavalry=1.2, archer=1.2),
        TerrainType.CITY: TerrainCoefficient(infantry=1.3, cavalry=1.3, archer=1.3),
        TerrainType.FOREST: TerrainCoefficient(
            infantry=1.05, cavalry=0.75, archer=0.85
        ),
        TerrainType.HILL: TerrainCoefficient(
            infantry=1.05, cavalry=1.1, archer=1.0  # 骑兵向下冲锋
        ),
        TerrainType.WATER: TerrainCoefficient(
            infantry=0.5, cavalry=0.3, archer=0.7  # 水域惩罚
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
        TerrainType.CITY: (105, 105, 105),  # 深灰色
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
