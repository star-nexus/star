"""
多层次资源系统组件
按照MULTILAYER_RESOURCE_SYSTEM_DESIGN.md设计实现
"""

from dataclasses import dataclass, field
from typing import Dict, Set
from framework import Component
from ..prefabs.config import ActionType


@dataclass
class ActionPoints(Component):
    """行动点 - 决策层级控制"""

    current_ap: int = 2  # 当前行动点
    max_ap: int = 2  # 最大行动点

    def can_perform_action(self, action_type: ActionType) -> bool:
        """检查是否有足够行动点执行决策"""
        cost = self._get_action_cost(action_type)
        return self.current_ap >= cost

    def consume_ap(self, action_type: ActionType) -> bool:
        """消耗行动点"""
        cost = self._get_action_cost(action_type)
        if self.current_ap >= cost:
            self.current_ap -= cost
            return True
        return False

    def _get_action_cost(self, action_type: ActionType) -> int:
        """获取决策消耗的行动点（决策层级）"""
        action_costs = {
            ActionType.MOVE: 1,  # 移动决策：固定1点
            ActionType.ATTACK: 1,  # 攻击决策：固定1点
            ActionType.REST: 1,  # 休整：固定1点
            ActionType.SKILL: 1,  # 技能决策：固定1点
            ActionType.OCCUPY: 1,  # 占领决策：固定1点
            ActionType.FORTIFY: 1,  # 建造决策：固定1点
        }
        return action_costs.get(action_type, 1)

    def reset(self):
        """重置行动点（回合开始时）"""
        self.current_ap = self.max_ap


@dataclass
class MovementPoints(Component):
    """移动力点数 - 移动执行层"""

    current_mp: int = 3  # 当前移动力
    max_mp: int = 3  # 最大移动力（基于单位类型）
    base_mp: int = 3  # 基础移动力
    has_moved: bool = False  # 是否已移动

    def get_effective_movement(self, unit_count) -> int:
        """获取考虑人数的有效移动力"""
        # 每少20%人数移动力-1（最低1）
        ratio = unit_count.ratio if unit_count else 1.0
        penalty = max(0, int((1 - ratio) / 0.2))
        return max(1, self.base_mp - penalty)

    def can_move(self, cost: int) -> bool:
        """检查是否有足够移动力"""
        return self.current_mp >= cost

    def consume_movement(self, cost: int) -> bool:
        """消耗移动力"""
        if self.current_mp >= cost:
            self.current_mp -= cost
            self.has_moved = True
            return True
        return False

    def reset(self):
        """重置移动力（回合开始时）"""
        self.current_mp = self.max_mp
        self.has_moved = False


@dataclass
class AttackPoints(Component):
    """攻击点数 - 攻击执行层"""

    normal_attacks: int = 1  # 普通攻击次数
    max_normal_attacks: int = 1  # 最大普通攻击次数
    skill_points: int = 2  # 技能点数
    max_skill_points: int = 2  # 最大技能点数

    def can_normal_attack(self) -> bool:
        """检查是否可以普通攻击"""
        return self.normal_attacks > 0

    def can_use_skill(self, skill_cost: int) -> bool:
        """检查是否可以使用技能"""
        return self.skill_points >= skill_cost

    def consume_normal_attack(self) -> bool:
        """消耗普通攻击次数"""
        if self.normal_attacks > 0:
            self.normal_attacks -= 1
            return True
        return False

    def consume_skill_points(self, cost: int) -> bool:
        """消耗技能点数"""
        if self.skill_points >= cost:
            self.skill_points -= cost
            return True
        return False

    def reset_normal_attacks(self):
        """重置普通攻击次数（每回合自动）"""
        self.normal_attacks = self.max_normal_attacks

    def restore_skill_points(self):
        """恢复技能点数（需要休整动作）"""
        self.skill_points = self.max_skill_points


@dataclass
class ConstructionPoints(Component):
    """建造点数 - 建造执行层"""

    current_cp: int = 3  # 当前建造点（根据文档修改为3）
    max_cp: int = 3  # 最大建造点

    def can_build(self, cost: int) -> bool:
        """检查是否可以建造"""
        return self.current_cp >= cost

    def consume_construction(self, cost: int) -> bool:
        """消耗建造点数"""
        if self.current_cp >= cost:
            self.current_cp -= cost
            return True
        return False

    def restore_to_city(self):
        """在城市根据地恢复建造点数"""
        self.current_cp = self.max_cp


@dataclass
class SkillPoints(Component):
    """技能点数 - 技能执行层（独立于攻击点的技能点）"""

    current_sp: int = 3  # 当前技能点
    max_sp: int = 3  # 最大技能点
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)  # 技能冷却

    def can_use_skill(self, skill_name: str, cost: int = 1) -> bool:
        """检查是否可以使用技能"""
        if skill_name in self.skill_cooldowns and self.skill_cooldowns[skill_name] > 0:
            return False
        return self.current_sp >= cost

    def use_skill(self, skill_name: str, cost: int = 1, cooldown: int = 0) -> bool:
        """使用技能"""
        if self.can_use_skill(skill_name, cost):
            self.current_sp -= cost
            if cooldown > 0:
                self.skill_cooldowns[skill_name] = cooldown
            return True
        return False

    def restore_by_rest(self):
        """通过休整恢复技能点数"""
        self.current_sp = self.max_sp

    def update_cooldowns(self):
        """更新冷却时间（每回合调用）"""
        for skill_name in list(self.skill_cooldowns.keys()):
            self.skill_cooldowns[skill_name] -= 1
            if self.skill_cooldowns[skill_name] <= 0:
                del self.skill_cooldowns[skill_name]


# 为了向后兼容，保留原有的组件别名
# Movement = MovementPoints
