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
                 authority_scheduling=True, ui_context=None, renderer=None, frame_provider=None,
                 **scene_options):
        self.runtime = None
        self.world = None
        self.closed = False
        self.failure = None
        self.ui_context = None
        self.renderer = None
        renderer = renderer or ('pygame' if display == 'window' else 'none')
        if (display == 'window') != (renderer == 'pygame'):
            raise ValueError('pygame requires window preparation; other renderers require none/dummy')
        if renderer == 'web':
            scene_options.setdefault('simulation_profile', 'interactive')
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
            from rotk_env.rendering import create_renderer
            from rotk_env.rendering.adapters import RendererFrameProvider
            self.renderer = create_renderer(renderer, presentation=self.presentation,
                update=self._update_systems, capture=self._capture_frame, initial=initial)
            self.frame_provider = frame_provider or RendererFrameProvider(self.renderer)
            if renderer == 'web':
                from rotk_env.rendering.commands import HumanCommandPolicy
                self.runtime._human_policy = HumanCommandPolicy(initial)
            self.runtime._frame_capture = self.frame_provider.capture
            if authority_scheduling:
                self.runtime = AuthorityRuntime(self.runtime,
                    on_publication=self.renderer.apply,
                    capture_frame=self.frame_provider.capture)
            self.controls = LocalControls(self.runtime, self.presentation, initial,
                on_events=on_events, on_error=self._fail, on_publication=self.renderer.apply)
            self.controls.refresh()
            if display == "window":
                self.renderer.mount(self.controls, self.ui_context, self._mount)
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
        from framework.engine.renders import RenderEngine, FRAME_CLEAR_COLOR
        from framework.engine.frame_capture import capture_rendered_frame
        if any(type(s).__name__ == 'UnitRenderSystem' for s in self.world.systems):
            render = RenderEngine()
            if render.screen is not None:
                render.screen.fill(FRAME_CLEAR_COLOR)
                self._update_systems(0, inputs=False, rendering=True)
                render.update()
        return capture_rendered_frame()

    def update_display(self, dt, *, inputs=True):
        """Run input/panels/rendering over derived data after the simulation step."""
        self.renderer.render(dt, inputs=inputs)

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
            try:
                if self.renderer is not None:
                    self.renderer.close()
            finally:
                try:
                    if self.ui_context is not None:
                        self.ui_context.close()
                finally:
                    if self.world is not None:
                        self.world.reset()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
