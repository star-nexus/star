"""Compatibility-named scale renderers used by the interactive world.

Several legacy UI helpers discover render systems by ``type(system).__name__``.
Keep those public class names stable while the implementation lives in the
Fast* subclasses.

The optimized Unit renderer also owns scale-test diagnostics for the actual
interactive path. Keeping the instrumentation here matters because the window
world mounts ``FastUnitRenderSystem`` through this compatibility class rather
than the legacy base renderer directly.
"""

from __future__ import annotations

import time

import pygame

from framework.engine import RMS
from framework.ecs import profiling
from ..components import Camera, DamageNumber, HexPosition
from .fast_render_systems import (
    FastEffectRenderSystem,
    FastMapRenderSystem,
    FastMiniMapSystem,
    FastUnitRenderSystem,
)


class MapRenderSystem(FastMapRenderSystem):
    pass


class UnitRenderSystem(FastUnitRenderSystem):
    """Scale renderer plus second-level diagnostics for rare UnitRender tails."""

    COMBAT_FONT_SIZES = (20, 24, 28)
    COMBAT_FONT_PREWARM_TEXT = "0123456789MISSCRIT!+-"

    def initialize(self, world) -> None:
        super().initialize(world)

        # Deterministic 500-unit profiling isolated two ~82 ms gameplay stalls
        # to the first pygame.font.Font.render() on combat floating text: once
        # for the already-created 24 px damage font and once for the newly-used
        # 28 px CRIT! font. Prewarm the exact runtime font sizes and glyphs while
        # the world is still initializing, before the gameplay profiling epoch.
        animation_system = self._get_animation_system()
        if animation_system:
            self._prewarm_combat_fonts(animation_system)

    def _prewarm_combat_fonts(self, animation_system) -> None:
        """Prime SDL_ttf/FreeType combat glyphs outside the gameplay hot path."""
        if not animation_system.damage_font:
            return

        warmed_sizes = []
        try:
            for font_size in self.COMBAT_FONT_SIZES:
                if font_size == 24:
                    font = animation_system.damage_font
                else:
                    font = animation_system.font_dict.get(font_size)
                    if font is None:
                        font = pygame.font.Font(
                            animation_system.font_file_path, font_size
                        )
                        animation_system.font_dict[font_size] = font

                # Do not retain the returned Surface. This only forces
                # SDL_ttf/FreeType through the one-time font/glyph cold path.
                font.render(self.COMBAT_FONT_PREWARM_TEXT, True, (255, 255, 255))
                warmed_sizes.append(font_size)
        except (pygame.error, FileNotFoundError) as exc:
            print(f"[UnitRenderSystem] Combat font prewarm skipped: {exc}")
            return

        print(
            "[UnitRenderSystem] Combat fonts prewarmed: "
            + ",".join(str(size) for size in warmed_sizes)
            + " px"
        )

    def _reset_texture_cache_frame_stats(self) -> None:
        # The parent base renderer owns these aggregate counters. The fast
        # renderer has a separate dynamic LRU tier, so reset both views here.
        super()._reset_texture_cache_frame_stats()
        self._frame_fast_cache_hits = 0
        self._frame_fast_cache_misses = 0
        self._frame_fast_texture_scales = 0
        self._frame_fast_cache_evictions = 0

    def _publish_texture_cache_frame_stats(self) -> None:
        # Report the cache that is actually used by FastUnitRenderSystem:
        # immutable/common pre-scales + the bounded dynamic zoom-size LRU.
        total_cache_size = len(self.scaled_texture_cache) + len(
            self._dynamic_texture_cache
        )
        profiling.profiler.set_frame_metric(
            "unit_texture_cache_size", total_cache_size
        )
        profiling.profiler.set_frame_metric(
            "unit_texture_cache_hits", self._frame_cache_hits
        )
        profiling.profiler.set_frame_metric(
            "unit_texture_cache_misses", self._frame_cache_misses
        )
        profiling.profiler.set_frame_metric(
            "unit_texture_scales", self._frame_texture_scales
        )
        profiling.profiler.set_frame_metric(
            "unit_texture_cache_evictions", self._frame_cache_evictions
        )
        profiling.profiler.set_frame_metric(
            "fast_unit_texture_cache_size", len(self._dynamic_texture_cache)
        )
        profiling.profiler.set_frame_metric(
            "fast_unit_texture_hits", self._frame_fast_cache_hits
        )
        profiling.profiler.set_frame_metric(
            "fast_unit_texture_misses", self._frame_fast_cache_misses
        )
        profiling.profiler.set_frame_metric(
            "fast_unit_texture_scales", self._frame_fast_texture_scales
        )
        profiling.profiler.set_frame_metric(
            "fast_unit_texture_evictions", self._frame_fast_cache_evictions
        )

    def _get_cached_texture(self, faction, unit_type, size: int):
        """Fast two-tier texture cache with per-frame diagnostics.

        The first tier contains common pre-scaled sizes. The second tier is the
        bounded dynamic LRU from FastUnitRenderSystem. Instrument both tiers so
        a future slow frame can prove or rule out texture scaling directly.
        """
        size = max(1, int(size))
        key = f"{faction.value}_{unit_type.value}"
        cache_key = (key, size)

        cached = self.scaled_texture_cache.get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            self._frame_cache_hits += 1
            self._frame_fast_cache_hits += 1
            return cached

        cached = self._dynamic_texture_cache.get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            self._frame_cache_hits += 1
            self._frame_fast_cache_hits += 1
            self._dynamic_texture_cache.move_to_end(cache_key)
            return cached

        original = self.unit_textures.get(key)
        if original is None:
            return None

        self.cache_misses += 1
        self._frame_cache_misses += 1
        self._frame_texture_scales += 1
        self._frame_fast_cache_misses += 1
        self._frame_fast_texture_scales += 1

        scaled = pygame.transform.scale(original, (size, size))
        self._dynamic_texture_cache[cache_key] = scaled
        self._dynamic_texture_cache.move_to_end(cache_key)
        while len(self._dynamic_texture_cache) > self._dynamic_texture_cache_limit:
            self._dynamic_texture_cache.popitem(last=False)
            self.cache_evictions += 1
            self._frame_cache_evictions += 1
            self._frame_fast_cache_evictions += 1
        return scaled

    def update(self, delta_time: float) -> None:
        """Render units while exposing the second-level hot-path breakdown."""
        update_start = time.time() if self.enable_profiler else None

        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        self._reset_texture_cache_frame_stats()
        self.render_count += 1

        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        step1_start = time.time() if self.enable_profiler else None
        with profiling.profiler.time_system("unit_visible_cull", category="render"):
            visible_units = self._get_visible_units(camera_offset, zoom)
        profiling.profiler.set_frame_metric("visible_units", len(visible_units))
        if self.enable_profiler:
            self._add_step_time("get_visible_units", time.time() - step1_start)

        step2_start = time.time() if self.enable_profiler else None
        render_strategy = "full_featured" if len(visible_units) <= 20 else "batch"
        profiling.profiler.set_frame_metric("unit_render_strategy", render_strategy)
        if self.enable_profiler:
            self._add_step_time("render_decision", time.time() - step2_start)

        if render_strategy == "full_featured":
            step3_start = time.time() if self.enable_profiler else None
            with profiling.profiler.time_system(
                "unit_full_featured_draw", category="render"
            ):
                self._render_units_full_featured(visible_units, camera_offset, zoom)
            if self.enable_profiler:
                self._add_step_time("full_featured_render", time.time() - step3_start)
        else:
            step3_start = time.time() if self.enable_profiler else None
            self._render_units_batch(visible_units, camera_offset, zoom)
            if self.enable_profiler:
                self._add_step_time("batch_render", time.time() - step3_start)

        step4_start = time.time() if self.enable_profiler else None
        animation_system = self._get_animation_system()
        if animation_system:
            self._render_damage_numbers_profiled(animation_system)
        else:
            profiling.profiler.set_frame_metric("damage_number_count", 0)
            profiling.profiler.set_frame_metric("damage_font_sizes", "")
            profiling.profiler.set_frame_metric("damage_font_creations", 0)
        if self.enable_profiler:
            self._add_step_time("animation_render", time.time() - step4_start)

        self._publish_texture_cache_frame_stats()

        if self.enable_profiler and update_start:
            total_time = time.time() - update_start
            if self.render_count % self.profiler_interval == 0:
                self._print_detailed_performance_stats(
                    len(visible_units), render_strategy, total_time
                )

    def _render_units_batch(self, visible_units, camera_offset, zoom):
        """Animation-aware batch path with prepare/static/animated timers."""
        if not visible_units:
            profiling.profiler.set_frame_metric("animated_visible_units", 0)
            return

        with profiling.profiler.time_system("unit_batch_prepare", category="render"):
            animation_system = self._get_animation_system()
            units_by_position = {}
            animated_units = []

            for entity in visible_units:
                animated_screen_pos = self._get_fast_animation_screen_position(
                    entity, animation_system, camera_offset, zoom
                )
                if animated_screen_pos is not None:
                    animated_units.append((entity, animated_screen_pos))
                    continue

                position = self.world.get_component(entity, HexPosition)
                if position:
                    pos_key = (position.col, position.row)
                    units_by_position.setdefault(pos_key, []).append(entity)

        profiling.profiler.set_frame_metric(
            "animated_visible_units", len(animated_units)
        )

        with profiling.profiler.time_system("unit_static_draw", category="render"):
            for pos_key, units in units_by_position.items():
                self._render_unit_group_optimized(
                    pos_key, units, camera_offset, zoom
                )

        with profiling.profiler.time_system("unit_animated_draw", category="render"):
            for entity, (screen_x, screen_y) in animated_units:
                self._render_single_unit_fast(entity, screen_x, screen_y, zoom)

    def _render_damage_numbers_profiled(self, animation_system) -> None:
        """Render combat floating text with font/query/submit attribution.

        This intentionally mirrors AnimationSystem.render_damage_numbers(). It
        is diagnostic, not an optimization: the goal is to determine whether a
        rare ~80 ms UnitRenderSystem frame is query work, lazy Font creation,
        glyph rasterization in Font.render(), or command submission.
        """
        with profiling.profiler.time_system("unit_damage_numbers", category="render"):
            if not animation_system.damage_font:
                profiling.profiler.set_frame_metric("damage_number_count", 0)
                profiling.profiler.set_frame_metric("damage_font_sizes", "")
                profiling.profiler.set_frame_metric("damage_font_creations", 0)
                return

            camera = self.world.get_singleton_component(Camera)
            if not camera:
                profiling.profiler.set_frame_metric("damage_number_count", 0)
                profiling.profiler.set_frame_metric("damage_font_sizes", "")
                profiling.profiler.set_frame_metric("damage_font_creations", 0)
                return

            camera_offset = camera.get_offset()
            with profiling.profiler.time_system(
                "damage_number_query", category="render"
            ):
                entities = list(
                    self.world.query().with_all(DamageNumber).entities()
                )

            font_sizes = set()
            font_creations = 0

            for entity in entities:
                damage_num = self.world.get_component(entity, DamageNumber)
                if not damage_num:
                    continue

                alpha_ratio = 1.0 - (
                    damage_num.elapsed_time / damage_num.lifetime
                )
                alpha = int(255 * alpha_ratio)
                if alpha <= 0:
                    continue

                font_to_use = animation_system.damage_font
                font_size = getattr(damage_num, "font_size", 24)
                font_sizes.add(font_size)

                if font_size != 24:
                    try:
                        if font_size not in animation_system.font_dict:
                            with profiling.profiler.time_system(
                                "damage_font_create", category="render"
                            ):
                                if not animation_system.font_file_path.exists():
                                    raise FileNotFoundError(
                                        f"Font file not found: {animation_system.font_file_path}"
                                    )
                                animation_system.font_dict[font_size] = pygame.font.Font(
                                    animation_system.font_file_path, font_size
                                )
                            font_creations += 1
                        font_to_use = animation_system.font_dict[font_size]
                    except Exception:
                        font_to_use = animation_system.damage_font

                with profiling.profiler.time_system(
                    "damage_font_render", category="render"
                ):
                    text_surface = font_to_use.render(
                        damage_num.text, True, damage_num.color
                    )

                if alpha < 255:
                    text_surface.set_alpha(alpha)

                screen_x = damage_num.position[0] + camera_offset[0]
                screen_y = damage_num.position[1] + camera_offset[1]
                with profiling.profiler.time_system(
                    "damage_number_submit", category="render"
                ):
                    RMS.draw(text_surface, (screen_x, screen_y))

            profiling.profiler.set_frame_metric(
                "damage_number_count", len(entities)
            )
            profiling.profiler.set_frame_metric(
                "damage_font_sizes",
                ",".join(str(size) for size in sorted(font_sizes)),
            )
            profiling.profiler.set_frame_metric(
                "damage_font_creations", font_creations
            )


class EffectRenderSystem(FastEffectRenderSystem):
    pass


class MiniMapSystem(FastMiniMapSystem):
    def _render_minimap(self, minimap):
        # The cached frame surface is intentionally reused. Clear dynamic unit/
        # viewport pixels before restoring the cached static terrain layer.
        if self._frame_surface is not None:
            self._frame_surface.fill((0, 0, 0, 0))
        super()._render_minimap(minimap)