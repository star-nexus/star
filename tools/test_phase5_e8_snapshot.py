from copy import deepcopy
from types import SimpleNamespace

import pytest
import performance_profiler as perf
from tools.phase5_e8_snapshot import export_aligned, install_volume_metrics


def test_aligned_export_preserves_missing_values_and_rejects_drift():
    p = perf.PerformanceProfiler()
    p.enabled = True
    p.start_frame()
    p.set_frame_metric('present_only_once', 7)
    p.end_frame()
    p.start_frame()
    p.end_frame()
    data = export_aligned(p)
    assert data['metrics']['present_only_once'] == [7, None]
    p.frame_controlled_ns.append(1)
    with pytest.raises(ValueError, match='unaligned'):
        export_aligned(p)


def test_volume_patch_preserves_batch_order_positions_and_commands():
    from rotk_env.systems.window_render_systems_base import UnitRenderSystem
    from framework.engine import RMS
    p = perf.profiler
    p.enabled = True
    p.reset()
    events = []
    def emit(*args):
        events.append(args)
        RMS.circle((0,0,0), (0,0), 1)
    obj = SimpleNamespace(
        world=SimpleNamespace(get_component=lambda e,c: SimpleNamespace(col=e % 2,row=0)),
        _get_animation_system=lambda: None,
        _get_fast_animation_screen_position=lambda e,*args: (e+.25,e+.75) if e%3==0 else None,
        _render_unit_group_optimized=lambda *args: emit('group',*args),
        _render_single_unit_fast=lambda *args: emit('animated',*args),
    )
    units = list(range(25))
    original = UnitRenderSystem._render_units_batch
    RMS.clear()
    original(obj,units,[3,4],.7)
    expected = deepcopy(events)
    events.clear()
    RMS.clear()
    restore = install_volume_metrics()
    try:
        p.start_frame()
        UnitRenderSystem._render_units_batch(obj,units,[3,4],.7)
        p.end_frame()
        assert events == expected
        metrics = export_aligned(p)['metrics']
        assert metrics['e8_visible_units'] == [25]
        assert metrics['e8_animated_units'] == [9]
        assert metrics['e8_static_units'] == [16]
        assert metrics['e8_static_groups'] == [2]
        assert metrics['e8_static_draw_slots'] == [12]
        assert metrics['e8_unit_commands'] == [11]
        assert metrics['e8_animated_commands'] == [9]
        assert metrics['e8_static_commands'] == [2]
    finally:
        restore()
        RMS.clear()
        p.reset()
        p.enabled = False


@pytest.mark.parametrize('dt',[0,.01,.5,1.7,10])
def test_animation_patch_preserves_authoritative_and_fractional_progress(dt):
    from rotk_env.components import HexPosition, MovementAnimation
    from rotk_env.systems.animation_system import AnimationSystem
    p = perf.profiler
    p.enabled = True
    p.reset()
    def fixture():
        positions = {i:HexPosition(0,0) for i in range(3)}
        animations = {i:MovementAnimation() for i in range(3)}
        for i, a in animations.items():
            a.path = [(1,0),(2,0),(3,0)]
            a.progress = i*.2
            a.speed = 2
            a.is_moving = i != 2
        commits=[]
        def commit(e,c,r,*,arrived):
            commits.append((e,c,r,arrived))
            positions[e].col, positions[e].row = c,r
        obj=SimpleNamespace(
            world=SimpleNamespace(
                query=lambda:SimpleNamespace(with_all=lambda *cs:SimpleNamespace(entities=lambda:range(3))),
                get_component=lambda e,c: positions[e] if c is HexPosition else animations[e]),
            _get_movement_system=lambda:SimpleNamespace(commit_hex_position=commit),
            _setup_movement_segment=lambda a,pos:None,
        )
        return obj,positions,animations,commits
    a=fixture()
    AnimationSystem._update_movement_animations(a[0],dt)
    b=fixture()
    restore=install_volume_metrics()
    try:
        p.start_frame()
        AnimationSystem._update_movement_animations(b[0],dt)
        p.end_frame()
        assert a[1:] == b[1:]
        m=export_aligned(p)['metrics']
        assert m['e8_movement_commits']==[len(a[3])]
        assert m['e8_animation_active']==[2]
    finally:
        restore()
        p.reset()
        p.enabled=False
