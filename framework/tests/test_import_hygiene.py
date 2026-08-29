"""The framework's layering, expressed as tests.

`import framework` used to construct `GameEngine` at module scope, which called
`pygame.init()` and `pygame.display.set_mode()`. Importing the ECS core opened a
window; on a machine with no display it crashed. `rotk_env/tests/conftest.py`
worked around it by exporting SDL_VIDEODRIVER before collection.

These run in subprocesses on purpose: the pytest process has almost certainly
already imported pygame via some other test, so `sys.modules` in-process proves
nothing.
"""

import subprocess
import sys

import pytest


def _run(code: str, **env_overrides) -> subprocess.CompletedProcess:
    import os

    env = {k: v for k, v in os.environ.items() if k != "SDL_VIDEODRIVER"}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_ok(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"subprocess failed\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_importing_framework_does_not_load_pygame():
    """The ECS core must be usable with no graphics stack at all."""
    _assert_ok(
        _run(
            "import sys, framework\n"
            "assert 'pygame' not in sys.modules, 'framework pulled in pygame'\n"
        )
    )


def test_importing_framework_does_not_open_a_display():
    _assert_ok(
        _run(
            "import framework\n"
            "import pygame\n"
            "assert not pygame.display.get_init(), 'a display was initialised at import time'\n"
        )
    )


def test_framework_does_not_import_repo_root_modules():
    """`framework/` must not depend upwards on its consumer's layout.

    It used to do `from performance_profiler import profiler`, a module at the
    repo root, which made the package impossible to extract or test alone.
    """
    _assert_ok(
        _run(
            "import sys\n"
            "import framework, framework.ecs.world, framework.ecs.builder\n"
            "import framework.ecs.core, framework.ecs.profiling\n"
            "assert 'performance_profiler' not in sys.modules\n"
        )
    )


def test_world_is_usable_without_pygame():
    _assert_ok(
        _run(
            "import sys\n"
            "from framework import World, Component, SingletonComponent\n"
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Pos(Component):\n"
            "    x: int = 0\n"
            "w = World()\n"
            "e = w.create_entity()\n"
            "w.add_component(e, Pos(3))\n"
            "assert w.get_component(e, Pos).x == 3\n"
            "assert w.query().with_component(Pos).entities() == {e}\n"
            "assert 'pygame' not in sys.modules\n"
        )
    )


def test_pygame_free_engine_symbols_do_not_load_pygame():
    """`framework.engine` is mixed; the pure-Python half must stay pure.

    Rule systems do `from framework.engine.events import EBS`. That must not
    initialise SDL as a side effect of running the package `__init__`.
    """
    _assert_ok(
        _run(
            "import sys\n"
            "from framework.engine import EBS, Event, QuitEvent, SceneManager\n"
            "assert 'pygame' not in sys.modules, 'the pygame-free engine half pulled in pygame'\n"
        )
    )


def test_render_symbols_do_load_pygame():
    """The flip side: asking for the renderer really does bring pygame."""
    _assert_ok(
        _run(
            "import sys\n"
            "from framework.engine import RMS\n"
            "assert 'pygame' in sys.modules\n"
        )
    )


def test_headless_engine_sets_the_dummy_driver_before_pygame_init():
    """Regression: the env var used to be set *after* `pygame.init()`.

    Passing means a machine with no display can run the headless ENV without
    the caller exporting SDL_VIDEODRIVER first.
    """
    _assert_ok(
        _run(
            "import os\n"
            "assert 'SDL_VIDEODRIVER' not in os.environ\n"
            "from framework.engine import GameEngine\n"
            "e = GameEngine(title='t', width=64, height=64)\n"
            "assert e.headless is True\n"
            "assert os.environ['SDL_VIDEODRIVER'] == 'dummy'\n"
            "assert e.screen.get_size() == (1, 1)\n",
            HEADLESS="1",
        )
    )
