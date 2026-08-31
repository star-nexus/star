from __future__ import annotations

from pathlib import Path

from rotk_env.systems import optimized_render_systems as optimized


class _Font:
    def __init__(self, size: int):
        self.size = size
        self.render_calls = []

    def render(self, text, antialias, color):
        self.render_calls.append((text, antialias, color))
        return object()


class _AnimationSystem:
    def __init__(self):
        self.damage_font = _Font(24)
        self.font_dict = {}
        self.font_file_path = Path("rotk_env/assets/fonts/sh.otf")


def test_combat_font_prewarm_primes_all_runtime_sizes_and_glyphs(monkeypatch):
    renderer = optimized.UnitRenderSystem.__new__(optimized.UnitRenderSystem)
    animation_system = _AnimationSystem()

    created_fonts = {}

    def fake_font(path, size):
        font = _Font(size)
        created_fonts[size] = font
        return font

    monkeypatch.setattr(optimized.pygame.font, "Font", fake_font)

    renderer._prewarm_combat_fonts(animation_system)

    assert set(created_fonts) == {20, 28}
    assert animation_system.font_dict[20] is created_fonts[20]
    assert animation_system.font_dict[28] is created_fonts[28]

    expected = (
        optimized.UnitRenderSystem.COMBAT_FONT_PREWARM_TEXT,
        True,
        (255, 255, 255),
    )
    assert animation_system.damage_font.render_calls == [expected]
    assert created_fonts[20].render_calls == [expected]
    assert created_fonts[28].render_calls == [expected]


def test_combat_font_prewarm_reuses_existing_non_default_fonts(monkeypatch):
    renderer = optimized.UnitRenderSystem.__new__(optimized.UnitRenderSystem)
    animation_system = _AnimationSystem()
    animation_system.font_dict[20] = _Font(20)
    animation_system.font_dict[28] = _Font(28)

    def fail_if_created(path, size):
        raise AssertionError(f"font {size} should have been reused")

    monkeypatch.setattr(optimized.pygame.font, "Font", fail_if_created)

    renderer._prewarm_combat_fonts(animation_system)

    assert len(animation_system.font_dict[20].render_calls) == 1
    assert len(animation_system.damage_font.render_calls) == 1
    assert len(animation_system.font_dict[28].render_calls) == 1
