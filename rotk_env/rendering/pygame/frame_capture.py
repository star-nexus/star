"""Explicit pygame frame provider, including the legacy dummy-display path."""


class PygameFrameProvider:
    renderer_id = 'pygame'

    @property
    def visual_version(self):
        from rotk_env.ui.context import VISUAL_VERSION
        return VISUAL_VERSION

    def __init__(self, world=None, update=None):
        self.world, self.update = world, update

    def capture(self):
        from framework.engine.renders import RenderEngine, FRAME_CLEAR_COLOR
        from framework.engine.frame_capture import capture_rendered_frame
        if (self.world is not None and self.update is not None
                and any(type(s).__name__ == 'UnitRenderSystem' for s in self.world.systems)):
            render = RenderEngine()
            if render.screen is not None:
                render.screen.fill(FRAME_CLEAR_COLOR)
                self.update(0, inputs=False, rendering=True)
                render.update()
        return capture_rendered_frame()
