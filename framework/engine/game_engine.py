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

# Production play is capped at 60 FPS by default. The optional uncapped mode is
# intended for throughput measurement: it removes the render-loop limiter and
# drives systems with measured wall-clock delta so the world does not speed up.
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
        uncapped: Optional[bool] = None,
    ):
        """Initialize the game engine."""
        if hasattr(self, "_initialized"):
            # Already built for this process. FPS remains re-pinnable. Uncapped
            # is only changed when explicitly supplied so incidental get_engine()
            # calls cannot silently alter the active clock mode.
            changed = False
            if fps != self.fps:
                self.fps = fps
                changed = True
            if uncapped is not None and bool(uncapped) != self.uncapped:
                self.uncapped = bool(uncapped)
                changed = True
            if changed:
                self._publish_clock_metadata()
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
        self.uncapped = bool(uncapped) if uncapped is not None else False
        self.running = False
        self.delta_time = 0.0

        # Initialize Pygame
        self._init_pygame()

        # self._init_world()

        # Initialize managers
        self._init_managers()

        profiling.profiler.set_metadata(
            headless=self.headless,
            window=f"{self.width}x{self.height}",
        )
        self._publish_clock_metadata()
        self._initialized = True

    def _publish_clock_metadata(self) -> None:
        """Expose the active frame-clock semantics in profiler output."""
        profiling.profiler.set_metadata(
            fps_cap="uncapped" if self.uncapped else self.fps,
            clock_mode="uncapped_wall_clock" if self.uncapped else "fixed_step_capped",
        )

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

        # STAR gameplay uses physical key state / KEYDOWN / KEYUP rather than
        # editable text. Pygame enables SDL text input by default; on macOS this
        # activates the InputMethodKit/IME path inside SDL_PumpEvents and can
        # make pygame.event.get() block for tens of milliseconds during heavy
        # keyboard use. Keep text input off unless a future focused text widget
        # explicitly opts in through set_text_input_enabled().
        self.set_text_input_enabled(False)

        self.clock = pygame.time.Clock()

    def set_text_input_enabled(self, enabled: bool) -> None:
        """Explicitly control SDL text/IME input for focused text widgets.

        Normal gameplay keeps this disabled. A future chat box, console, or
        name field may enable it while focused and must disable it again when
        focus leaves the text field.
        """
        enabled = bool(enabled)
        if enabled:
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()
        self.text_input_enabled = enabled
        profiling.profiler.set_metadata(text_input=enabled)

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

    def _frame_delta_seconds(
        self,
        now: float,
        previous_frame_started_at: Optional[float],
        fixed_dt: float,
    ) -> float:
        """Return the simulation delta for the active clock mode.

        Capped production play keeps the established fixed timestep. Uncapped
        measurement uses time between frame starts, so removing the limiter does
        not make one wall-clock second advance multiple seconds of game time.
        """
        if not self.uncapped or previous_frame_started_at is None:
            return fixed_dt
        return max(0.0, now - previous_frame_started_at)

    def _wait_for_frame_cap(self, profiler) -> None:
        """Apply the production frame cap; benchmark mode deliberately skips it."""
        if self.uncapped:
            return
        with profiler.time_system("fps_limiter_wait", category="wait"):
            self.clock.tick(self.fps)

    def run(self) -> None:
        """Run the main game loop.

        Production mode uses the established fixed timestep of ``1/FPS`` and
        ``clock.tick(FPS)``. ``uncapped`` mode is a throughput-measurement clock:
        it removes the limiter and supplies measured wall-clock delta to systems.
        This exposes full-frame capacity without accelerating realtime game time.

        The profiler ends each frame after any production limiter wait, so active
        work, presentation blocking, and intentional FPS-cap waiting remain
        separate in capped reports. Uncapped reports contain no limiter wait.
        """
        self.running = True
        fixed_dt = 1.0 / float(self.fps)
        previous_frame_started_at: Optional[float] = None
        profiler = profiling.profiler

        try:
            while self.running:
                frame_started_at = time.perf_counter()
                profiler.start_frame()
                self.delta_time = self._frame_delta_seconds(
                    frame_started_at,
                    previous_frame_started_at,
                    fixed_dt,
                )
                previous_frame_started_at = frame_started_at
                profiler.set_frame_metric("render_uncapped", int(self.uncapped))
                self._update()

                self._wait_for_frame_cap(profiler)

                profiler.end_frame()
                self._maybe_print_profiler(profiler)

        except KeyboardInterrupt:
            print("Game interrupted by user")
        finally:
            # Safe no-op if the frame was already closed.
            profiler.end_frame()
            self.quit()

    def _maybe_print_profiler(self, profiler) -> None:
        """Print the rolling profiler window every ~5 seconds when enabled."""
        now = time.monotonic()
        if hasattr(self, "_last_stats_time"):
            if now - self._last_stats_time > 5.0:
                profiler.print_stats()
                self._last_stats_time = now
        else:
            self._last_stats_time = now

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
        profiling.profiler.set_metadata(window=f"{self.width}x{self.height}")

    def _update(self) -> None:
        """Update one frame of game logic and rendering."""
        profiler = profiling.profiler

        if not self.headless:
            with profiler.time_system("screen_fill", category="render"):
                self.screen.fill((135, 141, 106))  # clear screen

        with profiler.time_system("input_system", category="input"):
            self.input_manager.update()

        with profiler.time_system("scene_update", category="update"):
            self.scene_manager.update(self.delta_time)

        if not self.headless:
            with profiler.time_system("render_engine", category="render"):
                self.render_manager.update()

            # This is presentation-call wall time. On some SDL/display stacks it
            # includes VSync/compositor blocking; the profiler reports it
            # separately rather than calling it CPU rendering time.
            with profiler.time_system("display_present", category="present"):
                pygame.display.flip()

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
