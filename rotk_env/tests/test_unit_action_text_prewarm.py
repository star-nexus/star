from rotk_env.systems.unit_action_button_system import UnitActionButtonSystem


class _FakeFont:
    def __init__(self):
        self.calls = []

    def render(self, text, antialias, color):
        surface = (text, color, len(self.calls))
        self.calls.append((text, color))
        return surface


def _bare_system():
    system = UnitActionButtonSystem.__new__(UnitActionButtonSystem)
    system.text_color = (255, 255, 255)
    system.text_disabled_color = (128, 128, 128)
    system.font = _FakeFont()
    system.small_font = _FakeFont()
    system.title_font = _FakeFont()
    system._fonts = {
        "main": system.font,
        "small": system.small_font,
        "title": system.title_font,
    }
    system._text_surface_cache = {}
    system._frame_text_cache_misses = 0
    return system


def test_unit_action_static_text_is_prewarmed_and_reused():
    system = _bare_system()
    system._prewarm_action_text()

    assert system._frame_text_cache_misses == 0
    assert len(system._text_surface_cache) > 0

    calls_before = len(system.title_font.calls)
    first = system._render_text_cached("title", "Unit Actions", system.text_color)
    second = system._render_text_cached("title", "Unit Actions", system.text_color)

    assert first is second
    assert len(system.title_font.calls) == calls_before
    assert system._frame_text_cache_misses == 0


def test_dynamic_cost_text_renders_once_after_font_warmup():
    system = _bare_system()
    system._prewarm_action_text()

    calls_before = len(system.small_font.calls)
    first = system._render_text_cached(
        "small", "Movement Points: 4", system.text_color
    )
    second = system._render_text_cached(
        "small", "Movement Points: 4", system.text_color
    )

    assert first is second
    assert len(system.small_font.calls) == calls_before + 1
    assert system._frame_text_cache_misses == 1
