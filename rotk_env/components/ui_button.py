"""
UI button components.
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Callable, Any
from framework import Component, SingletonComponent
import pygame


@dataclass
class UIButton(Component):
    """UI button component."""

    # Button geometry/content
    x: int
    y: int
    width: int
    height: int
    text: str

    # Style
    background_color: Tuple[int, int, int] = (70, 70, 70)
    hover_color: Tuple[int, int, int] = (100, 100, 100)
    text_color: Tuple[int, int, int] = (255, 255, 255)
    border_color: Tuple[int, int, int] = (150, 150, 150)
    border_width: int = 2

    # State
    is_hovered: bool = False
    is_pressed: bool = False
    is_enabled: bool = True
    is_visible: bool = True

    # Callback function name (the system resolves and invokes it by name)
    callback_name: str = ""

    # Arbitrary extra data
    data: Any = None


@dataclass
class UIButtonCollection(SingletonComponent):
    """Singleton UI button registry."""

    buttons: dict = field(default_factory=dict)  # button_id -> entity_id

    def add_button(self, button_id: str, entity_id: int):
        """Add a button mapping."""
        self.buttons[button_id] = entity_id

    def remove_button(self, button_id: str):
        """Remove a button mapping."""
        if button_id in self.buttons:
            del self.buttons[button_id]

    def get_button(self, button_id: str) -> Optional[int]:
        """Get the button entity id."""
        return self.buttons.get(button_id)


@dataclass
class UIPanel(Component):
    """UI panel component."""

    x: int
    y: int
    width: int
    height: int
    background_color: Tuple[int, int, int] = (50, 50, 50)
    border_color: Tuple[int, int, int] = (100, 100, 100)
    border_width: int = 2
    alpha: int = 200  # Opacity
    is_visible: bool = True
