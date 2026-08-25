"""
游戏配置模块
定义游戏的各种配置参数和枚举类型
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any


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

    # MOBA-specific terrain types
    LANE = "lane"  # 兵线路径 - 连接两个基地的主要通道
    JUNGLE = "jungle"  # 野区 - 中性区域，包含野怪和资源
    RIVER = "river"  # 河流 - 分隔两队的中央区域
    BASE = "base"  # 基地 - 队伍主基地区域
    TOWER = "tower"  # 防御塔 - 防御建筑位置
    INHIBITOR = "inhibitor"  # 兵营/水晶 - 控制超级兵的建筑
    ANCIENT = "ancient"  # 遗迹/主堡 - 游戏胜负关键建筑


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


# Headless / CLI player presets. The start-scene UI already uses AI/AI/AI
# for Three Kingdoms; keep that meaning here so eval can pass
# --players three_kingdoms without Wei leaking to HUMAN.
PLAYER_PRESETS: Dict[str, Dict[Faction, PlayerType]] = {
    "human_vs_ai": {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
    "ai_vs_ai": {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
    "three_kingdoms": {
        Faction.WEI: PlayerType.AI,
        Faction.SHU: PlayerType.AI,
        Faction.WU: PlayerType.AI,
    },
    "human_vs_two_ai": {
        Faction.WEI: PlayerType.HUMAN,
        Faction.SHU: PlayerType.AI,
        Faction.WU: PlayerType.AI,
    },
}


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
    REST = "rest"  # 待命
    SKILL = "skill"  # 技能
    OCCUPY = "occupy"  # 占领
    FORTIFY = "fortify"  # 建设工事
    DEFEND = "defend"  # 防御（规则预留）
    SCOUT = "scout"  # 侦察（规则预留）
    RETREAT = "retreat"  # 撤退（规则预留）


@dataclass
class TerrainEffect:
    """Numeric terrain modifiers the sim actually applies.

    ``movement_cost``: MovementSystem (999 is impassable; water is also an
    obstacle). ``defense_bonus`` / ``attack_bonus``: CombatSystem, then
    multiplied by ``TERRAIN_COEFFICIENTS``. ``vision_bonus``: added to unit
    vision range by VisionSystem. Mountains also block line of sight.
    """

    movement_cost: int = 1
    defense_bonus: int = 0
    attack_bonus: int = 0
    vision_bonus: int = 0


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

    # Display. Real-time AP/MP recover 1/FPS seconds per frame; keep at 60.
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    FPS = 60

    # 地图配置
    MAP_WIDTH = 15
    MAP_HEIGHT = 15
    HEX_SIZE = 50
    HEX_ORIENTATION = HexOrientation.FLAT_TOP  # 六边形方向：尖顶向上或平顶向上

    # 游戏配置
    MAX_TURNS = 100  # 回合制超时回合数（超过后平局）
    MAX_REALTIME_SECONDS = 3600  # 实时制超时秒数（到达后平局）
    # Per-faction mix: [infantry, archer, cavalry].
    UNIT_MIX = [1, 3, 1]
    # Wei blob is the visually tuned 2x2+1. Shu is derived at runtime by
    # 180° rotation in *pixel* space (odd-q stagger makes offset (-x,-y)
    # and anti-diagonal (-y,-x) both look wrong on screen). Wu is the
    # same blob reflected to the third bank.
    WEI_FORMATION: List[Tuple[int, int]] = [
        (1, 3),
        (2, 3),
        (1, 4),
        (2, 4),
        (3, 3),
    ]
    WU_FORMATION: List[Tuple[int, int]] = [
        (1, -3),
        (2, -3),
        (1, -4),
        (2, -4),
        (3, -3),
    ]
    VISION_FADE_ALPHA = 128  # 战争迷雾透明度

    # 战争迷雾颜色配置
    FOG_UNEXPLORED_COLOR = (0, 0, 0, 255)  # 未探索区域：黑色
    FOG_EXPLORED_COLOR = (0, 0, 0, 200)  # 已探索但非视野：深色半透明黑色 (从128改为200)
    CURRENT_VISION_OUTLINE_COLOR = (0, 255, 0)  # 当前视野轮廓：绿色
    VISION_OUTLINE_WIDTH = 2  # 视野轮廓线宽度

    # Applied by MovementSystem / CombatSystem / VisionSystem. No other
    # terrain special-cases exist (no hit-chance, range cut, regen, ships).
    TERRAIN_EFFECTS: Dict[TerrainType, TerrainEffect] = {
        TerrainType.PLAIN: TerrainEffect(movement_cost=1),
        TerrainType.MOUNTAIN: TerrainEffect(
            movement_cost=3, defense_bonus=2, attack_bonus=1, vision_bonus=2
        ),
        TerrainType.URBAN: TerrainEffect(movement_cost=2, defense_bonus=4),
        TerrainType.WATER: TerrainEffect(movement_cost=999),
        TerrainType.FOREST: TerrainEffect(movement_cost=2, defense_bonus=1),
        TerrainType.HILL: TerrainEffect(
            movement_cost=2, defense_bonus=1, attack_bonus=1, vision_bonus=1
        ),
        TerrainType.LANE: TerrainEffect(movement_cost=1),
        TerrainType.JUNGLE: TerrainEffect(movement_cost=2, defense_bonus=1),
        TerrainType.RIVER: TerrainEffect(movement_cost=2),
        TerrainType.BASE: TerrainEffect(
            movement_cost=1, defense_bonus=3, attack_bonus=1
        ),
        TerrainType.TOWER: TerrainEffect(
            movement_cost=1, defense_bonus=5, attack_bonus=2
        ),
        TerrainType.INHIBITOR: TerrainEffect(
            movement_cost=1, defense_bonus=3, attack_bonus=1
        ),
        TerrainType.ANCIENT: TerrainEffect(
            movement_cost=1, defense_bonus=8, attack_bonus=3
        ),
    }

    # Spawned onto units by the unit factory.
    UNIT_BASE_STATS: Dict[UnitType, UnitBaseStats] = {
        UnitType.INFANTRY: UnitBaseStats(
            max_count=100,
            movement=4,
            base_attack=10,
            base_defense=10,
            attack_range=1,
            vision_range=2,
        ),
        UnitType.CAVALRY: UnitBaseStats(
            max_count=100,
            movement=8,
            base_attack=14,
            base_defense=6,
            attack_range=1,
            vision_range=3,
        ),
        UnitType.ARCHER: UnitBaseStats(
            max_count=100,
            movement=4,
            base_attack=12,
            base_defense=6,
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
        # MOBA-specific terrain coefficients
        TerrainType.LANE: TerrainCoefficient(
            infantry=1.1, cavalry=1.2, archer=1.1  # 兵线路径利于移动
        ),
        TerrainType.JUNGLE: TerrainCoefficient(
            infantry=1.0, cavalry=0.9, archer=1.1  # 野区利于步兵和弓兵
        ),
        TerrainType.RIVER: TerrainCoefficient(
            infantry=0.9, cavalry=0.8, archer=1.0  # 河流阻碍近战单位
        ),
        TerrainType.BASE: TerrainCoefficient(
            infantry=1.2, cavalry=1.2, archer=1.2  # 基地区域全面加成
        ),
        TerrainType.TOWER: TerrainCoefficient(
            infantry=1.3, cavalry=1.3, archer=1.4  # 防御塔区域强力加成
        ),
        TerrainType.INHIBITOR: TerrainCoefficient(
            infantry=1.15, cavalry=1.15, archer=1.2  # 兵营区域中等加成
        ),
        TerrainType.ANCIENT: TerrainCoefficient(
            infantry=1.5, cavalry=1.5, archer=1.5  # 主堡区域最强加成
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
        # MOBA-specific terrain colors
        TerrainType.LANE: (255, 223, 128),  # 金黄色 - 兵线路径
        TerrainType.JUNGLE: (60, 120, 60),  # 深墨绿色 - 野区
        TerrainType.RIVER: (100, 149, 237),  # 矢车菊蓝 - 河流
        TerrainType.BASE: (220, 220, 220),  # 亮灰色 - 基地
        TerrainType.TOWER: (255, 165, 0),  # 橙色 - 防御塔
        TerrainType.INHIBITOR: (255, 20, 147),  # 深粉色 - 兵营
        TerrainType.ANCIENT: (255, 215, 0),  # 金色 - 主堡
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
