"""The ENV's headless eval path must not need a graphics stack.

`display="none"` mounts no render system, so it should not pay for one. Two
things used to break that: `rotk_env/systems/__init__.py` was an eager barrel
that imported every render system, and `world_builder` imported them at module
scope even though it only mounts them for `"dummy"`/`"window"`.

Subprocesses on purpose: the pytest process has already imported pygame via
other tests, so an in-process `sys.modules` check proves nothing.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(code: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "SDL_VIDEODRIVER"}
    env["PYTHONPATH"] = REPO_ROOT
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, (
        f"subprocess failed\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return result


def test_importing_one_system_does_not_import_the_render_stack():
    _run(
        "import sys\n"
        "from rotk_env.systems.llm_action_handler import LLMActionHandler\n"
        "assert 'pygame' not in sys.modules, 'the systems barrel dragged in pygame'\n"
    )


def test_headless_world_build_does_not_import_pygame():
    """The eval path: no display, no SDL, no window."""
    _run(
        "import sys\n"
        "from rotk_env.prefabs.world_builder import build_skirmish_world\n"
        "w = build_skirmish_world(display='none')\n"
        "assert 'pygame' not in sys.modules, 'headless build pulled in pygame'\n"
        "assert w.systems, 'no systems mounted'\n"
    )


def test_headless_world_build_mounts_no_render_system():
    _run(
        "from rotk_env.prefabs.world_builder import build_skirmish_world\n"
        "w = build_skirmish_world(display='none')\n"
        "names = [type(s).__name__ for s in w.systems]\n"
        "bad = [n for n in names if 'Render' in n or n in ('AnimationSystem', 'InputHandlingSystem', 'MiniMapSystem', 'UIButtonSystem')]\n"
        "assert not bad, f'display=none mounted display systems: {bad}'\n"
    )


def test_component_layer_is_pure_data():
    """Components are data; they have no business importing a display library."""
    _run(
        "import sys, rotk_env.components\n"
        "assert 'pygame' not in sys.modules, 'the component layer imports pygame'\n"
    )


def test_display_builds_still_work():
    """The flip side: asking for a display must still assemble."""
    _run(
        "import os\n"
        "os.environ['SDL_VIDEODRIVER'] = 'dummy'\n"
        "import pygame\n"
        "pygame.init()\n"
        "pygame.display.set_mode((64, 64))\n"
        "from rotk_env.prefabs.world_builder import build_skirmish_world\n"
        "w = build_skirmish_world(display='dummy')\n"
        "names = {type(s).__name__ for s in w.systems}\n"
        "assert 'AnimationSystem' in names and 'InputHandlingSystem' in names, names\n"
    )
