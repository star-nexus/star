"""
随机事件相关组件
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from framework import Component, SingletonComponent
from ..prefabs.config import TerrainType, UnitType


@dataclass
class DiceRoll(Component):
    """骰子判定组件"""

    dice_type: str = "1d6"  # 骰子类型
    threshold: int = 4  # 成功阈值
    result: Optional[int] = None  # 投掷结果
    success: Optional[bool] = None  # 是否成功

    def roll(self) -> bool:
        """执行骰子投掷"""
        import random

        if self.dice_type == "1d6":
            self.result = random.randint(1, 6)
        self.success = self.result >= self.threshold
        return self.success


@dataclass
class TerrainEvent(Component):
    """地形事件组件"""

    terrain_type: TerrainType
    event_name: str
    trigger_condition: str  # 触发条件描述
    effect_description: str  # 效果描述
    dice_threshold: int = 4  # 默认阈值

    def can_trigger(self, unit_type: UnitType, action: str) -> bool:
        """检查是否可以触发事件"""
        # 根据地形和单位类型判断
        terrain_triggers = {
            TerrainType.PLAIN: {"cavalry": ["move_end"]},
            TerrainType.MOUNTAIN: {"any": ["enter"]},
            TerrainType.URBAN: {"archer": ["garrison"]},
            TerrainType.WATER: {"ship": ["move_start"]},
            TerrainType.FOREST: {"any": ["enter"]},
            TerrainType.HILL: {"archer": ["attack"]},
        }

        triggers = terrain_triggers.get(self.terrain_type, {})
        return action in triggers.get("any", []) or action in triggers.get(
            unit_type.value, []
        )


@dataclass
class UnitSkillEvent(Component):
    """单位技能事件组件"""

    skill_name: str
    unit_type: UnitType
    count_requirement: float  # 人数要求（比例）
    success_effect: str  # 成功效果
    failure_effect: str  # 失败效果
    dice_threshold: int = 4
    cooldown: int = 0  # 冷却回合数


@dataclass
class RandomEventQueue(SingletonComponent):
    """随机事件队列单例"""

    pending_events: List[Dict] = field(default_factory=list)
    processed_events: List[Dict] = field(default_factory=list)

    def add_event(self, event_type: str, entity_id: int, data: Dict):
        """添加事件到队列"""
        event = {
            "type": event_type,
            "entity": entity_id,
            "data": data,
            "processed": False,
        }
        self.pending_events.append(event)

    def process_next_event(self) -> Optional[Dict]:
        """处理下一个事件"""
        if self.pending_events:
            event = self.pending_events.pop(0)
            event["processed"] = True
            self.processed_events.append(event)
            return event
        return None

    def clear_processed(self):
        """清理已处理的事件"""
        self.processed_events.clear()


@dataclass
class CombatRoll(Component):
    """战斗投掷组件"""

    hit_roll: Optional[int] = None  # 命中投掷
    damage_roll: Optional[int] = None  # 伤害投掷
    crit_roll: Optional[int] = None  # 暴击投掷

    hit_threshold: int = 1  # 命中阈值
    crit_threshold: int = 19  # 暴击阈值

    def roll_hit(self) -> bool:
        """投掷命中"""
        import random

        self.hit_roll = random.randint(1, 20)
        return self.hit_roll >= self.hit_threshold

    def roll_crit(self) -> bool:
        """投掷暴击"""
        import random

        self.crit_roll = random.randint(1, 20)
        return self.crit_roll >= self.crit_threshold

    def apply_forest_penalty(self):
        """应用森林命中率惩罚"""
        # 森林中远程命中率-5%，相当于提高阈值
        if self.hit_roll is not None:
            # 模拟5%惩罚，大约相当于+1阈值
            self.hit_threshold = min(20, self.hit_threshold + 1)
