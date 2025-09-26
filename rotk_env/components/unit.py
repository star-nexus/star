"""
单位相关组件
"""

from dataclasses import dataclass, field
from typing import Set, Optional, Dict
from framework import Component
from ..prefabs.config import UnitType, Faction, UnitState, ActionType


@dataclass
class Unit(Component):
    """单位组件"""

    unit_type: UnitType
    faction: Faction
    name: str = ""
    level: int = 1
    experience: int = 0


@dataclass
class UnitCount(Component):
    """单位人数组件"""

    current_count: int = 100  # 当前人数
    max_count: int = 100  # 满编人数

    @property
    def ratio(self) -> float:
        """人数比例"""
        return self.current_count / self.max_count if self.max_count > 0 else 0.0

    @property
    def percentage(self) -> float:
        """人数百分比"""
        return self.ratio * 100

    def is_decimated(self) -> bool:
        """是否已经残破（人数<=10%）"""
        return self.ratio <= 0.1


@dataclass
class UnitStatus(Component):
    """单位状态组件"""

    current_status: UnitState = UnitState.NORMAL
    status_duration: int = 0  # 状态持续回合数
    wait_turns: int = 0  # 连续待命回合数
    charge_stacks: int = 0  # 冲势层数


@dataclass
class Movement(Component):
    """移动组件"""

    base_movement: int  # 基础移动力
    current_movement: int  # 当前移动力
    has_moved: bool = False

    def get_effective_movement(self, unit_count: UnitCount) -> int:
        """获取考虑人数的有效移动力"""
        # 每少20%人数移动力-1（最低1）
        ratio = unit_count.ratio
        penalty = max(0, int((1 - ratio) / 0.2))
        return max(1, self.base_movement - penalty)


@dataclass
class Combat(Component):
    """战斗组件"""

    base_attack: int  # 基础攻击
    base_defense: int  # 基础防御
    attack_range: int = 1
    has_attacked: bool = False

    def get_effective_stats(
        self, unit_count: UnitCount, status: UnitStatus, terrain_coeff: float = 1.0
    ) -> tuple:
        """获取考虑人数、状态和地形的有效攻防"""
        from ..prefabs.config import GameConfig

        # 动态攻防公式：基础值 × (N/M)^0.7 × 状态系数 × 地形系数
        ratio = unit_count.ratio
        attack_modifier = ratio**0.3
        defense_modifier = 1.0
        status_modifier = GameConfig.STATE_COEFFICIENTS.get(status.current_status, 1.0)

        effective_attack = (
            self.base_attack * attack_modifier * status_modifier * terrain_coeff
        )
        effective_defense = (
            self.base_defense * defense_modifier * status_modifier * terrain_coeff
        )

        return int(effective_attack), int(effective_defense)


@dataclass
class Vision(Component):
    """视野组件"""

    range: int
    visible_tiles: Set[tuple] = field(default_factory=set)


@dataclass
class Selected(Component):
    """选中状态组件"""

    selected: bool = True


@dataclass
class AIControlled(Component):
    """AI控制组件"""

    difficulty: str = "normal"
    last_action_time: float = 0.0


@dataclass
class UnitSkills(Component):
    """单位技能组件"""

    available_skills: Set[str] = field(default_factory=set)
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)  # 技能冷却时间

    def can_use_skill(self, skill_name: str) -> bool:
        """检查是否可以使用技能"""
        return (
            skill_name in self.available_skills
            and self.skill_cooldowns.get(skill_name, 0) <= 0
        )

    def use_skill(self, skill_name: str, cooldown: int = 0):
        """使用技能"""
        if skill_name in self.available_skills:
            self.skill_cooldowns[skill_name] = cooldown


@dataclass
class ActionPoints(Component):
    """行动力组件"""

    current_ap: int = 2  # 当前行动力
    max_ap: int = 2  # 最大行动力

    def can_perform_action(self, action_type: ActionType) -> bool:
        """检查是否有足够行动力执行动作"""
        cost = self._get_action_cost(action_type)
        return self.current_ap >= cost

    def consume_ap(self, action_type: ActionType) -> bool:
        """消耗行动力"""
        cost = self._get_action_cost(action_type)
        if self.current_ap >= cost:
            self.current_ap -= cost
            return True
        return False

    def _get_action_cost(self, action_type: ActionType) -> int:
        """获取动作消耗的行动点（决策层级）"""
        action_costs = {
            # ActionType.MOVE: 1,  # 移动决策：固定1点
            ActionType.ATTACK: 1,  # 攻击决策：固定1点
            ActionType.GARRISON: 1,  # 驻扎决策：固定1点
            ActionType.REST: 0,  # 待命：无消耗
            ActionType.SKILL: 1,  # 技能决策：固定1点
            ActionType.OCCUPY: 1,  # 占领决策：固定1点
            ActionType.FORTIFY: 1,  # 建造决策：固定1点
        }
        return action_costs.get(action_type, 1)

    def reset(self):
        """重置行动力（回合开始时）"""
        self.current_ap = self.max_ap
