"""
Unit action panel component (display and manage executable action buttons).
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from framework import Component


class ActionType(Enum):
    """Action type enum."""

    MOVE = "move"
    ATTACK = "attack"
    WAIT = "wait"
    GARRISON = "garrison"
    CAPTURE = "capture"
    FORTIFY = "fortify"


@dataclass
class UnitActionButton(Component):
    """Unit action button component."""

    action_type: ActionType
    label: str
    hotkey: str = ""
    enabled: bool = True
    cost_description: str = ""  # Cost hint, e.g. "Costs 1 AP"
    description: str = ""  # Action description


@dataclass
class UnitActionPanel(Component):
    """Unit action panel component (buttons-only)."""

    # Selected unit
    selected_unit: Optional[int] = None

    # Available action buttons
    available_actions: List[UnitActionButton] = field(default_factory=list)

    # Visibility
    visible: bool = False

    # Panel position and size (right side)
    x: int = 850  # Right-side x position
    y: int = 100
    width: int = 200
    height: int = 300

    def clear(self):
        """Clear the panel state."""
        self.selected_unit = None
        self.available_actions.clear()
        self.visible = False

    def add_action(self, action_button: UnitActionButton):
        """Add an action button."""
        self.available_actions.append(action_button)

    def update_available_actions(self, unit_entity: int, world):
        """Rebuild available action buttons for the selected unit."""
        from ..components import ActionPoints, MovementPoints, Combat, HexPosition

        self.selected_unit = unit_entity
        self.available_actions.clear()

        # Fetch unit components
        action_points = world.get_component(unit_entity, ActionPoints)
        movement = world.get_component(unit_entity, MovementPoints)
        combat = world.get_component(unit_entity, Combat)
        position = world.get_component(unit_entity, HexPosition)

        # Move
        if movement and movement.current_mp > 0:
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.MOVE,
                    label="Move",
                    hotkey="M",
                    enabled=True,
                    cost_description=f"Movement Points: {movement.current_mp}",
                    description="Move to a target tile",
                )
            )

        # Attack
        if combat and not combat.has_attacked:
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.ATTACK,
                    label="Attack",
                    hotkey="A",
                    enabled=True,
                    cost_description=f"Attack: {combat.base_attack}",
                    description="Attack an enemy unit",
                )
            )

        # Wait
        if action_points and action_points.can_perform_action(ActionType.WAIT):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.WAIT,
                    label="Wait",
                    hotkey="W",
                    enabled=True,
                    cost_description="End this unit's turn",
                    description="Finish this unit's actions for the turn",
                )
            )

        # Garrison
        if action_points and action_points.can_perform_action(ActionType.GARRISON):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.GARRISON,
                    label="Garrison",
                    hotkey="G",
                    enabled=True,
                    cost_description="Gain a defense bonus",
                    description="Hold position and increase defense",
                )
            )

        # Capture (simplified check; the system decides executability)
        if (
            position
            and action_points
            and action_points.can_perform_action(ActionType.CAPTURE)
        ):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.CAPTURE,
                    label="Capture",
                    hotkey="C",
                    enabled=True,
                    cost_description="Capture the current tile",
                    description="Capture your current position",
                )
            )

        # Fortify
        if action_points and action_points.can_perform_action(ActionType.FORTIFY):
            self.add_action(
                UnitActionButton(
                    action_type=ActionType.FORTIFY,
                    label="Fortify",
                    hotkey="F",
                    enabled=True,
                    cost_description="Build fortifications",
                    description="Construct fortifications on this tile",
                )
            )

        self.visible = len(self.available_actions) > 0

    def _get_territory_system(self, world):
        """Get the territory system, if present."""
        for system in world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None


@dataclass
class ActionConfirmDialog(Component):
    """Action confirmation dialog component."""

    visible: bool = False
    message: str = ""
    action_type: Optional[ActionType] = None
    target_unit: Optional[int] = None

    def show(self, message: str, action_type: ActionType, target_unit: int = None):
        """Show the confirmation dialog."""
        self.visible = True
        self.message = message
        self.action_type = action_type
        self.target_unit = target_unit

    def hide(self):
        """Hide the confirmation dialog."""
        self.visible = False
        self.message = ""
        self.action_type = None
        self.target_unit = None
