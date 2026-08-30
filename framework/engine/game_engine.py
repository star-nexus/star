import pygame
import time
import sys
import os
import tomllib
from typing import Any, Optional

from .scenes import SceneManager
from .renders import RenderEngine
from .inputs import InputSystem
from .events import EventBus
from ..ecs.world import World
from ..ecs import profiling
from .engine_event import QuitEvent, WindowResizeEvent

# Eval and interactive play share this cap. Real-time AP/MP recover from
# fixed 1/FPS seconds per frame, so a 30fps loop would recover at half
# the intended rate. Do not lower this without changing recovery intervals.
DEFAULT_FPS = 60
MIN_WINDOW_WIDTH = 1200
MIN_WINDOW_HEIGHT = 800


class GameEngine:
    """Game engine - runs the main loop and core managers.

    One instance per process (managers below are module-level singletons that
    the engine wires to a single screen). Construction initialises SDL, so it is
    never done at import time -- use `get_engine()` or construct explicitly.
    """

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        title: str = "Game",
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: int = DEFAULT_FPS,
    ):
        """Initialize the game engine."""
        if hasattr(self, "_initialized"):
            # Already built for this process. Only FPS is re-pinnable, because
            # real-time AP/MP recovery is defined per frame. Headless mode
            # cannot change after SDL is up; a live window can still resize.
            if fps != self.fps:
                self.fps = fps
            return

        # Load config to check for headless mode
        self.headless = False
        try:
            # Check environment variable first
            env_headless = os.environ.get("HEADLESS")
            if env_headless is not None:
                self.headless = env_headless.lower() in ("1", "true", "yes", "on")
            else:
                config_path = ".configs.toml"
                if os.path.exists(config_path):
                    with open(config_path, "rb") as f:
                        config = tomllib.load(f)
                        self.headless = config.get("default", {}).get("headless", False)
        except Exception as e:
            print(f"Warning: Failed to load config for headless mode: {e}")

        if self.headless:
            print("Running in HEADLESS mode")

        # Basic configuration
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.delta_time = 0.0

        # Initialize Pygame
        self._init_pygame()

        # self._init_world()

        # Initialize managers
        self._init_managers()

        self._initialized = True

    def _init_pygame(self) -> None:
        """Initialize Pygame context and screen."""
        # SDL reads SDL_VIDEODRIVER while initialising its video subsystem, so
        # this has to happen *before* pygame.init(). Setting it afterwards left
        # headless runs on the real driver -- which crashes on a machine with no
        # display, and was only survivable because the shell wrapper and the
        # test conftest exported the variable externally.
        if self.headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

        pygame.init()

        if self.headless:
            # Minimal surface: render systems still need a blit target.
            self.width = self.width or MIN_WINDOW_WIDTH
            self.height = self.height or MIN_WINDOW_HEIGHT
            self.screen = pygame.display.set_mode((1, 1))
        else:
            self.width, self.height = self._choose_window_size(self.width, self.height)
            self.screen = pygame.display.set_mode(
                (self.width, self.height), pygame.RESIZABLE
            )
            pygame.display.set_caption(self.title)

        self.clock = pygame.time.Clock()

    def _choose_window_size(
        self, width: Optional[int], height: Optional[int]
    ) -> tuple[int, int]:
        """Grow to the desktop when the caller does not pin a size."""
        min_w, min_h = MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
        if width and height:
            return width, height
        info = pygame.display.Info()
        desktop_w = int(getattr(info, "current_w", 0) or 0)
        desktop_h = int(getattr(info, "current_h", 0) or 0)
        auto_w = min_w
        auto_h = min_h
        if desktop_w >= min_w and desktop_h >= min_h:
            auto_w = max(min_w, desktop_w - 80)
            auto_h = max(min_h, desktop_h - 100)
        return width or auto_w, height or auto_h

    def _init_managers(self) -> None:
        """Initialize manager singletons and wire them up."""
        # Get singletons
        self.event_manager = EventBus()
        self.scene_manager = SceneManager()
        self.scene_manager.set_engine(self)
        self.render_manager = RenderEngine()
        self.render_manager.screen = self.screen  # set render target
        self.input_manager = InputSystem()

        self.subscribe_events()

    def start(self) -> None:
        """Start the engine (blocking)."""
        self.run()

    def run(self) -> None:
        """Run the main game loop.

        Simulation uses a fixed timestep of 1/FPS, not wall-clock frame
        jitter. ``clock.tick`` caps the loop at FPS so one wall-clock
        second of LLM think time is about FPS sim frames (and thus the
        intended AP/MP recovery) as long as the machine keeps up.
        """
        self.running = True
        frame_dt = 1.0 / float(self.fps)

        try:
            while self.running:
                self.delta_time = frame_dt
                self._update()
                self.clock.tick(self.fps)

        except KeyboardInterrupt:
            print("Game interrupted by user")
        finally:
            self.quit()

    def subscribe_events(self) -> None:
        """Subscribe event handlers."""

        self.event_manager.subscribe(QuitEvent, self.stop)
        self.event_manager.subscribe(WindowResizeEvent, self._on_window_resize)

    def _on_window_resize(self, event: WindowResizeEvent) -> None:
        if self.headless:
            return
        requested_w = int(event.width)
        requested_h = int(event.height)
        width = max(MIN_WINDOW_WIDTH, requested_w)
        height = max(MIN_WINDOW_HEIGHT, requested_h)
        self.width = width
        self.height = height
        # pygame 2 already resized the window; calling set_mode again can
        # emit a second VIDEORESIZE and recurse. Only snap back when the
        # user dragged below the 1200×800 floor.
        if requested_w < MIN_WINDOW_WIDTH or requested_h < MIN_WINDOW_HEIGHT:
            self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        else:
            surface = pygame.display.get_surface()
            if surface is not None:
                self.screen = surface
        if self.render_manager is not None:
            self.render_manager.screen = self.screen

    def _update(self) -> None:
        """Update one frame of game logic and rendering."""
        profiler = profiling.profiler
        profiler.start_frame()

        if not self.headless:
            with profiler.time_system("screen_fill"):
                self.screen.fill((135, 141, 106))  # clear screen

        with profiler.time_system("input_system"):
            self.input_manager.update()

        with profiler.time_system("scene_update"):
            self.scene_manager.update(self.delta_time)

        if not self.headless:
            with profiler.time_system("render_engine"):
                self.render_manager.update()

            with profiler.time_system("display_flip"):
                pygame.display.flip()

        # Print profiling stats every ~5 seconds
        if hasattr(self, '_last_stats_time'):
            if time.time() - self._last_stats_time > 5.0:
                profiler.print_stats()
                self._last_stats_time = time.time()
        else:
            self._last_stats_time = time.time()

    def stop(self, event: Any) -> None:
        """Stop the main loop."""
        self.running = False

    def quit(self) -> None:
        """Quit the game and cleanup managers."""
        # Cleanup scene manager
        if self.scene_manager:
            self.scene_manager.shutdown()

        # Cleanup render manager
        if self.render_manager:
            self.render_manager.clear()

        # Quit Pygame
        pygame.quit()
        print("Game exited")

    @property
    def current_scene(self):
        """Get current scene instance."""
        return self.scene_manager.current_scene if self.scene_manager else None

    @property
    def current_scene_name(self) -> Optional[str]:
        """Get current scene name."""
        return self.scene_manager.current_scene_name if self.scene_manager else None

    def get_fps(self) -> float:
        """Get current FPS reported by clock."""
        return self.clock.get_fps()

    def get_delta_time(self) -> float:
        """Get last frame's delta time in seconds."""
        return self.delta_time


def get_engine(**kwargs) -> GameEngine:
    """Return the process engine, constructing it on first call.

    There is deliberately no module-level instance: `GameEngine()` initialises
    SDL and opens a window, so building one at import time meant that merely
    importing the ECS core required a display.
    """
    return GameEngine(**kwargs)


def reset_engine() -> None:
    """Drop the cached instance. For tests only."""
    GameEngine._instance = None
