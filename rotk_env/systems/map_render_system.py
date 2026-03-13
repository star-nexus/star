"""
Map Render System - High-performance, fully featured renderer
- Texture-backed hex rendering with intelligent caching
- Fog of war and explored-state overlays
- Territory boundaries, fortification markers, and city markers
- Coordinate overlays with zoom-aware styling

Optimized to render only visible tiles with stable visuals across zoom and camera.
"""

import pygame
import os
import random
import math
from typing import Tuple, Set, List, Dict, Optional
from framework import System, RMS
from ..components import (
    MapData,
    Terrain,
    TerritoryControl,
    GameState,
    FogOfWar,
    HexPosition,
    Unit,
    Camera,
    UIState,
)
from ..prefabs.config import GameConfig, TerrainType, HexOrientation, Faction
from ..utils.hex_utils import HexConverter


class MapRenderSystem(System):
    """Integrated high-performance map renderer with complete feature set."""

    def __init__(self):
        super().__init__(priority=1)  # Lowest priority → renders first (bottom layer)
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

        # Terrain texture resources
        self.terrain_textures: Dict[TerrainType, List[pygame.Surface]] = {}
        self.tile_texture_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.texture_loaded = False

        # Performance caches
        self.visible_tiles_cache: Set[Tuple[int, int]] = set()
        self.last_camera_pos = (0, 0)
        self.last_zoom = 1.0
        self.cache_tolerance = 50  # camera movement tolerance

        # Fog of war surfaces / hashing
        self.fog_surface = None
        self.fog_dirty = True
        self.last_fog_hash = 0

        # Stats (debug)
        self.frame_count = 0
        self.render_calls_saved = 0

        print("[Integrated] Map Render System initialized - performance + features")

    def initialize(self, world) -> None:
        """Initialize the map render system and preload textures."""
        self.world = world
        self._load_terrain_textures()

    def _load_terrain_textures(self) -> None:
        """Load terrain textures from assets if available; fallback to color fills."""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "terrain"
        )

        if not os.path.exists(assets_path):
            print(f"Warning: terrain texture directory not found: {assets_path}")
            return

        # Initialize containers for every terrain type
        for terrain_type in TerrainType:
            self.terrain_textures[terrain_type] = []

        # Walk each terrain directory and load textures
        for terrain_type in TerrainType:
            terrain_dir = os.path.join(assets_path, terrain_type.value)

            if os.path.exists(terrain_dir):
                # Load all textures for this terrain
                for filename in os.listdir(terrain_dir):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                        texture_path = os.path.join(terrain_dir, filename)
                        try:
                            texture = pygame.image.load(texture_path).convert_alpha()
                            # Pre-scale textures to standard size to reduce runtime scaling
                            hex_size = GameConfig.HEX_SIZE * 2
                            texture = pygame.transform.scale(
                                texture, (hex_size, hex_size)
                            )
                            self.terrain_textures[terrain_type].append(texture)
                        except pygame.error as e:
                            print(f"Warning: failed to load texture {texture_path}: {e}")

        loaded_count = sum(len(textures) for textures in self.terrain_textures.values())
        if loaded_count > 0:
            self.texture_loaded = True
            print(f"[Integrated] Loaded {loaded_count} terrain textures")
        else:
            print("Warning: no terrain textures loaded; will use color rendering")

    def load_seamless_hex_texture(self, texture_path, hex_size):
        """Load a hex texture and create a tightly cropped, seamless variant."""
        # Load original texture
        texture = pygame.image.load(texture_path).convert_alpha()

        # Create mask surface to extract opaque pixels
        mask_surface = pygame.Surface(texture.get_size(), pygame.SRCALPHA)
        mask_surface.fill((0, 0, 0, 0))  # fully transparent base

        # Copy only opaque pixels
        for x in range(texture.get_width()):
            for y in range(texture.get_height()):
                r, g, b, a = texture.get_at((x, y))
                if a > 0:
                    mask_surface.set_at((x, y), (r, g, b, a))

        # Compute tight bounds around opaque content
        min_x, min_y = mask_surface.get_width(), mask_surface.get_height()
        max_x, max_y = 0, 0

        # Find bounds of opaque pixels
        for x in range(mask_surface.get_width()):
            for y in range(mask_surface.get_height()):
                if mask_surface.get_at((x, y))[3] > 0:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        # Size of the hex content
        hex_width = max_x - min_x + 1
        hex_height = max_y - min_y + 1

        # Create tight surface (flat-top hex uses width as reference)
        final_texture = pygame.Surface((hex_width, hex_width), pygame.SRCALPHA)
        final_texture.fill((0, 0, 0, 0))  # transparent background

        # Blit the opaque region into the new surface
        final_texture.blit(mask_surface, (0, 0), (min_x, min_y, hex_width, hex_height))

        # Scale preserving hex proportions
        scale_factor = min(hex_size / hex_width, hex_size / hex_height)
        new_width = int(hex_width * scale_factor)
        new_height = int(hex_height * scale_factor)

        # High-quality rescale
        final_texture = pygame.transform.smoothscale(
            final_texture, (new_width, new_height)
        )

        return final_texture

    def _get_terrain_texture(
        self, terrain_type: TerrainType, tile_key: Tuple[int, int]
    ) -> Optional[pygame.Surface]:
        """Get the terrain texture; pick a stable choice per tile when multiple exist."""
        if not self.texture_loaded or terrain_type not in self.terrain_textures:
            return None

        textures = self.terrain_textures[terrain_type]
        if not textures:
            return None

        # Use cached texture if available
        if tile_key in self.tile_texture_cache:
            return self.tile_texture_cache[tile_key]

        # Seed by tile coordinates for stable, deterministic selection
        random.seed(tile_key[0] * 10007 + tile_key[1] * 10009)
        selected_texture = random.choice(textures)

        # Cache selected texture
        self.tile_texture_cache[tile_key] = selected_texture

        # Restore RNG
        random.seed()

        return selected_texture

    def subscribe_events(self):
        """Subscribe to engine events (none needed for rendering)."""
        pass

    def set_hex_orientation(self, orientation: HexOrientation) -> None:
        """Set hex orientation and clear caches if changed."""
        if self.hex_converter.orientation != orientation:
            self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)
            # Clear cached textures as shape changed
            self.tile_texture_cache.clear()
            print(f"Hex orientation switched to: {orientation.value}")

    def toggle_hex_orientation(self) -> None:
        """Toggle hex orientation between flat-top and pointy-top."""
        current = self.hex_converter.orientation
        new_orientation = (
            HexOrientation.FLAT_TOP
            if current == HexOrientation.POINTY_TOP
            else HexOrientation.POINTY_TOP
        )
        self.set_hex_orientation(new_orientation)

    def update(self, delta_time: float) -> None:
        """Render the map with visible-region optimization and full features."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        self.frame_count += 1
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # Core optimization: smart visible-region calculation
        visible_tiles = self._get_visible_tiles_smart(camera_offset, zoom)

        # Layered rendering: map → territory boundaries → fog of war → coordinates
        self._render_map_optimized(visible_tiles, camera_offset, zoom)
        self._render_territory_boundaries_optimized(visible_tiles, camera_offset, zoom)
        self._render_fog_of_war_optimized(visible_tiles, camera_offset, zoom)
        self._render_coordinates_optimized(visible_tiles, camera_offset, zoom)

        # Debug stats
        if self.frame_count % 300 == 0:
            map_data = self.world.get_singleton_component(MapData)
            total_tiles = len(map_data.tiles) if map_data else 0
            tiles_saved = total_tiles - len(visible_tiles)
            print(
                f"[DEBUG] Frames: {self.frame_count}, visible tiles: {len(visible_tiles)}/{total_tiles}, saved: {tiles_saved}"
            )

    def _get_visible_tiles_smart(
        self, camera_offset: List[float], zoom: float
    ) -> Set[Tuple[int, int]]:
        """Smart visible-region calculation with caching."""
        current_camera_pos = (camera_offset[0], camera_offset[1])

        # Reuse cache if camera/zoom hasn't meaningfully changed
        if (
            abs(current_camera_pos[0] - self.last_camera_pos[0]) < self.cache_tolerance
            and abs(current_camera_pos[1] - self.last_camera_pos[1])
            < self.cache_tolerance
            and abs(zoom - self.last_zoom) < 0.05
        ):
            return self.visible_tiles_cache

        # Recompute visible region
        visible_tiles = set()

        # Screen bounds in world coordinates (with margin)
        margin = GameConfig.HEX_SIZE * 2
        screen_bounds = {
            "left": (-camera_offset[0] - margin) / zoom,
            "right": (GameConfig.WINDOW_WIDTH - camera_offset[0] + margin) / zoom,
            "top": (-camera_offset[1] - margin) / zoom,
            "bottom": (GameConfig.WINDOW_HEIGHT - camera_offset[1] + margin) / zoom,
        }

        # Estimate hex coordinate ranges near screen center
        center_q = int(-camera_offset[0] / zoom / (GameConfig.HEX_SIZE * 1.5))
        center_r = int(-camera_offset[1] / zoom / (GameConfig.HEX_SIZE * 0.866))

        search_radius = max(
            int(GameConfig.WINDOW_WIDTH / zoom / GameConfig.HEX_SIZE) + 3,
            int(GameConfig.WINDOW_HEIGHT / zoom / GameConfig.HEX_SIZE) + 3,
        )

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return visible_tiles

        # Search visible tiles within the estimated range
        for q in range(center_q - search_radius, center_q + search_radius + 1):
            for r in range(center_r - search_radius, center_r + search_radius + 1):
                if (q, r) not in map_data.tiles:
                    continue

                # Check if tile is on screen
                world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

                if (
                    screen_bounds["left"] <= world_x <= screen_bounds["right"]
                    and screen_bounds["top"] <= world_y <= screen_bounds["bottom"]
                ):
                    visible_tiles.add((q, r))

        # Update caches
        self.visible_tiles_cache = visible_tiles
        self.last_camera_pos = current_camera_pos
        self.last_zoom = zoom

        return visible_tiles

    def _render_map_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float,
    ):
        """Optimized map rendering - draw only visible tiles, keep full visuals."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Draw only the visible tiles
        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if not tile_entity:
                continue

            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # Compute screen coordinates
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Try texture-backed rendering first
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture and self.texture_loaded:
                # Render with texture
                self._render_hex_with_texture(texture, screen_x, screen_y, zoom)

                # Add city marker for city tiles
                if terrain.terrain_type == TerrainType.CITY:
                    self._render_city_marker(q, r, camera_offset, zoom)
            else:
                # Fallback: solid color hex
                self._render_hex_with_color(
                    terrain.terrain_type, q, r, camera_offset, zoom
                )

    def _render_hex_with_texture(
        self, texture: pygame.Surface, center_x: float, center_y: float, zoom: float
    ):
        """Render a hex tile using a texture with zoom-aware scaling."""
        # Smart scaling: avoid rescaling when zoom is ~1.0
        if abs(zoom - 1.0) < 0.05:
            # Use original texture size when zoom≈1.0
            texture_rect = texture.get_rect(center=(int(center_x), int(center_y)))
            RMS.draw(texture, texture_rect.topleft)
        else:
            # Scale as needed
            scaled_size = int(GameConfig.HEX_SIZE * 2 * zoom)
            if scaled_size <= 0:
                return

            scaled_texture = pygame.transform.scale(texture, (scaled_size, scaled_size))
            texture_x = center_x - scaled_size // 2
            texture_y = center_y - scaled_size // 2
            RMS.draw(scaled_texture, (texture_x, texture_y))

    def _render_hex_with_color(
        self,
        terrain_type: TerrainType,
        q: int,
        r: int,
        camera_offset: List[float],
        zoom: float,
    ):
        """Render a hex tile with solid color (fallback path)."""
        # Get terrain color
        terrain_color = GameConfig.TERRAIN_COLORS.get(terrain_type, (128, 128, 128))

        # Draw hex with outline (scaled)
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
            for x, y in corners
        ]

        RMS.polygon(terrain_color, screen_corners)
        RMS.polygon((0, 0, 0), screen_corners, 1)

        # Add city marker for city tiles
        if terrain_type == TerrainType.CITY:
            self._render_city_marker(q, r, camera_offset, zoom)

    def _render_fog_of_war_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Optimized fog of war - process only visible tiles, preserve full effect."""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)

        if not game_state or not fog_of_war or not ui_state:
            return

        # God mode: skip fog rendering
        if ui_state.god_mode:
            return

        # Determine current view faction
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # Tiles visible and explored by the viewing faction
        visible_faction_tiles = fog_of_war.faction_vision.get(view_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(view_faction, set())

        # Layer for explored-but-not-currently-visible region fog
        explored_fog_surface = pygame.Surface(
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
        )

        # Process only visible tiles on screen
        for q, r in visible_tiles:
            # Compute screen position
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            if (q, r) in visible_faction_tiles:
                # In current vision: no fog applied
                continue
            elif (q, r) in explored_tiles:
                # Explored but not currently seen: semi-transparent overlay
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
            else:
                # Unexplored: full black
                pygame.draw.polygon(
                    explored_fog_surface,
                    GameConfig.FOG_UNEXPLORED_COLOR,
                    screen_corners,
                )

        # Apply fog overlay
        RMS.draw(explored_fog_surface, (0, 0))

        # Draw an outer green outline for the vision boundary (optional)
        # self._render_vision_boundary_optimized(
        #     visible_faction_tiles, camera_offset, zoom
        # )

    def _render_vision_boundary_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Optional vision boundary rendering (unit-centric circles)."""
        if not visible_tiles:
            return

        # Get current player's units
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return

        current_faction = game_state.current_player

        # Draw a vision circle for each friendly unit
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position or unit.faction != current_faction:
                continue

            # Compute unit center on screen
            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = (center_world_x * zoom) + camera_offset[0]
            center_screen_y = (center_world_y * zoom) + camera_offset[1]

            # Screen bounds guard (only likely-visible units)
            margin = 200 * zoom
            if (
                center_screen_x < -margin
                or center_screen_x > GameConfig.WINDOW_WIDTH + margin
                or center_screen_y < -margin
                or center_screen_y > GameConfig.WINDOW_HEIGHT + margin
            ):
                continue

            unit_stats = GameConfig.UNIT_STATS.get(unit.unit_type)
            if not unit_stats:
                continue

            vision_range = unit_stats.vision_range

            # Draw circle
            circle_radius = int(vision_range * GameConfig.HEX_SIZE * 1.5 * zoom)
            RMS.circle(
                GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                (int(center_screen_x), int(center_screen_y)),
                circle_radius,
                2,
            )

    def _render_territory_boundaries_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Optimized territory boundaries - process only visible tiles."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Traverse visible tiles and draw territory control info
        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if not tile_entity:
                continue

            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control or not territory_control.controlling_faction:
                continue

            # Compute screen coordinates
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Faction color
            faction_color = self._get_faction_color(
                territory_control.controlling_faction
            )
            if not faction_color:
                continue

            # Compute hex corners for boundary
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            # Style width/color based on capture progress and fortification
            border_width = self._get_border_width(territory_control)
            border_color = self._get_border_color(territory_control, faction_color)

            # Draw boundary
            RMS.polygon(border_color, screen_corners, border_width)

            # Draw fortification marker if any
            if territory_control.fortification_level > 0:
                self._render_fortification_marker(
                    screen_x, screen_y, territory_control, zoom
                )

    def _get_faction_color(self, faction: Faction) -> Optional[Tuple[int, int, int]]:
        """Get display color for a faction."""
        faction_colors = {
            Faction.WEI: (0, 100, 255),  # blue
            Faction.SHU: (255, 50, 50),  # red
            Faction.WU: (50, 255, 50),  # green
        }
        return faction_colors.get(faction)

    def _get_border_width(self, territory_control: TerritoryControl) -> int:
        """Determine boundary width from capture progress and fortification level."""
        base_width = 2

        # Adjust by capture progress
        if territory_control.capture_progress >= 0.8:
            base_width += 1
        elif territory_control.capture_progress <= 0.3:
            base_width = max(1, base_width - 1)

        # Fortification level influence
        base_width += territory_control.fortification_level

        return min(base_width, 5)  # cap max width

    def _get_border_color(
        self, territory_control: TerritoryControl, faction_color: Tuple[int, int, int]
    ) -> Tuple[int, int, int]:
        """Adjust boundary color intensity based on control state."""
        r, g, b = faction_color

        # Scale brightness by capture progress (at least 50%)
        intensity = max(0.5, territory_control.capture_progress)

        # Apply brightness scaling
        r = int(r * (0.5 + 0.5 * intensity))
        g = int(g * (0.5 + 0.5 * intensity))
        b = int(b * (0.5 + 0.5 * intensity))

        return (min(255, r), min(255, g), min(255, b))

    def _render_fortification_marker(
        self,
        center_x: float,
        center_y: float,
        territory_control: TerritoryControl,
        zoom: float,
    ):
        """Render fortification marker - inset border colored by level."""
        if territory_control.fortification_level <= 0:
            return

        # Pick color by level
        fortification_colors = {
            1: (184, 115, 51),  # copper
            2: (192, 192, 192),  # silver
            3: (255, 215, 0),  # gold
        }

        level = min(territory_control.fortification_level, 3)  # cap at 3
        border_color = fortification_colors.get(level, fortification_colors[1])

        # Use hex_converter corners; apply slight inset for inner border
        hex_size_scaled = GameConfig.HEX_SIZE * zoom * 0.9

        # Get canonical corners (0,0 relative), then scale/translate
        corners = self.hex_converter.get_hex_corners(0, 0)

        # Scale and place at center
        hex_points = []
        scale_factor = 0.9

        for corner_x, corner_y in corners:
            # Scale and translate to target center
            scaled_x = corner_x * scale_factor * zoom + center_x
            scaled_y = corner_y * scale_factor * zoom + center_y
            hex_points.append((int(scaled_x), int(scaled_y)))

        # Draw fortification border with level-driven width
        border_width = max(3, int(4 * zoom * level))

        # Draw
        RMS.polygon(border_color, hex_points, border_width)

    def _render_city_marker(
        self, q: int, r: int, camera_offset: List[float], zoom: float
    ):
        """Render a city marker at tile center."""
        # Compute city center position
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        center_x = (world_x * zoom) + camera_offset[0]
        center_y = (world_y * zoom) + camera_offset[1]

        # Marker size
        marker_size = int(12 * zoom)
        city_color = (211, 211, 211)  # light gray = city building

        # Draw circle marker
        RMS.circle(
            city_color,
            (int(center_x), int(center_y)),
            marker_size,
        )
        RMS.circle(
            (0, 0, 0), (int(center_x), int(center_y)), marker_size, 2  # black outline
        )

    def _render_coordinates_optimized(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Render coordinates overlay for visible tiles only."""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.show_coordinates:
            return

        # Font size adapts to zoom
        font_size = max(10, int(12 * zoom))

        # Avoid showing unreadable labels at very small zoom
        if zoom < 0.3:
            return

        # Iterate visible tiles and draw coordinate labels
        for q, r in visible_tiles:
            # Compute hex center on screen
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            center_x = (world_x * zoom) + camera_offset[0]
            center_y = (world_y * zoom) + camera_offset[1]

            # Text string
            coord_text = f"({q},{r})"

            # Draw label
            self._render_coordinate_text(coord_text, center_x, center_y, font_size)

    def _render_coordinate_text(self, text: str, x: float, y: float, font_size: int):
        """Render a coordinate label with simple 4-direction outline."""
        # Create font (fallback to system if default fails)
        try:
            font = pygame.font.Font(None, font_size)
        except:
            font = pygame.font.SysFont("arial", font_size)

        # Colors
        text_color = (255, 255, 255)  # white
        outline_color = (0, 0, 0)  # black outline

        # Main surface
        text_surface = font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=(int(x), int(y)))

        # Draw outline in 4 directions
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            outline_surface = font.render(text, True, outline_color)
            outline_rect = text_rect.copy()
            outline_rect.move_ip(dx, dy)
            RMS.draw(outline_surface, outline_rect.topleft)

        # Draw main text
        RMS.draw(text_surface, text_rect.topleft)
