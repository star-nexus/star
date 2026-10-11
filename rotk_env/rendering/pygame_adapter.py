"""pygame adapter retaining the accepted terrain, Fog, UI and blit caches."""

from .adapters import ProjectionRenderer


class PygameRenderer(ProjectionRenderer):
    renderer_id = 'pygame'

    def __init__(self, **context):
        super().__init__(**context)
        from .pygame.frame_capture import PygameFrameProvider
        self.frame_provider = PygameFrameProvider(self.presentation.world, self._update)

    def capture(self):
        return self.frame_provider.capture()

    @property
    def visual_version(self):
        from rotk_env.ui.context import VISUAL_VERSION
        return VISUAL_VERSION

    def mount(self, controls, ui_context, mount):
        from rotk_env.runtime.window_presentation import attach_battlefield_renderers
        from rotk_env.runtime.native_input import InputHandlingSystem, UnitActionButtonSystem, UIButtonSystem
        from rotk_env.systems.panel_render_system import PanelRenderSystem
        from rotk_env.systems.ui_render_system import UIRenderSystem
        from rotk_env.systems.window_minimap_system import MiniMapSystem

        attach_battlefield_renderers(self.presentation)
        for system in (InputHandlingSystem(controls), UnitActionButtonSystem(controls),
                       UIButtonSystem(controls)):
            mount(system)
        ui_context.attach(self.presentation.world)
        for system in (PanelRenderSystem(), UIRenderSystem(), MiniMapSystem()):
            mount(system)
