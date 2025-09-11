import pygame
import time
import sys
from typing import Any, Optional

from .scenes import SceneManager
from .renders import RenderEngine
from .inputs import InputSystem
from .events import EventBus
from ..ecs.world import World
from .engine_event import QuitEvent
from performance_profiler import profiler


class GameEngine:
    """Game engine - runs the main loop and core managers."""

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, title: str = "Game", width: int = 1200, height: int = 800, fps: int = 60
    ):
        """Initialize the game engine (idempotent for singleton)."""
        if hasattr(self, "_initialized"):
            return

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
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        self.clock = pygame.time.Clock()

    # def _init_world(self) -> None:
    #     """初始化世界"""
    #     # 如果需要 ECS 系统，可以在这里初始化
    #     self.world = World()

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
        """Run the main game loop."""
        self.running = True
        last_time = time.time()

        try:
            while self.running:
                # Compute delta time
                current_time = time.time()
                self.delta_time = current_time - last_time
                last_time = current_time

                # Main update
                self._update()

                # Frame limiting
                self.clock.tick(self.fps)

        except KeyboardInterrupt:
            print("Game interrupted by user")
        finally:
            self.quit()

    def subscribe_events(self) -> None:
        """Subscribe event handlers."""

        self.event_manager.subscribe(QuitEvent, self.stop)

    def _update(self) -> None:
        """Update one frame of game logic and rendering."""
        profiler.start_frame()

        with profiler.time_system("screen_fill"):
            self.screen.fill((135, 141, 106))  # clear screen

        with profiler.time_system("input_system"):
            self.input_manager.update()

        with profiler.time_system("scene_update"):
            self.scene_manager.update(self.delta_time)

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


GAMEENGINE = GameEngine()
