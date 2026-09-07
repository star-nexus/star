#!/usr/bin/env python3
"""Experiment-only E8 instrumentation and complete aligned-series export.

Runtime code is never edited. Instrumentation is installed only by this launcher.
STAR_E8_MODE=off exports existing profiler samples with no extra timed-loop work.
"""
from __future__ import annotations

import functools
import inspect
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_aligned(profiler):
    n = len(profiler.frame_controlled_ns)
    def series(values):
        result = list(values)
        if len(result) != n:
            raise ValueError(f"unaligned series: {len(result)} != {n}")
        return result
    return {
        "schema": "phase5-e8-aligned-v1",
        "sample_count": n,
        "frame_start_ns": series(profiler.frame_start_ns),
        "frame_end_ns": series(profiler.frame_end_ns),
        "controlled_ns": series(profiler.frame_controlled_ns),
        "frame_ns": series(profiler.frame_times_ns),
        "self_ns": {k: series(v) for k, v in profiler.section_self_ns.items()},
        "inclusive_ns": {k: series(v) for k, v in profiler.section_inclusive_ns.items()},
        "metrics": {k: series(v) for k, v in profiler.frame_metric_samples.items()},
    }


def instrument_function(original, replacements, additions):
    source = textwrap.dedent(inspect.getsource(original))
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"instrumentation source drift: {original.__name__}: {old!r}")
        source = source.replace(old, new)
    namespace = dict(original.__globals__, **additions)
    exec(compile(source, __file__, "exec"), namespace)
    return namespace[original.__name__]


def install_volume_metrics():
    from framework.ecs import profiling
    from framework.engine import RMS
    from rotk_env.components import HexPosition
    from rotk_env.systems.window_render_systems_base import UnitRenderSystem
    from rotk_env.systems.animation_system import AnimationSystem
    from rotk_env.systems.window_vision_system import VisionSystem

    import performance_profiler as perf
    profiler = perf.profiler
    def queue_size():
        return sum(map(len, RMS._render_queue.values()))

    original_batch = UnitRenderSystem._render_units_batch
    # Identical classification/group/draw order, with loop-level counters and timers.
    def batch(self, visible_units, camera_offset, zoom):
        if not visible_units:
            return
        animation_system = self._get_animation_system()
        units_by_position = {}
        animated_units = []
        with profiler.time_system("e8_unit_classify", category="render"):
            for entity in visible_units:
                animated_screen_pos = self._get_fast_animation_screen_position(
                    entity, animation_system, camera_offset, zoom
                )
                if animated_screen_pos is not None:
                    animated_units.append((entity, animated_screen_pos))
                    continue
                position = self.world.get_component(entity, HexPosition)
                if position:
                    units_by_position.setdefault((position.col, position.row), []).append(entity)
        before = queue_size()
        with profiler.time_system("e8_unit_static_draw", category="render"):
            for pos_key, units in units_by_position.items():
                self._render_unit_group_optimized(pos_key, units, camera_offset, zoom)
        after_static = queue_size()
        with profiler.time_system("e8_unit_animated_draw", category="render"):
            for entity, (screen_x, screen_y) in animated_units:
                self._render_single_unit_fast(entity, screen_x, screen_y, zoom)
        after = queue_size()
        metrics = {
            "e8_visible_units": len(visible_units),
            "e8_animated_units": len(animated_units),
            "e8_static_units": sum(map(len, units_by_position.values())),
            "e8_static_groups": len(units_by_position),
            "e8_static_draw_slots": sum(min(6, len(v)) for v in units_by_position.values()),
            "e8_unit_commands": after - before,
            "e8_animated_commands": after - after_static,
            "e8_static_commands": after_static - before,
        }
        for key, value in metrics.items():
            profiler.set_frame_metric(key, value)
    UnitRenderSystem._render_units_batch = batch

    original_move = AnimationSystem._update_movement_animations
    AnimationSystem._update_movement_animations = instrument_function(original_move, [
        ('    movement_system = self._get_movement_system()',
         '    e8_active = e8_scanned = e8_commits = e8_completed = 0\n    movement_system = self._get_movement_system()'),
        ('    ):\n', '    ):\n        e8_scanned += 1\n'),
        ('        anim.progress += anim.speed * delta_time',
         '        e8_active += 1\n        anim.progress += anim.speed * delta_time'),
        ('            target_hex = anim.path[anim.current_target_index]',
         '            e8_commits += 1\n            target_hex = anim.path[anim.current_target_index]'),
        ('            arrived = anim.current_target_index + 1 >= len(anim.path)',
         '            arrived = anim.current_target_index + 1 >= len(anim.path)\n            e8_completed += int(arrived)'),
        ('                self._setup_movement_segment(anim, pos)',
         '                self._setup_movement_segment(anim, pos)\n'
         '    for key, value in (("e8_animation_active", e8_active), ("e8_animation_scanned", e8_scanned),\n'
         '                       ("e8_movement_commits", e8_commits), ("e8_routes_completed", e8_completed)):\n'
         '        e8_profiler.set_frame_metric(key, value)'),
    ], {"e8_profiler": profiler})

    originals = [(UnitRenderSystem, "_render_units_batch", original_batch),
                 (AnimationSystem, "_update_movement_animations", original_move)]
    for cls, name in ((AnimationSystem, "animation"), (VisionSystem, "vision"), (UnitRenderSystem, "unit")):
        original = cls.update
        def wrap(original, name):
            @functools.wraps(original)
            def update(self, dt):
                cpu = time.thread_time_ns()
                wall = time.perf_counter_ns()
                result = original(self, dt)
                elapsed = time.perf_counter_ns() - wall
                cpu_elapsed = time.thread_time_ns() - cpu
                profiler.set_frame_metric(f"e8_{name}_cpu_ms", cpu_elapsed / 1e6)
                profiler.set_frame_metric(f"e8_{name}_wall_ms", elapsed / 1e6)
                if name == "animation":
                    self._e8_sim_time = getattr(self, "_e8_sim_time", 0.0) + dt
                    profiler.set_frame_metric("e8_dt_ms", dt * 1000)
                    profiler.set_frame_metric("e8_sim_time_s", self._e8_sim_time)
                return result
            return update
        originals.append((cls, "update", original))
        cls.update = wrap(original, name)
    def restore():
        for cls, name, original in reversed(originals):
            setattr(cls, name, original)
    return restore


