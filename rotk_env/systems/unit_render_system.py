"""
Unit Render System - High-performance, feature-complete unit rendering
- Texture caching and zoom-aware scaling
- Visibility checks with fog-of-war integration
- Group layouts inside hex tiles (single/multi-faction)
- Health bars, type icons, status indicators, and animation offsets

Designed to minimize per-frame cost while keeping visuals informative.
"""

import pygame
import os
import math
import time  # 添加time模块
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from framework import System, RMS
from ..components import (
    HexPosition,
    Unit,
    UnitCount,
    UnitStatus,
    Camera,
    GameState,
    FogOfWar,
    UIState,
)
from ..prefabs.config import GameConfig, HexOrientation, UnitType, Faction
from ..utils.hex_utils import HexConverter

# 导入性能分析器
try:
    from performance_profiler import profiler
except ImportError:
    # 如果没有profiler，创建一个简单的替代
    class DummyProfiler:
        def time_system(self, name):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    profiler = DummyProfiler()


class UnitRenderSystem(System):
    """Integrated unit renderer with optional performance profiling."""

    def __init__(self):
        super().__init__(priority=2)  # Render above the map layer
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.font = None
        self.small_font = None

        # Pre-cached textures for performance
        self.unit_textures: Dict[str, pygame.Surface] = {}
        self.scaled_texture_cache: Dict[Tuple[str, int], pygame.Surface] = {}
        self.textures_loaded = False

        # Visible units cache based on camera
        self.visible_units_cache: List[int] = []
        self.last_camera_hash = 0

        # Stats
        self.render_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

        # Profiling switch (off by default)
        self.enable_profiler = False
        self.profiler_interval = 60  # print stats every N frames (~1s at 60fps)

        # Detailed profiling buckets
        self.step_times = {
            "get_visible_units": [],
            "render_decision": [],
            "full_featured_render": [],
            "batch_render": [],
            "animation_render": [],
            "visibility_check": [],
            "position_grouping": [],
            "faction_grouping": [],
            "layout_calculation": [],
            "single_unit_render": [],
            "texture_operations": [],
            "ecs_queries": [],
        }

        # Fonts
        self.font_cache: Dict[int, pygame.font.Font] = {}
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)
        self.font_cache[24] = self.font
        self.font_cache[16] = self.small_font

        print("[Integrated] Unit Render System initialized - performance + features")

    def enable_performance_profiler(self, enabled: bool = True, interval: int = 60):
        """Enable/disable the profiler and configure print interval (frames)."""
        self.enable_profiler = enabled
        self.profiler_interval = interval

        if enabled:
            print(f"[UnitRenderSystem] Profiler enabled, prints every {interval} frames")
        else:
            print("[UnitRenderSystem] Profiler disabled")

    def _get_font(self, size: int) -> Optional[pygame.font.Font]:
        """Get cached font for requested size; create and cache on demand."""
        if size not in self.font_cache:
            try:
                # Clamp minimal font size to avoid errors
                font_size = max(size, 6)
                self.font_cache[size] = pygame.font.Font(
                    Path("rotk_env/assets/fonts/sh.otf"), font_size
                )
            except pygame.error as e:
                print(f"Warning: failed to load font size {size}: {e}")
                self.font_cache[size] = None
        return self.font_cache[size]

    def initialize(self, world) -> None:
        """Initialize unit renderer and load textures."""
        self.world = world
        self._load_unit_textures()

    def _load_unit_textures(self) -> None:
        """Load unit textures and pre-scale common sizes for performance."""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "units"
        )

        if not os.path.exists(assets_path):
            print(f"Warning: unit textures directory not found: {assets_path}")
            return

        # Pre-define common sizes to avoid runtime scaling
        common_sizes = [32, 40, 50, 64, 80, 100]

        # Iterate over factions and unit types
        for faction in Faction:
            faction_dir = os.path.join(assets_path, faction.value)
            if not os.path.exists(faction_dir):
                continue

            for unit_type in UnitType:
                texture_file = f"{unit_type.value}.png"
                texture_path = os.path.join(faction_dir, texture_file)

                if os.path.exists(texture_path):
                    try:
                        # Load original
                        original_texture = pygame.image.load(
                            texture_path
                        ).convert_alpha()

                        # Pre-scale for each common size
                        key = f"{faction.value}_{unit_type.value}"
                        for size in common_sizes:
                            scaled_texture = pygame.transform.scale(
                                original_texture, (size, size)
                            )
                            cache_key = (key, size)
                            self.scaled_texture_cache[cache_key] = scaled_texture

                        # Store original
                        self.unit_textures[key] = original_texture

                    except pygame.error as e:
                        print(f"Warning: failed to load unit texture {texture_path}: {e}")

        if len(self.unit_textures) > 0:
            self.textures_loaded = True
            print(
                f"[DEBUG] Loaded {len(self.unit_textures)} unit textures, pre-cached {len(self.scaled_texture_cache)} variants"
            )
        else:
            print("Warning: no unit textures loaded; falling back to circle rendering")

    def _add_step_time(self, step_name: str, elapsed_time: float):
        """Add timing sample to a step bucket (only when profiling)."""
        if not self.enable_profiler:
            return

        if step_name in self.step_times:
            self.step_times[step_name].append(elapsed_time)
            # 保持最近50次的数据
            if len(self.step_times[step_name]) > 50:
                self.step_times[step_name].pop(0)

    def _get_cached_texture(
        self, faction: Faction, unit_type: UnitType, size: int
    ) -> Optional[pygame.Surface]:
        """Get cached texture of exact size; create near-size on miss (with cap)."""
        key = f"{faction.value}_{unit_type.value}"
        cache_key = (key, size)

        if cache_key in self.scaled_texture_cache:
            self.cache_hits += 1
            return self.scaled_texture_cache[cache_key]

        # Cache miss: scale from original to requested size
        if key in self.unit_textures:
            self.cache_misses += 1
            original = self.unit_textures[key]
            scaled = pygame.transform.scale(original, (size, size))

            # Cache new size (bounded cache size)
            if len(self.scaled_texture_cache) < 200:
                self.scaled_texture_cache[cache_key] = scaled

            return scaled

        return None

    def _get_unit_texture(
        self, faction: Faction, unit_type: UnitType
    ) -> Optional[pygame.Surface]:
        """Get original texture for a faction/unit_type combo (compat)."""
        key = f"{faction.value}_{unit_type.value}"
        return self.unit_textures.get(key)

    def subscribe_events(self):
        """Subscribe to engine events (none needed for rendering)."""
        pass

    def update(self, delta_time: float) -> None:
        """Render units; optionally collect fine-grained profiling metrics."""
        # Detailed timings only when profiling
        update_start = time.time() if self.enable_profiler else None

        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        self.render_count += 1

        # Camera offset & zoom
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # Step 1: compute visible units
        step1_start = time.time() if self.enable_profiler else None
        visible_units = self._get_visible_units(camera_offset, zoom)
        if self.enable_profiler:
            step1_time = time.time() - step1_start
            self._add_step_time("get_visible_units", step1_time)

        # Step 2: choose rendering strategy
        step2_start = time.time() if self.enable_profiler else None
        render_strategy = "full_featured" if len(visible_units) <= 20 else "batch"
        if self.enable_profiler:
            step2_time = time.time() - step2_start
            self._add_step_time("render_decision", step2_time)

        # Step 3: render
        if render_strategy == "full_featured":
            step3_start = time.time() if self.enable_profiler else None
            self._render_units_full_featured(visible_units, camera_offset, zoom)
            if self.enable_profiler:
                step3_time = time.time() - step3_start
                self._add_step_time("full_featured_render", step3_time)
        else:
            step3_start = time.time() if self.enable_profiler else None
            self._render_units_batch(visible_units, camera_offset, zoom)
            if self.enable_profiler:
                step3_time = time.time() - step3_start
                self._add_step_time("batch_render", step3_time)

        # Step 4: animation overlays
        step4_start = time.time() if self.enable_profiler else None
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.render_damage_numbers()
        if self.enable_profiler:
            step4_time = time.time() - step4_start
            self._add_step_time("animation_render", step4_time)

        # Profiler print
        if self.enable_profiler and update_start:
            total_time = time.time() - update_start
            # Print at configured interval
            if self.render_count % self.profiler_interval == 0:
                self._print_detailed_performance_stats(
                    len(visible_units), render_strategy, total_time
                )

    def _get_visible_units(self, camera_offset: List[float], zoom: float) -> List[int]:
        """Compute units visible on screen bounds (keeps existing perf approach)."""
        visible_units = []

        # Screen bounds (with margin)
        margin = 100
        screen_left = (-camera_offset[0] - margin) / zoom
        screen_right = (GameConfig.WINDOW_WIDTH - camera_offset[0] + margin) / zoom
        screen_top = (-camera_offset[1] - margin) / zoom
        screen_bottom = (GameConfig.WINDOW_HEIGHT - camera_offset[1] + margin) / zoom

        # ECS query timing (if profiling)
        ecs_start = time.time() if self.enable_profiler else None
        entities = list(
            self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        )
        if self.enable_profiler:
            ecs_time = time.time() - ecs_start
            self._add_step_time("ecs_queries", ecs_time)

        for entity in entities:
            # Visibility timing (if profiling)
            visibility_start = time.time() if self.enable_profiler else None

            position = self.world.get_component(entity, HexPosition)
            if not position:
                continue

            # Check unit-level visibility
            if not self._is_unit_visible(entity):
                continue

            if self.enable_profiler:
                visibility_time = time.time() - visibility_start
                self._add_step_time("visibility_check", visibility_time)

            # Compute unit world position
            world_x, world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )

            # Screen bounds check
            if (
                screen_left <= world_x <= screen_right
                and screen_top <= world_y <= screen_bottom
            ):
                visible_units.append(entity)

        return visible_units

    def _render_units_full_featured(
        self, visible_units: List[int], camera_offset: List[float], zoom: float
    ):
        """Full-featured unit rendering for a small visible set."""
        if not visible_units:
            return

        # Animation system
        animation_system = self._get_animation_system()

        # Group by position (profiled)
        grouping_start = time.time() if self.enable_profiler else None
        units_by_position = {}
        for entity in visible_units:
            position = self.world.get_component(entity, HexPosition)
            if not position:
                continue

            pos_key = (position.col, position.row)
            if pos_key not in units_by_position:
                units_by_position[pos_key] = []
            units_by_position[pos_key].append(entity)

        if self.enable_profiler:
            grouping_time = time.time() - grouping_start
            self._add_step_time("position_grouping", grouping_time)

        # Render unit groups per tile
        for pos_key, units in units_by_position.items():
            group_start = time.time() if self.enable_profiler else None
            self._render_unit_group_full(
                pos_key, units, camera_offset, zoom, animation_system
            )
            if self.enable_profiler:
                group_time = time.time() - group_start
                self._add_step_time("single_unit_render", group_time)

    def _render_units_batch(
        self, visible_units: List[int], camera_offset: List[float], zoom: float
    ):
        """High-performance batch rendering for large visible sets."""
        if not visible_units:
            return

        # Group by tile position
        units_by_position = {}
        for entity in visible_units:
            position = self.world.get_component(entity, HexPosition)
            if position:
                pos_key = (position.col, position.row)
                if pos_key not in units_by_position:
                    units_by_position[pos_key] = []
                units_by_position[pos_key].append(entity)

        # Render per tile
        for pos_key, units in units_by_position.items():
            self._render_unit_group_optimized(pos_key, units, camera_offset, zoom)

    def _render_unit_group_full(
        self, pos_key, units, camera_offset, zoom, animation_system
    ):
        """Render a unit group with full visuals (multi/single faction layouts)."""
        # Group by faction (profiled)
        faction_start = time.time() if self.enable_profiler else None
        units_by_faction = {}
        for entity in units:
            unit = self.world.get_component(entity, Unit)
            if unit:
                if unit.faction not in units_by_faction:
                    units_by_faction[unit.faction] = []
                units_by_faction[unit.faction].append(entity)

        if self.enable_profiler:
            faction_time = time.time() - faction_start
            self._add_step_time("faction_grouping", faction_time)

        # Base screen position of the hex
        base_world_x, base_world_y = self.hex_converter.hex_to_pixel(
            pos_key[0], pos_key[1]
        )
        base_screen_x = (base_world_x * zoom) + camera_offset[0]
        base_screen_y = (base_world_y * zoom) + camera_offset[1]

        factions = list(units_by_faction.keys())
        total_factions = len(factions)

        if total_factions == 1:
            # Same faction: distribute evenly within the hex
            faction = factions[0]
            faction_units = units_by_faction[faction]
            self._render_same_faction_units(
                faction_units, base_screen_x, base_screen_y, zoom, animation_system
            )
        else:
            # Multiple factions: split into halves and distribute
            self._render_multi_faction_units(
                units_by_faction, base_screen_x, base_screen_y, zoom, animation_system
            )

    def _render_same_faction_units(self, units, base_x, base_y, zoom, animation_system):
        """Render multiple units of the same faction inside a single hex."""
        unit_count = len(units)
        if unit_count == 1:
            # Single unit: center
            self._render_single_unit_full(
                units[0], base_x, base_y, zoom, animation_system
            )
        else:
            # Layout calculation (profiled)
            layout_start = time.time() if self.enable_profiler else None
            positions = self._calculate_unit_positions_in_hex(
                unit_count, base_x, base_y, zoom
            )
            if self.enable_profiler:
                layout_time = time.time() - layout_start
                self._add_step_time("layout_calculation", layout_time)

            for i, entity in enumerate(units):
                if i < len(positions):
                    x, y = positions[i]
                    self._render_single_unit_full(entity, x, y, zoom, animation_system)

    def _render_multi_faction_units(
        self, units_by_faction, base_x, base_y, zoom, animation_system
    ):
        """Render units of multiple factions inside a single hex."""
        factions = list(units_by_faction.keys())

        # Compute area for each faction
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8

        if len(factions) == 2:
            # Two factions: left/right split
            faction1, faction2 = factions

            # Left center
            left_x = base_x - hex_radius * 0.3
            left_y = base_y

            # Right center
            right_x = base_x + hex_radius * 0.3
            right_y = base_y

            # Render faction 1 (left)
            units1 = units_by_faction[faction1]
            positions1 = self._calculate_unit_positions_in_area(
                len(units1), left_x, left_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units1):
                if i < len(positions1):
                    x, y = positions1[i]
                    self._render_single_unit_full(entity, x, y, zoom, animation_system)

            # Render faction 2 (right)
            units2 = units_by_faction[faction2]
            positions2 = self._calculate_unit_positions_in_area(
                len(units2), right_x, right_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units2):
                if i < len(positions2):
                    x, y = positions2[i]
                    self._render_single_unit_full(entity, x, y, zoom, animation_system)
        else:
            # 3+ factions: circular arrangement
            for i, faction in enumerate(factions):
                angle = (2 * math.pi * i) / len(factions)
                area_x = base_x + hex_radius * 0.4 * math.cos(angle)
                area_y = base_y + hex_radius * 0.4 * math.sin(angle)

                units = units_by_faction[faction]
                positions = self._calculate_unit_positions_in_area(
                    len(units), area_x, area_y, hex_radius * 0.4, zoom
                )
                for j, entity in enumerate(units):
                    if j < len(positions):
                        x, y = positions[j]
                        self._render_single_unit_full(
                            entity, x, y, zoom, animation_system
                        )

    def _render_unit_group_optimized(
        self,
        pos_key: Tuple[int, int],
        units: List[int],
        camera_offset: List[float],
        zoom: float,
    ):
        """Optimized unit-group rendering (fast path)."""
        if not units:
            return

        # Base screen position
        world_x, world_y = self.hex_converter.hex_to_pixel(pos_key[0], pos_key[1])
        base_screen_x = (world_x * zoom) + camera_offset[0]
        base_screen_y = (world_y * zoom) + camera_offset[1]

        # Simple layout: single unit centered
        if len(units) == 1:
            self._render_single_unit_fast(units[0], base_screen_x, base_screen_y, zoom)
        else:
            # Multiple units: simple ring layout
            radius = GameConfig.HEX_SIZE * zoom * 0.3
            for i, entity in enumerate(units):
                if i < 6:  # 最多显示6个单位
                    angle = (2 * math.pi * i) / len(units)
                    offset_x = radius * math.cos(angle)
                    offset_y = radius * math.sin(angle)
                    self._render_single_unit_fast(
                        entity,
                        base_screen_x + offset_x,
                        base_screen_y + offset_y,
                        zoom * 0.8,  # slightly smaller
                    )

    def _render_single_unit_full(
        self, entity, screen_x, screen_y, zoom, animation_system
    ):
        """Render a single unit with textures, health bar, icon, and status."""
        position = self.world.get_component(entity, HexPosition)
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)

        if not position or not unit or not unit_count:
            return

        # Use interpolated animation position if significantly different
        use_animation_pos = False
        if animation_system:
            render_pos = animation_system.get_unit_render_position(entity)
            if render_pos:
                world_x, world_y = render_pos
                target_world_x, target_world_y = self.hex_converter.hex_to_pixel(
                    position.col, position.row
                )
                distance = (
                    (world_x - target_world_x) ** 2 + (world_y - target_world_y) ** 2
                ) ** 0.5
                if distance > 5:
                    camera = self.world.get_singleton_component(Camera)
                    screen_x = (world_x * zoom) + camera.offset_x
                    screen_y = (world_y * zoom) + camera.offset_y
                    use_animation_pos = True

        # Dynamic scale by crowding
        base_radius = GameConfig.HEX_SIZE // 3
        if use_animation_pos:
            scale_factor = 1.0
        else:
            units_in_same_hex = self._get_units_in_same_hex(entity)
            unit_count_in_hex = len(units_in_same_hex)

            if unit_count_in_hex == 1:
                scale_factor = 1.0
            elif unit_count_in_hex <= 3:
                scale_factor = 0.8
            elif unit_count_in_hex <= 6:
                scale_factor = 0.7
            else:
                scale_factor = 0.6

        # Render unit itself (texture or fallback circle)
        texture_size = int(GameConfig.HEX_SIZE * zoom * scale_factor)
        # Texture op timing (if profiling)
        texture_start = time.time() if self.enable_profiler else None
        texture = self._get_cached_texture(unit.faction, unit.unit_type, texture_size)

        if texture and self.textures_loaded:
            # Texture path
            texture_rect = texture.get_rect(center=(int(screen_x), int(screen_y)))
            RMS.draw(texture, texture_rect.topleft)
        else:
            # Fallback: circle rendering
            unit_radius = int(base_radius * zoom)
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

        if self.enable_profiler:
            texture_time = time.time() - texture_start
            self._add_step_time("texture_operations", texture_time)

        # Count/health bar
        unit_radius = int(base_radius * zoom)
        self._render_unit_count_bar(
            screen_x, screen_y, unit_count, unit_radius, zoom, scale=scale_factor
        )

        # Type icon
        self._render_unit_icon(screen_x, screen_y, unit, zoom, scale=scale_factor)

        # Status indicator
        status = self.world.get_component(entity, UnitStatus)
        if status:
            self._render_unit_status(screen_x, screen_y, status, unit_radius, zoom)

    def _render_single_unit_fast(
        self, entity: int, screen_x: float, screen_y: float, zoom: float
    ):
        """Fast-path single unit rendering with pre-cached textures."""
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)

        if not unit or not unit_count:
            return

        # Compute base size
        base_size = int(GameConfig.HEX_SIZE * zoom)

        # Use pre-cached texture if available
        texture = self._get_cached_texture(unit.faction, unit.unit_type, base_size)

        if texture and self.textures_loaded:
            # Already at requested size; no extra scaling
            texture_rect = texture.get_rect(center=(int(screen_x), int(screen_y)))
            RMS.draw(texture, texture_rect.topleft)
        else:
            # Fallback: circle
            unit_radius = int(base_size // 2)
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

        # Simple health bar
        if unit_count.current_count < unit_count.max_count:
            self._render_simple_health_bar(screen_x, screen_y, unit_count, base_size)

    def _render_simple_health_bar(
        self, screen_x: float, screen_y: float, unit_count: UnitCount, unit_size: int
    ):
        """Simple health bar (fast path)."""
        bar_width = unit_size
        bar_height = 4
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - unit_size // 2 - 8

        # Compute ratio
        health_ratio = unit_count.current_count / unit_count.max_count
        fill_width = int(bar_width * health_ratio)

        # Background
        RMS.rect((100, 100, 100), (int(bar_x), int(bar_y), bar_width, bar_height))

        # Fill
        if fill_width > 0:
            color = (
                (0, 255, 0)
                if health_ratio > 0.7
                else (255, 255, 0) if health_ratio > 0.3 else (255, 0, 0)
            )
            RMS.rect(color, (int(bar_x), int(bar_y), fill_width, bar_height))

        # Outline
        RMS.rect((255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)

    def _calculate_unit_positions_in_hex(self, unit_count, center_x, center_y, zoom):
        """Evenly distribute positions inside a flat-top hex; avoid overlap."""
        positions = []
        # Base unit radius
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8
        # Usable hex radius (leave margin)
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8

        if unit_count == 1:
            positions.append((center_x, center_y))
        elif unit_count == 2:
            offset = max(unit_radius * 1.2, hex_radius * 0.3)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            offset = max(unit_radius * 1.2, hex_radius * 0.4)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        elif unit_count == 4:
            offset = max(unit_radius * 1.1, hex_radius * 0.35)
            positions.append((center_x - offset, center_y - offset))
            positions.append((center_x + offset, center_y - offset))
            positions.append((center_x - offset, center_y + offset))
            positions.append((center_x + offset, center_y + offset))
        elif unit_count == 5:
            center_pos = (center_x, center_y)
            positions.append(center_pos)
            offset = max(unit_radius * 1.3, hex_radius * 0.4)
            for i in range(4):
                angle = (math.pi / 2) * i
                x = center_x + offset * math.cos(angle)
                y = center_y + offset * math.sin(angle)
                positions.append((x, y))
        elif unit_count == 6:
            radius = max(unit_radius * 1.2, hex_radius * 0.45)
            for i in range(6):
                angle = (2 * math.pi * i) / 6
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions.append((x, y))
        else:
            # More units: dual-ring layouts
            if unit_count <= 12:
                radius = max(unit_radius * 1.1, hex_radius * 0.5)
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # Inner ring 6, outer ring remaining
                inner_radius = max(unit_radius * 1.0, hex_radius * 0.3)
                for i in range(6):
                    angle = (2 * math.pi * i) / 6
                    x = center_x + inner_radius * math.cos(angle)
                    y = center_y + inner_radius * math.sin(angle)
                    positions.append((x, y))

                outer_count = unit_count - 6
                outer_radius = max(unit_radius * 1.2, hex_radius * 0.6)
                for i in range(outer_count):
                    angle = (2 * math.pi * i) / outer_count
                    x = center_x + outer_radius * math.cos(angle)
                    y = center_y + outer_radius * math.sin(angle)
                    positions.append((x, y))

        return positions

    def _calculate_unit_positions_in_area(
        self, unit_count, center_x, center_y, area_radius, zoom
    ):
        """Evenly distribute positions within a circular area; avoid overlap."""
        positions = []
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8

        if unit_count == 1:
            positions.append((center_x, center_y))
        elif unit_count == 2:
            offset = max(unit_radius * 1.2, area_radius * 0.6)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            offset = max(unit_radius * 1.1, area_radius * 0.7)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        else:
            radius = max(unit_radius * 1.0, area_radius * 0.8)
            min_distance = unit_radius * 2.2
            circle_circumference = 2 * math.pi * radius
            max_units_on_circle = int(circle_circumference / min_distance)

            if unit_count <= max_units_on_circle:
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # Compact grid as fallback
                cols = int(math.ceil(math.sqrt(unit_count)))
                rows = int(math.ceil(unit_count / cols))

                grid_spacing = max(unit_radius * 2.2, area_radius * 2 / max(cols, rows))
                start_x = center_x - (cols - 1) * grid_spacing / 2
                start_y = center_y - (rows - 1) * grid_spacing / 2

                for i in range(unit_count):
                    row = i // cols
                    col = i % cols
                    x = start_x + col * grid_spacing
                    y = start_y + row * grid_spacing
                    positions.append((x, y))

        return positions

    def _render_unit_count_bar(
        self, screen_x, screen_y, unit_count, unit_radius, zoom, scale=1.0
    ):
        """Render unit count bar (health/strength proxy)."""
        if unit_count.current_count <= 1:
            return

        bar_width = int(unit_radius * 2 * zoom * scale)
        bar_height = int(5 * zoom * scale)
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - unit_radius - int(10 * zoom * scale)

        fill_ratio = unit_count.current_count / unit_count.max_count
        fill_width = int(bar_width * fill_ratio)

        # Background
        RMS.rect((100, 100, 100), (bar_x, bar_y, bar_width, bar_height))

        # Fill
        if fill_ratio > 0.7:
            fill_color = (0, 255, 0)  # green
        elif fill_ratio > 0.3:
            fill_color = (255, 255, 0)  # yellow
        else:
            fill_color = (255, 0, 0)  # red

        if fill_width > 0:
            RMS.rect(fill_color, (bar_x, bar_y, fill_width, bar_height))

        # Outline
        RMS.rect((255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)

    def _render_unit_icon(self, screen_x, screen_y, unit, zoom, scale=1.0):
        """Render unit type icon label."""
        unit_symbols = {
            UnitType.INFANTRY: "Infantry",
            UnitType.CAVALRY: "Cavalry",
            UnitType.ARCHER: "Archer",
        }

        symbol = unit_symbols.get(unit.unit_type, "?")
        font_size = int(14 * zoom * scale)

        if font_size < 8:
            return

        try:
            font = self._get_font(font_size)
            if font:
                text_surface = font.render(symbol, True, (255, 255, 255))
                text_rect = text_surface.get_rect(center=(int(screen_x), int(screen_y)))
                RMS.draw(text_surface, text_rect)
        except:
            pass

    def _render_unit_status(
        self,
        screen_x: float,
        screen_y: float,
        status: UnitStatus,
        unit_radius: int,
        zoom: float = 1.0,
    ):
        """Render unit status indicator dot near the token."""
        if not status:
            return

        status_colors = {
            "idle": (128, 128, 128),
            "moving": (0, 255, 255),
            "combat": (255, 0, 0),
            "hidden": (128, 0, 128),
            "resting": (0, 255, 0),
        }

        if status.current_status in status_colors:
            indicator_size = int(4 * zoom)
            indicator_x = screen_x + unit_radius * 0.7
            indicator_y = screen_y - unit_radius * 0.7

            color = status_colors[status.current_status]
            RMS.circle(color, (int(indicator_x), int(indicator_y)), indicator_size)
            RMS.circle(
                (0, 0, 0), (int(indicator_x), int(indicator_y)), indicator_size, 1
            )

    def _is_unit_visible(self, unit_entity: int) -> bool:
        """Check if a unit is visible considering fog-of-war and view faction."""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not fog_of_war or not position or not unit or not ui_state:
            return True

        # God view: show all
        if ui_state.god_mode:
            return True

        # Determine current viewing faction
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # Own faction always visible
        if unit.faction == view_faction:
            return True

        # Check tile in viewing faction vision
        current_vision = fog_of_war.faction_vision.get(view_faction, set())
        return (position.col, position.row) in current_vision

    def _get_units_in_same_hex(self, target_entity):
        """Get all units located in the same hex as the target entity (visible only)."""
        target_position = self.world.get_component(target_entity, HexPosition)
        if not target_position:
            return [target_entity]

        units_in_hex = []
        for entity in (
            self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        ):
            if not self._is_unit_visible(entity):
                continue

            position = self.world.get_component(entity, HexPosition)
            if (
                position
                and position.col == target_position.col
                and position.row == target_position.row
            ):
                units_in_hex.append(entity)

        return units_in_hex

    def _get_animation_system(self):
        """Get AnimationSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def get_performance_stats(self) -> dict:
        """Return snapshot of render/cache stats."""
        cache_ratio = (
            self.cache_hits / max(1, self.cache_hits + self.cache_misses) * 100
        )
        return {
            "render_count": self.render_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": cache_ratio,
            "cached_textures": len(self.scaled_texture_cache),
        }

    def _print_detailed_performance_stats(
        self, visible_count: int, strategy: str, total_time: float
    ):
        """Print detailed profiling statistics in a readable format."""
        print("\n" + "=" * 80)
        print(
            f"[UnitRenderSystem] Detailed Profiling - visible: {visible_count}, strategy: {strategy}"
        )
        print(f"Total time: {total_time*1000:.2f}ms")
        print("=" * 80)

        # Average per-step times
        step_averages = {}
        for step_name, times in self.step_times.items():
            if times:
                avg_time = sum(times) / len(times)
                step_averages[step_name] = avg_time

        # Sort by cost
        sorted_steps = sorted(step_averages.items(), key=lambda x: x[1], reverse=True)

        print("Step cost ranking:")
        for step_name, avg_time in sorted_steps:
            percentage = (avg_time / total_time * 100) if total_time > 0 else 0
            print(f"  {step_name:25} {avg_time*1000:8.2f}ms ({percentage:5.1f}%)")

        # Cache stats
        cache_ratio = (
            self.cache_hits / max(1, self.cache_hits + self.cache_misses) * 100
        )
        print(
            f"\nCache hit ratio: {cache_ratio:.1f}% (hits:{self.cache_hits}, misses:{self.cache_misses})"
        )
        print("=" * 80)
