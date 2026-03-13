"""
Unit action panel components.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from framework import Component, SingletonComponent
from ..prefabs.config import ActionType


@dataclass
class UnitActionButton:
    """Unit action button."""

    action_type: ActionType
    label: str
    description: str
    enabled: bool = True
    cost_description: str = ""
    hotkey: Optional[str] = None


@dataclass
class UnitActionPanel(SingletonComponent):
    """Singleton unit action panel."""

    # Panel state
    visible: bool = False
    selected_unit: Optional[int] = None

    # Panel position and size
    x: int = 10
    y: int = 100
    width: int = 250
    height: int = 400

    # Available action buttons
    available_actions: List[UnitActionButton] = field(default_factory=list)

    # Unit info to display
    unit_info: Dict[str, Any] = field(default_factory=dict)

    def clear(self):
        """Clear panel state."""
        self.visible = False
        self.selected_unit = None
        self.available_actions.clear()
        self.unit_info.clear()

    def update_unit_info(self, unit_entity: int, world):
        """Update displayed unit info."""
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

        # Fetch base unit info
        unit = world.get_component(unit_entity, Unit)
        position = world.get_component(unit_entity, HexPosition)
        unit_count = world.get_component(unit_entity, UnitCount)
        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)

        if unit:
            self.unit_info["name"] = unit.name or f"{unit.unit_type.value} Unit"
            self.unit_info["faction"] = unit.faction.value
            self.unit_info["type"] = unit.unit_type.value

        if position:
            self.unit_info["position"] = f"({position.col}, {position.row})"

        if unit_count:
            self.unit_info["soldiers"] = (
                f"{unit_count.current_count}/{unit_count.max_count}"
            )
            # "Morale" is represented as troop strength percentage.
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
        """Update available actions."""
        from ..components import ActionPoints, MovementPoints, Combat

        self.available_actions.clear()

        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)

        if not action_points:
            return

        # Move
        if movement and not movement.has_moved and movement.current_movement > 0:
            if action_points.can_perform_action(ActionType.MOVE):
                self.available_actions.append(
                    UnitActionButton(
                        action_type=ActionType.MOVE,
                        label="Move",
                        description="Move to a target tile",
                        cost_description=f"Cost: {action_points._get_action_cost(ActionType.MOVE)} AP",
                        hotkey="M",
                    )
                )

        # Attack
        if combat and not combat.has_attacked:
            if action_points.can_perform_action(ActionType.ATTACK):
                self.available_actions.append(
                    UnitActionButton(
                        action_type=ActionType.ATTACK,
                        label="Attack",
                        description="Attack an enemy unit",
                        cost_description=f"Cost: {action_points._get_action_cost(ActionType.ATTACK)} AP",
                        hotkey="A",
                    )
                )

        # Capture
        if action_points.can_perform_action(ActionType.CAPTURE):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.CAPTURE,
                    label="Capture",
                    description="Capture the current tile",
                    cost_description=f"Cost: {action_points._get_action_cost(ActionType.CAPTURE)} AP",
                    hotkey="C",
                )
            )

        # Fortify
        if action_points.can_perform_action(ActionType.FORTIFY):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.FORTIFY,
                    label="Fortify",
                    description="Construct fortifications on this tile",
                    cost_description=f"Cost: {action_points._get_action_cost(ActionType.FORTIFY)} AP",
                    hotkey="F",
                )
            )

        # Garrison
        if action_points.can_perform_action(ActionType.GARRISON):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.GARRISON,
                    label="Garrison",
                    description="Hold position and recover some morale",
                    cost_description=f"Cost: {action_points._get_action_cost(ActionType.GARRISON)} AP",
                    hotkey="G",
                )
            )

        # Wait
        if action_points.can_perform_action(ActionType.WAIT):
            self.available_actions.append(
                UnitActionButton(
                    action_type=ActionType.WAIT,
                    label="Wait",
                    description="End this unit's actions",
                    cost_description=f"Cost: {action_points._get_action_cost(ActionType.WAIT)} AP",
                    hotkey="W",
                )
            )


@dataclass
class ActionConfirmDialog(SingletonComponent):
    """Action confirmation dialog."""

    visible: bool = False
    action_type: Optional[ActionType] = None
    target_position: Optional[tuple] = None
    target_unit: Optional[int] = None
    message: str = ""

    def show_confirm(
        self, action_type: ActionType, message: str, target_pos=None, target_unit=None
    ):
        """Show the confirmation dialog."""
        self.visible = True
        self.action_type = action_type
        self.message = message
        self.target_position = target_pos
        self.target_unit = target_unit

    def hide(self):
        """Hide the dialog."""
        self.visible = False
        self.action_type = None
        self.target_position = None
        self.target_unit = None
        self.message = ""
