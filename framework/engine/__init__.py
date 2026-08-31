"""Framework runtime: scenes, events, input, rendering, and the main loop.

Resolution is lazy (PEP 562) because this package is *mixed*: `events`,
`engine_event` and `scenes` are pure Python, while `renders`, `inputs` and
`game_engine` need pygame. An eager barrel made `from framework.engine.events
import EBS` -- which rule systems like CombatSystem do -- initialise SDL as a
side effect of running this package's `__init__`.

With lazy resolution you pay for pygame only when you ask for something that
needs it (`RMS`, `IPS`, `GameEngine`).

Nothing here initialises a display; constructing `GameEngine` does.
"""

from importlib import import_module
from typing import Any, Dict

# name -> defining module (relative to this package)
_EXPORTS: Dict[str, str] = {
    # --- pygame-free ---
    "EventBus": "events",
    "Event": "events",
    "EBS": "events",
    "SceneManager": "scenes",
    "Scene": "scenes",
    "SMS": "scenes",
    "QuitEvent": "engine_event",
    "KeyDownEvent": "engine_event",
    "KeyUpEvent": "engine_event",
    "MouseButtonDownEvent": "engine_event",
    "MouseButtonUpEvent": "engine_event",
    "MouseMotionEvent": "engine_event",
    "MouseWheelEvent": "engine_event",
    "WindowResizeEvent": "engine_event",
    # --- require pygame ---
    "RenderEngine": "renders",
    "RMS": "renders",
    "InputSystem": "inputs",
    "IPS": "inputs",
    "GameEngine": "game_engine",
    "get_engine": "game_engine",
    "reset_engine": "game_engine",
    "DEFAULT_FPS": "game_engine",
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
