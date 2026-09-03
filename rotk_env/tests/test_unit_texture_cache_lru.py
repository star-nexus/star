from __future__ import annotations

from collections import OrderedDict

import rotk_env.systems.unit_render_system as unit_render_module
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.unit_render_system import UnitRenderSystem


def _renderer_with_full_cache():
    renderer = UnitRenderSystem.__new__(UnitRenderSystem)
    renderer.unit_textures = {"wei_infantry": object()}
    renderer.scaled_texture_cache = OrderedDict(
        [
            (("old_a", 1), "a"),
            (("old_b", 2), "b"),
            (("old_c", 3), "c"),
        ]
    )
    renderer.scaled_texture_cache_max = 3
    renderer.cache_hits = 0
    renderer.cache_misses = 0
    renderer.cache_evictions = 0
    return renderer


def test_full_texture_cache_evicts_lru_and_caches_new_zoom_size(monkeypatch):
    renderer = _renderer_with_full_cache()
    scale_calls = []

    def fake_scale(original, size):
        scale_calls.append((original, size))
        return f"scaled-{size[0]}"

    monkeypatch.setattr(unit_render_module.pygame.transform, "scale", fake_scale)

    first = renderer._get_cached_texture(Faction.WEI, UnitType.INFANTRY, 73)
    second = renderer._get_cached_texture(Faction.WEI, UnitType.INFANTRY, 73)

    # The old hard-cap behavior would scale twice because the new variant was
    # never inserted once the cache reached its limit. LRU must scale exactly
    # once, evict the oldest entry, then hit on the second lookup.
    assert first == "scaled-73"
    assert second == first
    assert len(scale_calls) == 1
    assert len(renderer.scaled_texture_cache) == 3
    assert ("old_a", 1) not in renderer.scaled_texture_cache
    assert ("wei_infantry", 73) in renderer.scaled_texture_cache
    assert renderer.cache_misses == 1
    assert renderer.cache_hits == 1
    assert renderer.cache_evictions == 1
