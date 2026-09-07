"""Exact fast-render equivalence for frame-scoped style preparation."""
from types import SimpleNamespace

import pygame
import pytest

from framework.engine import RMS
from rotk_env.components import Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.optimized_render_systems import UnitRenderSystem
from rotk_env.systems.unit_render_system import UnitRenderSystem as OriginalRenderer


def renderer(textures=True, texture=None):
    obj = UnitRenderSystem.__new__(UnitRenderSystem)
    obj.textures_loaded = textures
    obj.calls = 0
    obj.unit = SimpleNamespace(faction=Faction.WEI, unit_type=UnitType.INFANTRY)
    obj.count = SimpleNamespace(current_count=5, max_count=10)
    obj.world = SimpleNamespace(get_component=lambda e,c: None if e==99 else obj.unit if c is Unit else obj.count)
    def get_texture(*args):
        obj.calls += 1
        return texture
    obj._get_cached_texture = get_texture
    return obj


def raster(commands):
    surface = pygame.Surface((160,160),pygame.SRCALPHA)
    surface.fill((13,27,41,255))
    for cmd in commands:
        cmd.execute(surface)
    return pygame.image.tobytes(surface,'RGBA')


def queued():
    return [c for cmds in RMS._render_queue.values() for c in cmds]


@pytest.mark.parametrize('size',[(17,19),(18,20)])
@pytest.mark.parametrize('textures',[True,False])
@pytest.mark.parametrize('health',[False,True])
def test_fast_style_reuse_is_pixel_identical(size,textures,health):
    texture=pygame.Surface(size,pygame.SRCALPHA)
    texture.fill((19,208,70,170))
    obj=renderer(textures,texture)
    if not health: obj.count.current_count=10
    draws=[(1,-3.7,-1.2,.7),(2,40.9,60.2,1.0),(3,100.2,90.8,1.0),(99,0,0,1.0)]
    RMS.clear()
    for args in draws: OriginalRenderer._render_single_unit_fast(obj,*args)
    expected=raster(queued())
    expected_types=[type(c) for c in queued()]
    RMS.clear()
    obj._frame_fast_styles={}
    for args in draws: obj._render_single_unit_fast(*args)
    assert raster(queued())==expected
    assert [type(c) for c in queued()]==expected_types
    RMS.clear()


def test_style_cache_lifetime_ends_on_exception(monkeypatch):
    from rotk_env.systems.window_render_systems_base import UnitRenderSystem as Base
    obj=renderer()
    def fail(*args):
        obj._frame_fast_styles['temporary']=object()
        raise RuntimeError('draw failure')
    monkeypatch.setattr(Base,'_render_units_batch',fail)
    with pytest.raises(RuntimeError,match='draw failure'):
        obj._render_units_batch([1],[0,0],1)
    assert obj._frame_fast_styles is None


def test_style_cache_reloads_resources_next_frame(monkeypatch):
    from rotk_env.systems.window_render_systems_base import UnitRenderSystem as Base
    first=pygame.Surface((17,19),pygame.SRCALPHA)
    second=pygame.Surface((18,20),pygame.SRCALPHA)
    obj=renderer(True,first)
    monkeypatch.setattr(Base,'_render_units_batch',lambda self,*args: self._render_single_unit_fast(1,30,30,1))
    RMS.clear()
    obj._render_units_batch([1],[0,0],1)
    assert queued()[0].surface is first
    obj._get_cached_texture=lambda *args:second
    RMS.clear()
    obj._render_units_batch([1],[0,0],1)
    assert queued()[0].surface is second
    assert obj._frame_fast_styles is None
    RMS.clear()
