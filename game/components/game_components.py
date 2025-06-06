"""
Romance of the Three Kingdoms Game Components
游戏组件定义 - 三国演义相关的游戏数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum

from framework.ecs.component import Component


# 基础游戏组件
@dataclass
class Position(Component):
    """位置组件 - 在2D/3D空间中的位置"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Movement(Component):
    """移动组件 - 移动相关属性"""

    velocity_x: float = 0.0
    velocity_y: float = 0.0
    speed: float = 1.0
    max_speed: float = 5.0


@dataclass
class Health(Component):
    """生命值组件"""

    current: int = 100
    maximum: int = 100

    @property
    def is_alive(self) -> bool:
        return self.current > 0

    @property
    def health_percentage(self) -> float:
        return self.current / self.maximum if self.maximum > 0 else 0.0


# 三国游戏特色组件
class Kingdom(Enum):
    """三国势力枚举"""

    WEI = "魏"  # 魏国
    SHU = "蜀"  # 蜀国
    WU = "吴"  # 吴国
    HAN = "汉"  # 汉朝
    YELLOW_TURBAN = "黄巾"  # 黄巾军
    NEUTRAL = "中立"


class GeneralType(Enum):
    """武将类型"""

    WARRIOR = "武将"  # 武力型
    STRATEGIST = "谋士"  # 智力型
    BALANCED = "全才"  # 平衡型
    ARCHER = "弓将"  # 弓箭手
    CAVALRY = "骑将"  # 骑兵


@dataclass
class General(Component):
    """武将组件 - 三国武将的核心属性"""

    name: str = "无名武将"
    kingdom: Kingdom = Kingdom.NEUTRAL
    general_type: GeneralType = GeneralType.BALANCED

    # 五维属性（满分100）
    force: int = 50  # 武力 - 影响攻击力和近战能力
    intelligence: int = 50  # 智力 - 影响策略和魔法能力
    politics: int = 50  # 政治 - 影响外交和内政
    charisma: int = 50  # 魅力 - 影响招募和士气
    leadership: int = 50  # 统帅 - 影响部队数量和指挥

    level: int = 1
    experience: int = 0

    @property
    def total_stats(self) -> int:
        """总属性值"""
        return (
            self.force
            + self.intelligence
            + self.politics
            + self.charisma
            + self.leadership
        )


@dataclass
class Army(Component):
    """军队组件"""

    soldiers: int = 100  # 士兵数量
    max_soldiers: int = 100  # 最大士兵数量
    morale: int = 100  # 士气
    supplies: int = 100  # 补给
    formation: str = "方阵"  # 阵型


@dataclass
class Skills(Component):
    """技能组件 - 武将特殊技能"""

    active_skills: List[str] = field(default_factory=list)  # 主动技能
    passive_skills: List[str] = field(default_factory=list)  # 被动技能
    ultimate_skill: Optional[str] = None  # 必杀技
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)  # 技能冷却


@dataclass
class Equipment(Component):
    """装备组件"""

    weapon: Optional[str] = None  # 武器
    armor: Optional[str] = None  # 盔甲
    accessory: Optional[str] = None  # 配饰
    horse: Optional[str] = None  # 战马

    # 装备加成
    force_bonus: int = 0
    intelligence_bonus: int = 0
    defense_bonus: int = 0


@dataclass
class Territory(Component):
    """领土组件 - 用于城池或据点"""

    name: str = "未知城池"
    controller: Kingdom = Kingdom.NEUTRAL
    population: int = 1000
    prosperity: int = 50  # 繁荣度
    defense: int = 50  # 防御力
    garrison: int = 0  # 驻军数量


@dataclass
class Diplomacy(Component):
    """外交组件 - 与其他势力的关系"""

    relationships: Dict[Kingdom, int] = field(
        default_factory=dict
    )  # 关系值 (-100到100)
    alliances: Set[Kingdom] = field(default_factory=set)  # 同盟
    enemies: Set[Kingdom] = field(default_factory=set)  # 敌对

    def get_relationship(self, kingdom: Kingdom) -> int:
        """获取与指定势力的关系"""
        return self.relationships.get(kingdom, 0)


@dataclass
class Resources(Component):
    """资源组件"""

    gold: int = 1000  # 金币
    food: int = 1000  # 粮食
    iron: int = 100  # 铁矿
    wood: int = 100  # 木材
    population: int = 1000  # 人口


