"""
游戏系统模块
"""

from .map_system import MapSystem
from .turn_system import TurnSystem
from .realtime_system import RealtimeSystem
from .movement_system import MovementSystem
from .combat_system import CombatSystem
from .vision_system import VisionSystem
from .ai_system import AISystem
from .input_system import InputHandlingSystem
from .minimap_system import MiniMapSystem
from .animation_system import AnimationSystem
from .game_over_render_system import GameOverRenderSystem
from .llm_system import LLMSystem
from .llm_action_handler import LLMActionHandler
from .llm_observation_system import LLMObservationSystem

# 渲染系统拆分为多个独立系统
from .map_render_system import MapRenderSystem
from .unit_render_system import UnitRenderSystem
from .ui_render_system import UIRenderSystem
from .effect_render_system import EffectRenderSystem
from .panel_render_system import PanelRenderSystem
from .ui_button_system import UIButtonSystem

__all__ = [
    "AnimationSystem",
    "MapSystem",
    "TurnSystem",
    "RealtimeSystem",
    "MovementSystem",
    "CombatSystem",
    "VisionSystem",
    "AISystem",
    "InputHandlingSystem",
    "MiniMapSystem",
    "LLMSystem",
    "LLMActionHandler",
    "LLMObservationSystem",
    # 新的渲染系统
    "MapRenderSystem",
    "UnitRenderSystem",
    "UIRenderSystem",
    "EffectRenderSystem",
    "PanelRenderSystem",
    "GameOverRenderSystem",
    "UIButtonSystem",
]
