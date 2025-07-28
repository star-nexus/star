"""
单位行动面板组件
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from framework import Component, SingletonComponent
from ..prefabs.config import ActionType


@dataclass
class UnitActionButton:
    """单位行动按钮"""

    action_type: ActionType
    label: str
    description: str
    enabled: bool = True
    cost_description: str = ""
    hotkey: Optional[str] = None


@dataclass
class UnitActionPanel(SingletonComponent):
    """单位行动面板单例组件"""

    # 面板状态
    visible: bool = False
    selected_unit: Optional[int] = None

    # 面板位置和大小
    x: int = 10
    y: int = 100
    width: int = 250
    height: int = 400

    # 可用行动按钮
    available_actions: List[UnitActionButton] = field(default_factory=list)

    # 单位信息显示
    unit_info: Dict[str, Any] = field(default_factory=dict)

    def clear(self):
        """清空面板"""
        self.visible = False
        self.selected_unit = None
        self.available_actions.clear()
        self.unit_info.clear()

    def update_unit_info(self, unit_entity: int, world):
        """更新单位信息"""
        from ..components import (
            Unit,
            HexPosition,
            UnitCount,
            ActionPoints,
            MovementPoints,
            Combat,
        )

        self.selected_unit = unit_entity
        self.unit_info.clear()

        # 获取单位基本信息
        unit = world.get_component(unit_entity, Unit)
        position = world.get_component(unit_entity, HexPosition)
        unit_count = world.get_component(unit_entity, UnitCount)
        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)

        if unit:
            self.unit_info["name"] = unit.name or f"{unit.unit_type.value}部队"
            self.unit_info["faction"] = unit.faction.value
            self.unit_info["type"] = unit.unit_type.value

        if position:
            self.unit_info["position"] = f"({position.col}, {position.row})"

        if unit_count:
            self.unit_info["soldiers"] = (
                f"{unit_count.current_count}/{unit_count.max_count}"
            )
            # 计算"士气"为兵力比例百分比
            morale_percentage = unit_count.percentage
            self.unit_info["morale"] = f"{morale_percentage:.1f}%"
            self.unit_info["is_decimated"] = unit_count.is_decimated()

        if action_points:
            self.unit_info["action_points"] = (
                f"{action_points.current_ap}/{action_points.max_ap}"
            )

        if movement:
            self.unit_info["movement"] = (
                f"{movement.current_movement}/{movement.base_movement}"
            )
            self.unit_info["has_moved"] = movement.has_moved

        if combat:
            self.unit_info["attack"] = combat.base_attack
            self.unit_info["defense"] = combat.base_defense
            self.unit_info["range"] = combat.attack_range
            self.unit_info["has_attacked"] = combat.has_attacked

    def update_available_actions(self, unit_entity: int, world):
        """更新可用行动"""
        from ..components import ActionPoints, MovementPoints, Combat

        self.available_actions.clear()

        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)

        if not action_points:
            return

        # 移动行动
        if movement and not movement.has_moved and movement.current_movement > 0:
            if action_points.can_perform_action(ActionType.MOVE):
                self.available_actions.append(
                    UnitActionButton(
                        action_type=ActionType.MOVE,
                        label="移动",
                        description="移动到指定位置",
                        cost_description=f"消耗: {action_points._get_action_cost(ActionType.MOVE)} AP",
                        hotkey="M",
                    )
                )

        # 攻击行动
        if combat and not combat.has_attacked:
            if action_points.can_perform_action(ActionType.ATTACK):
                self.available_actions.append(
                    UnitActionButton(
                        action_type=ActionType.ATTACK,
                        label="攻击",
                        description="攻击敌方单位",
                        cost_description=f"消耗: {action_points._get_action_cost(ActionType.ATTACK)} AP",
                        hotkey="A",
                    )
                )

        # 占领行动
        if action_points.can_perform_action(ActionType.CAPTURE):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.CAPTURE,
                    label="占领",
                    description="占领当前地块",
                    cost_description=f"消耗: {action_points._get_action_cost(ActionType.CAPTURE)} AP",
                    hotkey="C",
                )
            )

        # 工事建设
        if action_points.can_perform_action(ActionType.FORTIFY):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.FORTIFY,
                    label="建设工事",
                    description="在当前位置建设防御工事",
                    cost_description=f"消耗: {action_points._get_action_cost(ActionType.FORTIFY)} AP",
                    hotkey="F",
                )
            )

        # 驻扎行动
        if action_points.can_perform_action(ActionType.GARRISON):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.GARRISON,
                    label="驻扎",
                    description="原地驻扎，恢复部分士气",
                    cost_description=f"消耗: {action_points._get_action_cost(ActionType.GARRISON)} AP",
                    hotkey="G",
                )
            )

        # 待命行动
        if action_points.can_perform_action(ActionType.WAIT):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.WAIT,
                    label="待命",
                    description="结束单位行动",
                    cost_description=f"消耗: {action_points._get_action_cost(ActionType.WAIT)} AP",
                    hotkey="W",
                )
            )


@dataclass
class ActionConfirmDialog(SingletonComponent):
    """行动确认对话框"""

    visible: bool = False
    action_type: Optional[ActionType] = None
    target_position: Optional[tuple] = None
    target_unit: Optional[int] = None
    message: str = ""

    def show_confirm(
        self, action_type: ActionType, message: str, target_pos=None, target_unit=None
    ):
        """显示确认对话框"""
        self.visible = True
        self.action_type = action_type
        self.message = message
        self.target_position = target_pos
        self.target_unit = target_unit

    def hide(self):
        """隐藏对话框"""
        self.visible = False
        self.action_type = None
        self.target_position = None
        self.target_unit = None
        self.message = ""
