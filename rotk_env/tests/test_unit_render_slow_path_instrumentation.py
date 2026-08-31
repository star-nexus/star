from __future__ import annotations

from collections import OrderedDict
from contextlib import nullcontext
from pathlib import Path

from rotk_env.components import DamageNumber
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems import optimized_render_systems as optimized


class _Profiler:
    def __init__(self):
        self.metrics = {}
        self.timers = []

    def time_system(self, name, *, category="work"):
        self.timers.append((name, category))
        return nullcontext()

    def set_frame_metric(self, name, value):
        self.metrics[name] = value


class _Surface:
    def set_alpha(self, alpha):
        self.alpha = alpha


class _Font:
    def __init__(self):
        self.render_calls = []

    def render(self, text, antialias, color):
        self.render_calls.append((text, antialias, color))
        return _Surface()


class _Camera:
    @staticmethod
    def get_offset():
        return (10.0, 20.0)


class _Query:
    @staticmethod
    def with_all(*component_types):
        return _Query()

    @staticmethod
    def entities():
        return [1]


class _World:
    def __init__(self, damage_number):
        self.damage_number = damage_number

    @staticmethod
    def query():
        return _Query()

    @staticmethod
    def get_singleton_component(component_type):
        return _Camera()

    def get_component(self, entity, component_type):
        if component_type is DamageNumber and entity == 1:
            return self.damage_number
        return None


def _bare_renderer():
    renderer = optimized.UnitRenderSystem.__new__(optimized.UnitRenderSystem)
    renderer.scaled_texture_cache = OrderedDict()
    renderer._dynamic_texture_cache = OrderedDict()
    renderer._dynamic_texture_cache_limit = 2
    renderer.unit_textures = {}
    renderer.cache_hits = 0
    renderer.cache_misses = 0
    renderer.cache_evictions = 0
    renderer._frame_cache_hits = 0
    renderer._frame_cache_misses = 0
    renderer._frame_texture_scales = 0
    renderer._frame_cache_evictions = 0
    renderer._frame_fast_cache_hits = 0
    renderer._frame_fast_cache_misses = 0
    renderer._frame_fast_texture_scales = 0
    renderer._frame_fast_cache_evictions = 0
    # __new__ intentionally bypasses UnitRenderSystem.__init__ in this fixture.
    # Keep newly added per-frame diagnostics in sync with production state.
    renderer._frame_unit_label_cache_misses = 0
    return renderer


def test_fast_unit_texture_metrics_cover_the_actual_dynamic_cache(monkeypatch):
    profiler = _Profiler()
    monkeypatch.setattr(optimized.profiling, "profiler", profiler)

    renderer = _bare_renderer()
    original = object()
    renderer.unit_textures["wei_infantry"] = original

    scaled = []

    def fake_scale(texture, size):
        result = (texture, size)
        scaled.append(result)
        return result

    monkeypatch.setattr(optimized.pygame.transform, "scale", fake_scale)

    first = renderer._get_cached_texture(Faction.WEI, UnitType.INFANTRY, 73)
    second = renderer._get_cached_texture(Faction.WEI, UnitType.INFANTRY, 73)
    renderer._publish_texture_cache_frame_stats()

    assert first is second
    assert len(scaled) == 1
    assert profiler.metrics["fast_unit_texture_misses"] == 1
    assert profiler.metrics["fast_unit_texture_scales"] == 1
    assert profiler.metrics["fast_unit_texture_hits"] == 1
    assert profiler.metrics["unit_texture_cache_misses"] == 1
    assert profiler.metrics["unit_texture_scales"] == 1
    assert profiler.metrics["unit_texture_cache_hits"] == 1
    assert profiler.metrics["unit_full_icon_cache_misses"] == 0


def test_damage_number_profile_splits_font_create_render_and_submit(monkeypatch, tmp_path):
    profiler = _Profiler()
    monkeypatch.setattr(optimized.profiling, "profiler", profiler)

    damage_number = DamageNumber(
        text="CRIT!",
        position=(100.0, 200.0),
        lifetime=2.5,
        elapsed_time=0.0,
        velocity=(0.0, -60.0),
        color=(255, 255, 0),
        font_size=28,
    )
    renderer = _bare_renderer()
    renderer.world = _World(damage_number)

    default_font = _Font()
    created_font = _Font()
    font_path = tmp_path / "font.otf"
    font_path.write_bytes(b"test")

    class _AnimationSystem:
        damage_font = default_font
        font_dict = {}
        font_file_path = Path(font_path)

    monkeypatch.setattr(
        optimized.pygame.font, "Font", lambda path, size: created_font
    )
    draws = []
    monkeypatch.setattr(
        optimized.RMS, "draw", lambda surface, position: draws.append((surface, position))
    )

    renderer._render_damage_numbers_profiled(_AnimationSystem())

    timer_names = [name for name, _ in profiler.timers]
    assert "unit_damage_numbers" in timer_names
    assert "damage_number_query" in timer_names
    assert "damage_font_create" in timer_names
    assert "damage_font_render" in timer_names
    assert "damage_number_submit" in timer_names

    assert profiler.metrics["damage_number_count"] == 1
    assert profiler.metrics["damage_font_sizes"] == "28"
    assert profiler.metrics["damage_font_creations"] == 1
    assert created_font.render_calls == [("CRIT!", True, (255, 255, 0))]
    assert draws and draws[0][1] == (110.0, 220.0)
