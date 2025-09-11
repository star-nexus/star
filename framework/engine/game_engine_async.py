import pygame
import asyncio
import time
from typing import Any, Optional

from .scenes import SceneManager
from .renders import RenderEngine
from .inputs import InputSystem
from .events import EventBus
from ..ecs.world import World
from .engine_event import QuitEvent


class AsyncGameEngine:
    """Asynchronous game engine - supports pygbag Web deployment."""

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, title: str = "Game", width: int = 800, height: int = 600, fps: int = 60
    ):
        """Initialize the async engine (idempotent for singleton)."""
        if hasattr(self, "_initialized"):
            return

        # Basic configuration
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.delta_time = 0.0
        self.frame_duration = 1.0 / self.fps

        # Initialize Pygame
        self._init_pygame()
        self._init_world()
        self._init_managers()

        self._initialized = True

    def _init_pygame(self) -> None:
        """Initialize Pygame context and screen."""
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        self.clock = pygame.time.Clock()

    def _init_world(self) -> None:
        """Initialize ECS world."""
        self.world = World()

    def _init_managers(self) -> None:
        """Initialize managers and subscriptions."""
        self.event_manager = EventBus()
        self.scene_manager = SceneManager(self)
        self.render_manager = RenderEngine(self.screen)
        self.input_manager = InputSystem()
        self.subscribe_events()

    async def start(self) -> None:
        """Start the async engine."""
        await self.run()

    async def run(self) -> None:
        """Run the asynchronous main loop."""
        self.running = True
        last_time = time.time()

        try:
            while self.running:
                # Compute delta time
                current_time = time.time()
                self.delta_time = current_time - last_time
                last_time = current_time

                # Main async update
                await self._async_update()

                # Frame limiting (important for pygbag)
                frame_time = time.time() - current_time
                if frame_time < self.frame_duration:
                    await asyncio.sleep(self.frame_duration - frame_time)

        except KeyboardInterrupt:
            print("Game interrupted by user")
        finally:
            await self.quit()

    def subscribe_events(self) -> None:
        """Subscribe event handlers."""
        self.event_manager.subscribe(QuitEvent, self.stop)

    async def _async_update(self) -> None:
        """Update one async frame of game logic and rendering."""
        # Clear screen
        self.screen.fill((0, 0, 0))

        # Input update
        self.input_manager.update()

        # Scene update (async if supported)
        await self._async_scene_update()

        # Render
        self.render_manager.update()

        # Flip display
        pygame.display.flip()

    async def _async_scene_update(self) -> None:
        """Async scene update if available; otherwise run sync with await point."""
        if hasattr(self.scene_manager, "async_update"):
            await self.scene_manager.async_update(self.delta_time)
        else:
            # Fallback to sync scene manager
            self.scene_manager.update(self.delta_time)
            # Yield control to event loop
            await asyncio.sleep(0)

    def stop(self, event: Any) -> None:
        """Stop the main loop."""
        self.running = False

    async def quit(self) -> None:
        """Quit the game asynchronously and cleanup managers."""
        # Cleanup scene manager
        if self.scene_manager:
            if hasattr(self.scene_manager, "async_shutdown"):
                await self.scene_manager.async_shutdown()
            else:
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

    # pygbag-specific entrypoints
    async def pygbag_main(self) -> None:
        """pygbag main entrypoint."""
        # Start loop after initialization
        await self.start()


def async_game_engine() -> AsyncGameEngine:
    """Get async game engine singleton."""
    return AsyncGameEngine()


# pygbag compatibility
async def main():
    """pygbag entry function."""
    engine = async_game_engine()
    await engine.pygbag_main()


if __name__ == "__main__":
    # Local run
    asyncio.run(main())
