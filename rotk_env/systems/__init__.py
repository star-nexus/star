"""Game systems.

Resolution is lazy (PEP 562). A flat barrel of eager imports meant that pulling
in a single rule system dragged the whole render stack -- and therefore pygame
and SDL -- into the process. The headless eval path (`display="none"`) mounts no
render system at all, so it should never pay for one.

Attribute access still works exactly as before: `from rotk_env.systems import
LLMSystem` imports only `llm_system`.
"""

from importlib import import_module
from typing import Any, Dict

# name -> defining module (relative to this package)
_EXPORTS: Dict[str, str] = {
    # --- rules / simulation ---
    "MapSystem": "map_system",
    "TurnSystem": "turn_system",
    "RealtimeSystem": "realtime_system",
    "MovementSystem": "movement_system",
    "CombatSystem": "combat_system",
    "VisionSystem": "vision_system",
    "TerritorySystem": "territory_system",
    "GameOverPolicy": "game_over_policy",
    # --- agent interface ---
    "LLMSystem": "llm_system",
    "LLMActionHandler": "llm_action_handler",
    "LLMObservationSystem": "llm_observation_system",
    "MockLLMAISystem": "mock_llm_ai_system",
    # --- display-dependent (import pygame) ---
    "InputHandlingSystem": "input_system",
    "AnimationSystem": "animation_system",
    "MiniMapSystem": "minimap_system",
    "UnitActionButtonSystem": "unit_action_button_system",
    "GameOverRenderSystem": "game_over_render_system",
    "MapRenderSystem": "map_render_system",
    "UnitRenderSystem": "unit_render_system",
    "UIRenderSystem": "ui_render_system",
    "EffectRenderSystem": "effect_render_system",
    "PanelRenderSystem": "panel_render_system",
    "UIButtonSystem": "ui_button_system",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from None
    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value  # cache so later lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return __all__