@dataclass
class Combat(Component):
    """战斗组件"""

    attack_power: int = 10
    defense_power: int = 5
    accuracy: float = 0.8  # 命中率
    dodge: float = 0.1  # 闪避率
    critical_rate: float = 0.1  # 暴击率
    critical_damage: float = 1.5  # 暴击伤害倍数

    is_in_combat: bool = False
    combat_target: Optional[int] = None  # 攻击目标的实体ID


@dataclass
class AI(Component):
    """AI组件 - 人工智能行为"""

    behavior_type: str = "defensive"  # 行为类型：aggressive, defensive, balanced
    target_entity: Optional[int] = None
    patrol_points: List[Tuple[float, float]] = field(default_factory=list)
    current_patrol_index: int = 0
    decision_cooldown: float = 0.0

    # AI状态机
    state: str = "idle"  # idle, moving, attacking, defending, retreating
    state_timer: float = 0.0


@dataclass
class Renderable(Component):
    """渲染组件 - 用于图形显示"""

    sprite_name: str = "default"
    color: Tuple[int, int, int] = (255, 255, 255)  # RGB颜色
    size: Tuple[int, int] = (32, 32)  # 尺寸
    layer: int = 0  # 渲染层级
    visible: bool = True


@dataclass
class Animator(Component):
    """动画组件"""

    current_animation: str = "idle"
    animations: Dict[str, List[str]] = field(default_factory=dict)  # 动画帧
    frame_index: int = 0
    animation_speed: float = 0.1
    animation_timer: float = 0.0
    loop: bool = True


@dataclass
class StatusEffect(Component):
    """状态效果组件"""

    effects: Dict[str, float] = field(default_factory=dict)  # 效果名称: 剩余时间

    def add_effect(self, effect_name: str, duration: float):
        """添加状态效果"""
        self.effects[effect_name] = duration

    def remove_effect(self, effect_name: str):
        """移除状态效果"""
        self.effects.pop(effect_name, None)

    def has_effect(self, effect_name: str) -> bool:
        """检查是否有指定状态效果"""
        return effect_name in self.effects


@dataclass
class Experience(Component):
    """经验组件"""

    current_exp: int = 0
    level: int = 1
    exp_to_next_level: int = 100

    def add_experience(self, amount: int) -> bool:
        """添加经验，返回是否升级"""
        self.current_exp += amount
        if self.current_exp >= self.exp_to_next_level:
            self.level_up()
            return True
        return False

    def level_up(self):
        """升级"""
        self.current_exp -= self.exp_to_next_level
        self.level += 1
        self.exp_to_next_level = int(self.exp_to_next_level * 1.2)  # 升级所需经验递增


@dataclass
class Inventory(Component):
    """背包组件"""

    items: Dict[str, int] = field(default_factory=dict)  # 物品名称: 数量
    max_capacity: int = 20

    def add_item(self, item_name: str, quantity: int = 1) -> bool:
        """添加物品"""
        if len(self.items) >= self.max_capacity and item_name not in self.items:
            return False  # 背包已满

        self.items[item_name] = self.items.get(item_name, 0) + quantity
        return True

    def remove_item(self, item_name: str, quantity: int = 1) -> bool:
        """移除物品"""
        if item_name not in self.items or self.items[item_name] < quantity:
            return False

        self.items[item_name] -= quantity
        if self.items[item_name] == 0:
            del self.items[item_name]
        return True


@dataclass
class Quest(Component):
    """任务组件"""

    active_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    quest_progress: Dict[str, int] = field(default_factory=dict)

    def add_quest(self, quest_id: str):
        """添加任务"""
        if quest_id not in self.active_quests:
            self.active_quests.append(quest_id)
            self.quest_progress[quest_id] = 0

    def complete_quest(self, quest_id: str):
        """完成任务"""
        if quest_id in self.active_quests:
            self.active_quests.remove(quest_id)
            self.completed_quests.append(quest_id)
            self.quest_progress.pop(quest_id, None)


# 特殊组件标记
@dataclass
class Player(Component):
    """玩家控制标记组件"""

    player_id: int = 1


@dataclass
class NPC(Component):
    """NPC标记组件"""

    npc_type: str = "civilian"  # civilian, merchant, guard, etc.
    dialogue: List[str] = field(default_factory=list)


@dataclass
class Building(Component):
    """建筑组件"""

    building_type: str = "house"  # house, barrack, market, etc.
    construction_progress: float = 1.0  # 建造进度 (0.0-1.0)
    upgrade_level: int = 1
    functions: List[str] = field(default_factory=list)  # 建筑功能
