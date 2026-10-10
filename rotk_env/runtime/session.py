"""Owned offline native scene lifecycle, shared by scene integration and Lab.

Hub, BOT and post-game report orchestration attach separately; no Python gameplay
systems survive preparation. This is not an alternate simulation fallback.
"""

from .bootstrap import prepare_display_world
from .native import RustRuntime
from .world_presentation import WorldPresentation
from .local_controls import LocalControls
from .authority import AuthorityRuntime
from framework.ecs import profiling


class NativeSession:
    def __init__(self, *, display="none", threads=1, on_events=None,
                 authority_scheduling=True, ui_context=None, **scene_options):
        self.runtime = None
        self.world = None
        self.closed = False
        self.failure = None
        self.ui_context = None
        if display == "window":
            from ..ui.context import UiContext
            self.ui_context = ui_context or UiContext(backend="rust", controller="none")
            scene_options['ui_context'] = self.ui_context
        try:
            self.world, initial = prepare_display_world(display=display, **scene_options)
            if self.ui_context:
                self.ui_context.unbind()
            self.runtime = RustRuntime(initial, threads=threads)
            self.presentation = WorldPresentation(self.world)
            if authority_scheduling:
                self.runtime = AuthorityRuntime(self.runtime,
                    on_publication=lambda delta: self.presentation.apply(delta),
                    capture_frame=self._capture_frame)
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
                self.ui_context.attach(self.world)
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
        if isinstance(self.runtime, AuthorityRuntime):
            self.refresh()
        self._update_systems(dt, inputs=True, rendering=False)

    def refresh(self):
        """Consume all queued deltas, including one current owner fence."""
        self._check_open()
        return self.controls.refresh()

    def _capture_frame(self):
        # Called on the display thread after the owner's publication fence.
        # Prepare/render the current projection without admitting inputs or
        # advancing authority. Preserve the legacy bytes/label/error contract.
        from framework.engine.renders import RenderEngine
        from framework.engine.frame_capture import capture_rendered_frame
        if any(type(s).__name__ == 'UnitRenderSystem' for s in self.world.systems):
            render = RenderEngine()
            if render.screen is not None:
                render.screen.fill((135, 141, 106))
                self._update_systems(0, inputs=False, rendering=True)
                render.update()
        return capture_rendered_frame()

    def update_display(self, dt, *, inputs=True):
        """Run input/panels/rendering over derived data after the simulation step."""
        self._update_systems(dt, inputs=inputs, rendering=True)

    def _update_systems(self, dt, *, inputs, rendering):
        self._check_open()
        try:
            self.world.bump_revision()
            for system in self.world.systems:
                is_input = getattr(system, "controls", None) is self.controls
                if system.enabled and is_input and hasattr(system, 'render_only'):
                    if inputs:
                        system.update_control_state(dt)
                    if rendering:
                        with profiling.profiler.time_system(type(system).__name__):
                            system.render_only(dt)
                elif system.enabled and (inputs if is_input else rendering):
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
            if self.ui_context:
                self.ui_context.bind(system)
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
                if isinstance(self.runtime, AuthorityRuntime) and self.runtime._pumping:
                    self.runtime.retire()
                else:
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
            if self.runtime is not None:
                self.runtime.close()
        finally:
            if self.ui_context is not None:
                self.ui_context.close()
            if self.world is not None:
                self.world.reset()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
