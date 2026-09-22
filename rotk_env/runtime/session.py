"""Owned offline native scene lifecycle, shared by scene integration and Lab.

Hub, BOT and post-game report orchestration attach separately; no Python gameplay
systems survive preparation. This is not an alternate simulation fallback.
"""

from .bootstrap import prepare_display_world
from .native import RustRuntime
from .world_presentation import WorldPresentation
from .local_controls import LocalControls
from framework.ecs import profiling


class NativeSession:
    def __init__(self, *, display="none", threads=1, on_events=None, **scene_options):
        self.runtime = None
        self.world = None
        self.closed = False
        self.failure = None
        try:
            self.world, initial = prepare_display_world(display=display, **scene_options)
            self.runtime = RustRuntime(initial, threads=threads)
            self.presentation = WorldPresentation(self.world)
            self.controls = LocalControls(self.runtime, self.presentation, initial,
                                          on_events=on_events, on_error=self._fail)
            self.controls.refresh()
            if display == "window":
                from .window_presentation import attach_battlefield_renderers
                from .native_input import InputHandlingSystem, UnitActionButtonSystem, UIButtonSystem
                from rotk_env.systems.panel_render_system import PanelRenderSystem
                from rotk_env.systems.ui_render_system import UIRenderSystem
                from rotk_env.systems.window_minimap_system import MiniMapSystem

                attach_battlefield_renderers(self.presentation)
                for system in (InputHandlingSystem(self.controls), UnitActionButtonSystem(self.controls),
                               UIButtonSystem(self.controls), PanelRenderSystem(), UIRenderSystem(), MiniMapSystem()):
                    self._mount(system)
            elif display == "dummy":
                from .native_input import CoordinateInputHandlingSystem
                self._mount(CoordinateInputHandlingSystem(self.controls))
        except BaseException:
            self.close()
            raise

    def step(self, dt, *, wall_time=None):
        """Advance authority, then refresh derived data; no drawing or wall dt."""
        self._check_open()
        try:
            self.runtime.step(dt, wall_time=wall_time)
            return self.controls.refresh()
        except Exception as exc:
            self._fail(exc)
            raise

    def update_inputs(self, dt):
        """Poll native input/panels before simulation, preserving command order."""
        self._update_systems(dt, inputs=True, rendering=False)

    def update_display(self, dt, *, inputs=True):
        """Run input/panels/rendering over derived data after the simulation step."""
        self._update_systems(dt, inputs=inputs, rendering=True)

    def _update_systems(self, dt, *, inputs, rendering):
        self._check_open()
        try:
            self.world.bump_revision()
            for system in self.world.systems:
                is_input = getattr(system, "controls", None) is self.controls
                if system.enabled and (inputs if is_input else rendering):
                    with profiling.profiler.time_system(type(system).__name__):
                        system.update(dt)
            self._check_open()
        except Exception as exc:
            self._fail(exc)
            raise

    def _mount(self, system):
        # World.add_system appends only after initialization and subscription.
        # A partial subscription failure otherwise escapes World.reset cleanup.
        try:
            self.world.add_system(system)
        except BaseException:
            cleanup = getattr(system, "cleanup", None)
            if cleanup is not None:
                cleanup()
            raise

    def _fail(self, exc):
        if self.failure is None:
            self.failure = exc
            # The legacy event bus prints callback exceptions. Retire authority
            # immediately and re-raise at the next scene boundary instead of
            # letting another queued input or tick continue a damaged world.
            if self.runtime is not None:
                self.runtime.close()

    def _check_open(self):
        if self.failure is not None:
            raise RuntimeError("Native session failed") from self.failure
        if self.closed:
            raise RuntimeError("Native session is closed")

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.world is not None:
                self.world.reset()
        finally:
            if self.runtime is not None:
                self.runtime.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