def main():
    import performance_profiler as perf
    mode = os.environ.get("STAR_E8_MODE", "volume")
    if mode not in {"volume", "off", "ui"}:
        raise ValueError(mode)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    expected = os.environ["STAR_E8_RUNTIME_SHA"]
    if actual != expected:
        raise RuntimeError(f"runtime source mismatch {actual} != {expected}")
    window = float(os.environ.get("STAR_E8_WINDOW", "30"))
    perf.profiler.sample_window_seconds = window
    if mode == "volume":
        install_volume_metrics()
    if mode == "ui":
        from rotk_env.systems.ui_render_system import UIRenderSystem
        for method in ("_render_faction_status_indicators", "_render_game_info", "_render_stats_panel", "_render_help_panel"):
            original = getattr(UIRenderSystem, method)
            def timed(original, method):
                @functools.wraps(original)
                def wrapped(self, *args, **kwargs):
                    with perf.profiler.time_system("e8_ui" + method, category="render"):
                        return original(self, *args, **kwargs)
                return wrapped
            setattr(UIRenderSystem, method, timed(original, method))
    trace = os.environ.get("STAR_E8_TRACE") == "1"
    if trace:
        from tools.phase5_e8_trace import install_trace, export_trace
        install_trace(perf.PerformanceProfiler)
    original_stats = perf.PerformanceProfiler.get_stats
    def stats(self):
        result = original_stats(self)
        result["e8_aligned"] = export_aligned(self)
        if trace:
            result["e8_trace"] = export_trace(self)
        return result
    perf.PerformanceProfiler.get_stats = stats
    perf.profiler.set_metadata(e8_mode=mode, e8_runtime_sha=actual, e8_window_s=window, e8_trace=trace)
    from rotk_env.main import main as env_main
    env_main()


if __name__ == "__main__":
    main()
