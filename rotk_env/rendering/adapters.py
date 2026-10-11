"""Adapters over the existing presentation World; no Python simulation runs here."""


class ProjectionRenderer:
    renderer_id = 'none'
    visual_version = 'none'

    def __init__(self, *, presentation, update, capture, initial):
        self.presentation = presentation
        self._update = update
        self._capture = capture

    def apply(self, delta):
        return self.presentation.apply(delta)

    def render(self, dt, *, inputs=False):
        self._update(dt, inputs=inputs, rendering=True)

    def capture(self):
        return self._capture()

    def close(self):
        pass


class WebRenderer(ProjectionRenderer):
    renderer_id = 'threejs'
    visual_version = 'starbench-web-v1'

    def __init__(self, **context):
        super().__init__(**context)
        from .projection import RenderProjection
        self.model = RenderProjection(self.presentation.world, context['initial'])
        self.player_types = {r['components']['Player']['faction']: r['components']['Player']['player_type']
                             for r in context['initial']['entities'] if 'Player' in r['components']}

    def apply(self, delta):
        events = super().apply(delta)
        self.model.apply(delta)
        return events

    def capture(self):
        # Web pixels are not an authority-backed Agent observation provider yet.
        return None, 'Web renderer does not provide Agent observation frames'


class RendererFrameProvider:
    """Default capture capability; hosts may supply an independent provider."""

    def __init__(self, renderer):
        self.renderer = renderer
        self.renderer_id = renderer.renderer_id
        self.visual_version = renderer.visual_version

    def capture(self):
        capture = getattr(self.renderer, 'capture', None)
        if capture is None:
            return None, f'{self.renderer_id} does not provide Agent observation frames'
        return capture()
