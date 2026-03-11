"""
Map Render System - responsible for rendering the map, terrain, and fog of war.
"""

import pygame
import os
import random
from typing import Tuple, Set, List, Dict, Optional, Optional
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
    """Map render system."""

    def __init__(self):
        super().__init__(priority=1)  # Lowest priority, renders first (bottom layer)
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.terrain_textures: Dict[TerrainType, List[pygame.Surface]] = {}
        self.tile_texture_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.texture_loaded = False

    def initialize(self, world) -> None:
        """Initialize the map render system."""
        self.world = world
        self._load_terrain_textures()

    def _load_terrain_textures(self) -> None:
        """Load terrain textures."""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "terrain"
        )

        if not os.path.exists(assets_path):
            print(f"Warning: terrain texture directory not found: {assets_path}")
            return

        # Initialize texture lists for all terrain types
        for terrain_type in TerrainType:
            self.terrain_textures[terrain_type] = []

        # Traverse all terrain type directories
        for terrain_type in TerrainType:
            terrain_dir = os.path.join(assets_path, terrain_type.value)

            if os.path.exists(terrain_dir):
                # Load all textures for this terrain type
                for filename in os.listdir(terrain_dir):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                        texture_path = os.path.join(terrain_dir, filename)
                        try:
                            texture = pygame.image.load(texture_path).convert_alpha()
                            # Scale texture to appropriate size
                            hex_size = int(GameConfig.HEX_SIZE * 10)
                            # texture = self.load_seamless_hex_texture(
                            #     texture_path, hex_size
                            # )
                            texture = pygame.transform.scale(
                                texture, (hex_size, hex_size)
                            )
                            self.terrain_textures[terrain_type].append(texture)
                        except pygame.error as e:
                            print(f"Warning: failed to load texture {texture_path}: {e}")

        # Check loading results
        loaded_count = sum(len(textures) for textures in self.terrain_textures.values())
        if loaded_count > 0:
            self.texture_loaded = True
            print(f"Successfully loaded {loaded_count} terrain textures")
        else:
            print("Warning: no terrain textures loaded, falling back to color rendering")

    def load_seamless_hex_texture(self, texture_path, hex_size):
        """Load a hex texture and create a seamlessly fitted version."""
        # Load original texture
        texture = pygame.image.load(texture_path).convert_alpha()

        # Create mask surface (to extract opaque region)
        mask_surface = pygame.Surface(texture.get_size(), pygame.SRCALPHA)
        mask_surface.fill((0, 0, 0, 0))  # Fully transparent

        # Iterate pixels, copying only opaque ones
        for x in range(texture.get_width()):
            for y in range(texture.get_height()):
                r, g, b, a = texture.get_at((x, y))
                if a > 0:  # Only process opaque pixels
                    mask_surface.set_at((x, y), (r, g, b, a))

        # Calculate actual hex boundary
        min_x, min_y = mask_surface.get_width(), mask_surface.get_height()
        max_x, max_y = 0, 0

        # Find boundary of opaque pixels
        for x in range(mask_surface.get_width()):
            for y in range(mask_surface.get_height()):
                if mask_surface.get_at((x, y))[3] > 0:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        # Calculate actual hex dimensions
        hex_width = max_x - min_x + 1
        hex_height = max_y - min_y + 1

        # Create exact-size surface - texture is flat-top, so use R as width
        final_texture = pygame.Surface((hex_width, hex_width), pygame.SRCALPHA)
        final_texture.fill((0, 0, 0, 0))  # Transparent background

        # Copy opaque region to new surface
        final_texture.blit(mask_surface, (0, 0), (min_x, min_y, hex_width, hex_height))

        # Calculate scale factor (preserve hex proportions)
        scale_factor = min(hex_size / hex_width, hex_size / hex_height)
        new_width = int(hex_width * scale_factor)
        new_height = int(hex_height * scale_factor)
        # Proportional scaling

        # High-quality rescale
        final_texture = pygame.transform.smoothscale(
            final_texture, (new_width, new_height)
        )

        return final_texture

    def _get_terrain_texture(
        self, terrain_type: TerrainType, tile_key: Tuple[int, int]
    ) -> Optional[pygame.Surface]:
        """Get terrain texture; if multiple exist, pick a stable one per tile."""
        if not self.texture_loaded or terrain_type not in self.terrain_textures:
            return None

        textures = self.terrain_textures[terrain_type]
        if not textures:
            return None

        # Return cached texture if available
        if tile_key in self.tile_texture_cache:
            return self.tile_texture_cache[tile_key]

        # Use tile coordinates as seed for deterministic texture selection
        random.seed(tile_key[0] * 10007 + tile_key[1] * 10009)
        selected_texture = random.choice(textures)

        # Cache selected texture
        self.tile_texture_cache[tile_key] = selected_texture

        # Restore random seed
        random.seed()

        return selected_texture

    def subscribe_events(self):
        """Subscribe to events (map render system requires none)."""
        pass

    def set_hex_orientation(self, orientation: HexOrientation) -> None:
        """Set hex orientation."""
        if self.hex_converter.orientation != orientation:
            self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)
            # Clear texture cache because the hex shape has changed
            self.tile_texture_cache.clear()
            print(f"Hex orientation switched to: {orientation.value}")

    def toggle_hex_orientation(self) -> None:
        """Toggle hex orientation."""
        current = self.hex_converter.orientation
        new_orientation = (
            HexOrientation.FLAT_TOP
            if current == HexOrientation.POINTY_TOP
            else HexOrientation.POINTY_TOP
        )
        self.set_hex_orientation(new_orientation)

    def update(self, delta_time: float) -> None:
        """Update map rendering."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # Compute camera offset
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # Render map and fog of war
        self._render_map(camera_offset, zoom)
        self._render_territory_boundaries(camera_offset, zoom)
        self._render_fog_of_war(camera_offset, zoom)

    def _render_map(self, camera_offset: List[float], zoom: float = 1.0):
        """Render the map."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Iterate all map tiles
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # Compute screen position (apply zoom)
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Check if within screen bounds (accounting for zoom)
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
                or screen_y < -hex_size_scaled
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
            ):
                continue

            # Try to get terrain texture
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture and self.texture_loaded:
                # Render with texture
                self._render_hex_with_texture(texture, screen_x, screen_y, zoom)

                # Add city marker for city terrain
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.CITY:
                    self._render_city_marker(q, r, camera_offset, zoom)
            else:
                # Fallback: render with color
                self._render_hex_with_color(
                    terrain.terrain_type, q, r, camera_offset, zoom
                )

    def _render_hex_with_texture(
        self, texture: pygame.Surface, center_x: float, center_y: float, zoom: float
    ):
        """Render a hex tile using a texture."""
        # Scale texture
        scaled_size = int(GameConfig.HEX_SIZE * 2 * zoom)
        if scaled_size <= 0:
            return

        scaled_texture = pygame.transform.scale(texture, (scaled_size, scaled_size))

        # Calculate centered position
        texture_x = center_x - scaled_size // 2
        texture_y = center_y - scaled_size // 2

        # Draw texture
        RMS.draw(scaled_texture, (texture_x, texture_y))

    def _render_hex_with_color(
        self,
        terrain_type: TerrainType,
        q: int,
        r: int,
        camera_offset: List[float],
        zoom: float,
    ):
        """Render a hex tile with solid color (fallback)."""
        # Get terrain color
        terrain_color = GameConfig.TERRAIN_COLORS.get(terrain_type, (128, 128, 128))

        # Draw hex tile (apply zoom)
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
            for x, y in corners
        ]

        RMS.polygon(terrain_color, screen_corners)
        RMS.polygon((0, 0, 0), screen_corners, 1)

        # Add city marker for city terrain
        if terrain_type == TerrainType.CITY:
            self._render_city_marker(q, r, camera_offset, zoom)

    def _render_fog_of_war(self, camera_offset: List[float], zoom: float = 1.0):
        """Render fog of war - three states: unexplored (black), explored but not visible (semi-transparent black), current vision (green outline)."""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)

        if not game_state or not fog_of_war or not ui_state:
            return

        # God mode: skip fog rendering
        if ui_state.god_mode:
            return

        # Determine the faction currently being viewed
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # Get the viewing faction's vision
        visible_tiles = fog_of_war.faction_vision.get(view_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(view_faction, set())

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Create semi-transparent fog layer for explored-but-not-visible tiles
        explored_fog_surface = pygame.Surface(
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
        )

        # Step 1: Draw unexplored and explored-but-not-visible tiles
        for (q, r), tile_entity in map_data.tiles.items():
            # Compute screen position (apply zoom)
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Check if within screen bounds (accounting for zoom)
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled * 2
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled * 2
                or screen_y < -hex_size_scaled * 2
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled * 2
            ):
                continue

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            if (q, r) in visible_tiles:
                # Currently visible: skip for now, handle boundary later
                continue
            elif (q, r) in explored_tiles:
                # Explored but not currently visible: draw semi-transparent black overlay
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
            else:
                # Unexplored: draw fully black
                # RMS.polygon(GameConfig.FOG_EXPLORED_COLOR, screen_corners)
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
                pass

        # Apply the semi-transparent fog overlay
        RMS.draw(explored_fog_surface, (0, 0))

        # Step 2: Draw green outline around the vision boundary
        self._render_vision_boundary(visible_tiles, camera_offset, zoom)

    def _render_vision_boundary(
        self,
        visible_tiles: Set[Tuple[int, int]],
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Draw a per-unit vision circle centered on each unit."""
        if not visible_tiles:
            return

        # Get all units of the current player
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

            # Compute unit center screen coordinates (apply zoom)
            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = (center_world_x * zoom) + camera_offset[0]
            center_screen_y = (center_world_y * zoom) + camera_offset[1]

            # Check if unit is within screen bounds (accounting for zoom)
            margin = 100 * zoom
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

            # Draw vision circle (max vision range, with zoom)
            circle_radius = int(vision_range * GameConfig.HEX_SIZE * 1.5 * zoom)

            # Draw vision circle outline
            RMS.circle(
                GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                (int(center_screen_x), int(center_screen_y)),
                circle_radius,
                2,
            )

    def _render_territory_boundaries(
        self, camera_offset: List[float], zoom: float = 1.0
    ):
        """Render territory boundaries and faction ownership."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Iterate over all tiles and render territory control info
        for (q, r), tile_entity in map_data.tiles.items():
            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control or not territory_control.controlling_faction:
                continue

            # Compute screen position (apply zoom)
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Check if within screen bounds (accounting for zoom)
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
                or screen_y < -hex_size_scaled
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
            ):
                continue

            # Get faction color
            faction_color = self._get_faction_color(
                territory_control.controlling_faction
            )
            if not faction_color:
                continue

            # Render hex boundary
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            # Adjust border style based on capture progress and fortification level
            border_width = self._get_border_width(territory_control)
            border_color = self._get_border_color(territory_control, faction_color)

            # Draw territory border
            RMS.polygon(border_color, screen_corners, border_width)

            # Add fortification marker if present
            if territory_control.fortification_level > 0:
                self._render_fortification_marker(
                    screen_x, screen_y, territory_control, zoom
                )

    def _get_faction_color(self, faction: Faction) -> Optional[Tuple[int, int, int]]:
        """Get faction color."""
        faction_colors = {
            Faction.WEI: (0, 100, 255),   # blue
            Faction.SHU: (255, 50, 50),   # red
            Faction.WU: (50, 255, 50),    # green
        }
        return faction_colors.get(faction)

    def _get_border_width(self, territory_control: TerritoryControl) -> int:
        """Determine border width based on capture progress and fortification level."""
        base_width = 2

        # Adjust based on capture progress
        if territory_control.capture_progress >= 0.8:
            base_width += 1
        elif territory_control.capture_progress <= 0.3:
            base_width = max(1, base_width - 1)

        # Fortification level increases border width
        base_width += territory_control.fortification_level

        return min(base_width, 5)  # max width cap

    def _get_border_color(
        self, territory_control: TerritoryControl, faction_color: Tuple[int, int, int]
    ) -> Tuple[int, int, int]:
        """Adjust border color based on control state."""
        r, g, b = faction_color

        # Adjust brightness based on capture progress (minimum 50% brightness)
        intensity = max(0.5, territory_control.capture_progress)

        # Scale color brightness
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
        """Render fortification marker."""
        if territory_control.fortification_level <= 0:
            return

        # Marker size scales with fortification level
        marker_size = int(8 * zoom * territory_control.fortification_level)
        marker_color = (139, 69, 19)  # brown, representing fortification

        # Draw fortification marker (small square)
        marker_rect = pygame.Rect(
            center_x - marker_size // 2,
            center_y - marker_size // 2,
            marker_size,
            marker_size,
        )

        RMS.rect(marker_color, marker_rect)
        RMS.rect((0, 0, 0), marker_rect, 1)  # black border

    def _render_city_marker(
        self, q: int, r: int, camera_offset: List[float], zoom: float
    ):
        """Render city marker."""
        # Compute city center screen position
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        center_x = (world_x * zoom) + camera_offset[0]
        center_y = (world_y * zoom) + camera_offset[1]

        # City marker size
        marker_size = int(12 * zoom)
        city_color = (211, 211, 211)  # light gray, representing city building

        # Draw city marker (circle)
        RMS.circle(
            city_color,
            (int(center_x), int(center_y)),
            marker_size,
        )
        RMS.circle(
            (0, 0, 0), (int(center_x), int(center_y)), marker_size, 2  # black border
        )
