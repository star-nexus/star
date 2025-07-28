"""
单位动作面板组件 - 仅负责显示和管理可执行的动作按钮
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from framework import Component


class ActionType(Enum):
    """动作类型枚举"""

    MOVE = "move"
    ATTACK = "attack"
    WAIT = "wait"
    GARRISON = "garrison"
    CAPTURE = "capture"
    FORTIFY = "fortify"


@dataclass
class UnitActionButton(Component):
    """单位动作按钮组件"""

    action_type: ActionType
    label: str
    hotkey: str = ""
    enabled: bool = True
    cost_description: str = ""  # 消耗描述，如"消耗1行动力"
    description: str = ""  # 动作描述


@dataclass
class UnitActionPanel(Component):
    """单位动作面板组件 - 仅显示动作按钮"""

    # 选中的单位
    selected_unit: Optional[int] = None

    # 可用动作按钮
    available_actions: List[UnitActionButton] = field(default_factory=list)

    # 面板显示控制
    visible: bool = False

    # 面板位置和大小（右侧显示）
    x: int = 850  # 右侧位置
    y: int = 100
    width: int = 200
    height: int = 300

    def clear(self):
        """清空面板"""
        self.selected_unit = None
        self.available_actions.clear()
        self.visible = False

    def add_action(self, action_button: UnitActionButton):
        """添加动作按钮"""
        self.available_actions.append(action_button)

    def update_available_actions(self, unit_entity: int, world):
        """更新可用动作按钮"""
        from ..components import ActionPoints, MovementPoints, Combat, HexPosition

        self.selected_unit = unit_entity
        self.available_actions.clear()

        # 获取单位组件
        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)
        position = world.get_component(unit_entity, HexPosition)

        # 移动动作
        if movement and movement.current_mp > 0:
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.MOVE,
                    label="移动",
                    hotkey="M",
                    enabled=True,
                    cost_description=f"剩余移动力: {movement.current_mp}",
                    description="移动到指定位置",
                )
            )

        # 攻击动作
        if combat and not combat.has_attacked:
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.ATTACK,
                    label="攻击",
                    hotkey="A",
                    enabled=True,
                    cost_description=f"攻击力: {combat.base_attack}",
                    description="攻击敌方单位",
                )
            )

        # 待命动作
        if action_points and action_points.can_perform_action(ActionType.WAIT):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.WAIT,
                    label="待命",
                    hotkey="W",
                    enabled=True,
                    cost_description="结束本回合行动",
                    description="结束当前单位回合",
                )
            )

        # 驻扎动作
        if action_points and action_points.can_perform_action(ActionType.GARRISON):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.GARRISON,
                    label="驻扎",
                    hotkey="G",
                    enabled=True,
                    cost_description="提升防御力",
                    description="原地驻扎，提升防御",
                )
            )

        # 占领动作（简化检查，让系统决定是否可执行）
        if (
            position
            and action_points
            and action_points.can_perform_action(ActionType.CAPTURE)
        ):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.CAPTURE,
                    label="占领",
                    hotkey="C",
                    enabled=True,
                    cost_description="占领当前地块",
                    description="占领当前位置",
                )
            )

        # 工事建设动作
        if action_points and action_points.can_perform_action(ActionType.FORTIFY):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.FORTIFY,
                    label="建设工事",
                    hotkey="F",
                    enabled=True,
                    cost_description="建设防御工事",
                    description="在当前位置建设工事",
                )
            )

        self.visible = len(self.available_actions) > 0

    def _get_territory_system(self, world):
        """获取领土系统"""
        for system in world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None


@dataclass
class ActionConfirmDialog(Component):
    """动作确认对话框组件"""

    visible: bool = False
    message: str = ""
    action_type: Optional[ActionType] = None
    target_unit: Optional[int] = None

    def show(self, message: str, action_type: ActionType, target_unit: int = None):
        """显示确认对话框"""
        self.visible = True
        self.message = message
        self.action_type = action_type
        self.target_unit = target_unit

    def hide(self):
        """隐藏确认对话框"""
        self.visible = False
        self.message = ""
        self.action_type = None
        self.target_unit = None
