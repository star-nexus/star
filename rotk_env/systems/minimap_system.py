"""
Minimap system.
"""

import pygame
from typing import Tuple, Optional
from framework import System, World, RMS, EBS, MouseButtonDownEvent
from ..components import (
    MiniMap,
    MapData,
    Camera,
    Terrain,
    HexPosition,
    Unit,
)
from ..prefabs.config import GameConfig, HexOrientation
from ..utils.hex_utils import HexConverter


class MiniMapSystem(System):
    """Minimap system - handles minimap rendering and interaction."""

    def __init__(self):
        super().__init__(priority=5)  # runs before main render
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

    def initialize(self, world: World) -> None:
        """Initialize system."""
        self.world = world

    def subscribe_events(self):
        """Subscribe to events."""
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def update(self, delta_time: float) -> None:
        """Update minimap."""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible:
            return

        self._render_minimap(minimap)

    def _render_minimap(self, minimap: MiniMap):
        """Render minimap - with corrected coordinate boundary calculation."""
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data:
            return

        # Get minimap screen rectangle
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        # Create minimap surface
        minimap_surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
        minimap_surface.fill((0, 0, 0, minimap.background_alpha))

        # Compute world coordinate bounds (refresh each render)
        self._calculate_world_bounds(map_data)

        # Compute tile coordinate bounds (kept for backward compatibility, no longer used for primary calculations)
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        # Render terrain (if enabled)
        if minimap.show_terrain:
            self._render_terrain(
                minimap_surface, minimap, map_data, min_q, min_r, map_width, map_height
            )

        # Render units (if enabled)
        if minimap.show_units:
            self._render_units(
                minimap_surface, minimap, min_q, min_r, map_width, map_height
            )

        # Render camera viewport (if enabled)
        if minimap.show_camera_viewport and camera:
            self._render_camera_viewport(
                minimap_surface, minimap, camera, min_q, min_r, map_width, map_height
            )

        # Draw border
        pygame.draw.rect(
            minimap_surface,
            minimap.border_color,
            (0, 0, rect_w, rect_h),
            minimap.border_width,
        )

        # Blit to main screen
        RMS.draw(minimap_surface, (rect_x, rect_y))

    def _calculate_world_bounds(self, map_data: MapData):
        """Calculate world coordinate bounds for accurate coordinate mapping."""
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for q, r in map_data.tiles.keys():
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            min_x = min(min_x, world_x)
            max_x = max(max_x, world_x)
            min_y = min(min_y, world_y)
            max_y = max(max_y, world_y)

        # Add padding to ensure all content is visible
        padding = 50
        self._world_bounds = {
            "min_x": min_x - padding,
            "max_x": max_x + padding,
            "min_y": min_y - padding,
            "max_y": max_y + padding,
        }

    def _get_screen_rect(self, minimap: MiniMap) -> Tuple[int, int, int, int]:
        """Get the minimap's screen rectangle."""
        x, y = minimap.position
        # Position minimap in the top-right corner
        rect_x = GameConfig.WINDOW_WIDTH - minimap.width - x
        return (rect_x, y, minimap.width, minimap.height)

    def _render_terrain(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        map_data: MapData,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """Render minimap terrain - with corrected coordinate conversion."""
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # Convert hex coordinates to world pixel coordinates
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

            # Compute world bounds for all tiles if not yet done
            if not hasattr(self, "_world_bounds"):
                self._calculate_world_bounds(map_data)

            # Map world coordinates to minimap coordinates
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # Only draw if within valid range
            if 0 <= pixel_x < minimap.width and 0 <= pixel_y < minimap.height:
                terrain_colors = {
                    "plain": (144, 238, 144),    # light green
                    "forest": (34, 139, 34),     # dark green
                    "mountain": (139, 69, 19),   # brown
                    "water": (70, 130, 180),     # steel blue
                    "city": (255, 215, 0),       # gold
                    "urban": (255, 215, 0),      # gold (same as city)
                    "hill": (205, 133, 63),      # peru
                }

                color = terrain_colors.get(terrain.terrain_type.value, (128, 128, 128))

                # Draw a small square to represent the tile
                tile_size = max(2, int(minimap.scale * 12))
                pygame.draw.rect(
                    surface, color, (pixel_x, pixel_y, tile_size, tile_size)
                )

    def _render_units(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """Render minimap units - with corrected coordinate conversion."""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if not pos or not unit:
                continue

            # HexPosition uses col/row; in the hex grid col=q and row=r
            world_x, world_y = self.hex_converter.hex_to_pixel(pos.col, pos.row)

            # Ensure world bounds have been computed
            if not hasattr(self, "_world_bounds"):
                map_data = self.world.get_singleton_component(MapData)
                if map_data:
                    self._calculate_world_bounds(map_data)
                else:
                    return

            # Map world coordinates to minimap coordinates
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)

            # Only draw if within valid range
            if 0 <= pixel_x < minimap.width and 0 <= pixel_y < minimap.height:
                faction_colors = {
                    "wei": (255, 0, 0),   # red
                    "shu": (0, 255, 0),   # green
                    "wu": (0, 0, 255),    # blue
                }

                color = faction_colors.get(unit.faction.value, (255, 255, 255))

                # Draw unit dot
                unit_size = max(3, int(minimap.scale * 15))
                pygame.draw.circle(surface, color, (pixel_x, pixel_y), unit_size)

    def _render_camera_viewport(
        self,
        surface: pygame.Surface,
        minimap: MiniMap,
        camera: Camera,
        min_q: int,
        min_r: int,
        map_width: int,
        map_height: int,
    ):
        """Render camera viewport on minimap - with corrected coordinate conversion."""
        # Compute the region currently visible by the camera in world coordinates
        camera_offset = camera.get_offset()

        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # Four corners of the camera viewport (world coordinates)
        viewport_corners = [
            (-camera_offset[0], -camera_offset[1]),                              # top-left
            (-camera_offset[0] + screen_width, -camera_offset[1]),               # top-right
            (-camera_offset[0], -camera_offset[1] + screen_height),              # bottom-left
            (-camera_offset[0] + screen_width, -camera_offset[1] + screen_height),  # bottom-right
        ]

        # Ensure world bounds have been computed
        if not hasattr(self, "_world_bounds"):
            map_data = self.world.get_singleton_component(MapData)
            if map_data:
                self._calculate_world_bounds(map_data)
            else:
                return

        # Map viewport corners to minimap coordinates
        minimap_corners = []
        for world_x, world_y in viewport_corners:
            rel_x = (world_x - self._world_bounds["min_x"]) / (
                self._world_bounds["max_x"] - self._world_bounds["min_x"]
            )
            rel_y = (world_y - self._world_bounds["min_y"]) / (
                self._world_bounds["max_y"] - self._world_bounds["min_y"]
            )

            pixel_x = int(rel_x * minimap.width)
            pixel_y = int(rel_y * minimap.height)
            minimap_corners.append((pixel_x, pixel_y))

        # Compute viewport bounding box
        min_x = min(corner[0] for corner in minimap_corners)
        max_x = max(corner[0] for corner in minimap_corners)
        min_y = min(corner[1] for corner in minimap_corners)
        max_y = max(corner[1] for corner in minimap_corners)

        viewport_x = max(0, min_x)
        viewport_y = max(0, min_y)
        viewport_w = min(minimap.width - viewport_x, max_x - min_x)
        viewport_h = min(minimap.height - viewport_y, max_y - min_y)

        # Draw viewport rectangle
        if viewport_w > 0 and viewport_h > 0:
            pygame.draw.rect(
                surface,
                (255, 255, 255),
                (viewport_x, viewport_y, viewport_w, viewport_h),
                2,
            )

    def handle_click(self, mouse_pos: Tuple[int, int]) -> bool:
        """Handle minimap click; returns True if the click was on the minimap."""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible or not minimap.clickable:
            return False

        # Check if click landed on the minimap area
        if not self._is_point_inside(minimap, mouse_pos):
            return False

        # Convert to relative minimap coordinates
        rel_pos = self._screen_to_minimap(minimap, mouse_pos)
        if not rel_pos:
            return False

        # Convert relative coordinates to world coordinates
        world_pos = self._minimap_to_world_pos(rel_pos)
        if world_pos:
            # Move camera to target position
            self._move_camera_to_position(world_pos)

        return True

    def _is_point_inside(self, minimap: MiniMap, screen_pos: Tuple[int, int]) -> bool:
        """Check whether a screen coordinate is within the minimap area."""
        x, y = screen_pos
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)
        return rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + rect_h

    def _screen_to_minimap(
        self, minimap: MiniMap, screen_pos: Tuple[int, int]
    ) -> Optional[Tuple[float, float]]:
        """Convert screen coordinates to minimap-relative coordinates (0–1 range)."""
        if not self._is_point_inside(minimap, screen_pos):
            return None

        x, y = screen_pos
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        rel_x = (x - rect_x) / rect_w
        rel_y = (y - rect_y) / rect_h

        return (rel_x, rel_y)

    def _minimap_to_world_pos(
        self, rel_pos: Tuple[float, float]
    ) -> Optional[Tuple[int, int]]:
        """Convert minimap-relative coordinates to world hex coordinates."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        # Compute tile coordinate bounds
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        # Convert to hex coordinates
        rel_x, rel_y = rel_pos
        target_q = min_q + rel_x * (max_q - min_q)
        target_r = min_r + rel_y * (max_r - min_r)

        return (int(target_q), int(target_r))

    def _move_camera_to_position(self, hex_pos: Tuple[int, int]):
        """Move camera to the specified hex coordinate."""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        q, r = hex_pos

        # Convert hex coordinates to world pixel coordinates
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)

        # Set camera offset to center the target position on screen
        camera_x = GameConfig.WINDOW_WIDTH // 2 - world_x
        camera_y = GameConfig.WINDOW_HEIGHT // 2 - world_y

        camera.set_offset(camera_x, camera_y)

    def _handle_mouse_click(self, event: MouseButtonDownEvent):
        """Handle minimap mouse click event."""
        minimap = self.world.get_singleton_component(MiniMap)
        if not minimap or not minimap.visible:
            return

        # Only handle left-button clicks
        if event.button != 1:
            return

        # Check if click is within the minimap area
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        mouse_x, mouse_y = event.pos
        if not (
            rect_x <= mouse_x <= rect_x + rect_w
            and rect_y <= mouse_y <= rect_y + rect_h
        ):
            return

        # Convert screen coordinates to minimap-relative coordinates
        relative_x = mouse_x - rect_x
        relative_y = mouse_y - rect_y

        # Convert relative coordinates to hex map coordinates
        hex_pos = self._screen_to_hex(relative_x, relative_y, minimap)
        if hex_pos:
            # Move camera to clicked position
            self._move_camera_to_position(hex_pos)

        # Only handle left-button clicks
        if event.button != 1:
            return

        # Check if click is within the minimap area
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        mouse_x, mouse_y = event.pos
        if not (
            rect_x <= mouse_x <= rect_x + rect_w
            and rect_y <= mouse_y <= rect_y + rect_h
        ):
            return

        # Convert screen coordinates to minimap-relative coordinates
        relative_x = mouse_x - rect_x
        relative_y = mouse_y - rect_y

        # Convert relative coordinates to hex map coordinates
        hex_pos = self._screen_to_hex(relative_x, relative_y, minimap)
        if hex_pos:
            # Move camera to clicked position
            self._move_camera_to_position(hex_pos)

    def _screen_to_hex(
        self, screen_x: int, screen_y: int, minimap: MiniMap
    ) -> Optional[Tuple[int, int]]:
        """Convert minimap screen coordinates to hex map coordinates."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        # Compute tile coordinate bounds
        min_q = min(coord[0] for coord in map_data.tiles.keys())
        max_q = max(coord[0] for coord in map_data.tiles.keys())
        min_r = min(coord[1] for coord in map_data.tiles.keys())
        max_r = max(coord[1] for coord in map_data.tiles.keys())

        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        # Get minimap screen rectangle
        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)

        # Compute normalized position on map (0 to 1)
        norm_x = screen_x / rect_w
        norm_y = screen_y / rect_h

        # Convert to hex coordinates
        hex_q = int(min_q + norm_x * map_width)
        hex_r = int(min_r + norm_y * map_height)

        # Ensure coordinates are within valid range
        if (hex_q, hex_r) in map_data.tiles:
            return (hex_q, hex_r)

        return None
