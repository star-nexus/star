"""
Unit Render System (v0) - Handles rendering of units, health bars, icons, and status indicators
"""

import pygame
import os
from typing import List, Dict, Optional
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


class UnitRenderSystem(System):
    """Unit render system"""

    def __init__(self):
        super().__init__(priority=2)  # Render units above the map layer
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.font = None
        self.small_font = None
        
        # Unit texture cache
        self.unit_textures: Dict[str, pygame.Surface] = {}
        self.textures_loaded = False

        # Initialize fonts
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """Initialize unit render system"""
        self.world = world
        self._load_unit_textures()

    def _load_unit_textures(self) -> None:
        """Load unit textures"""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "units"
        )

        if not os.path.exists(assets_path):
            print(f"Warning: unit texture directory not found: {assets_path}")
            return

        # Iterate over all faction and unit type combinations
        for faction in Faction:
            faction_dir = os.path.join(assets_path, faction.value)
            if not os.path.exists(faction_dir):
                continue
                
            for unit_type in UnitType:
                texture_file = f"{unit_type.value}.png"
                texture_path = os.path.join(faction_dir, texture_file)
                
                if os.path.exists(texture_path):
                    try:
                        texture = pygame.image.load(texture_path).convert_alpha()
                        # Scale texture to appropriate size (based on HEX_SIZE)
                        size = GameConfig.HEX_SIZE
                        texture = pygame.transform.scale(texture, (size, size))
                        
                        # Store using "faction_unit_type" as key
                        key = f"{faction.value}_{unit_type.value}"
                        self.unit_textures[key] = texture
                        print(f"Loaded unit texture: {key}")
                    except pygame.error as e:
                        print(f"Warning: failed to load texture {texture_path}: {e}")

        # Check loading results
        if len(self.unit_textures) > 0:
            self.textures_loaded = True
            print(f"Unit textures loaded: {len(self.unit_textures)} textures")
        else:
            print("Warning: no unit textures loaded; falling back to circle rendering")

    def _get_unit_texture(self, faction: Faction, unit_type: UnitType) -> Optional[pygame.Surface]:
        """Get texture for specified faction and unit type"""
        key = f"{faction.value}_{unit_type.value}"
        return self.unit_textures.get(key)

    def subscribe_events(self):
        """Subscribe to events (unit render system does not need to subscribe to events)"""
        pass

    def update(self, delta_time: float) -> None:
        """Update unit rendering"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # Calculate camera offset
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # Render units
        self._render_units(camera_offset, zoom)
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.render_damage_numbers()

    def _render_units(self, camera_offset: List[float], zoom: float = 1.0):
        """Render units"""
        # Get animation system to obtain correct render positions
        animation_system = self._get_animation_system()

        # Collect all visible units and group by position
        units_by_position = {}

        for entity in (
            self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        ):
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            if not position or not unit or not unit_count:
                continue

            # Check unit visibility
            if not self._is_unit_visible(entity):
                continue

            # Get base position (ignoring animation, since we group by logical position)
            pos_key = (position.col, position.row)
            if pos_key not in units_by_position:
                units_by_position[pos_key] = []
            units_by_position[pos_key].append(entity)

        # Render unit groups at each position
        for pos_key, units in units_by_position.items():
            self._render_unit_group(
                pos_key, units, camera_offset, zoom, animation_system
            )

    def _render_unit_group(self, pos_key, units, camera_offset, zoom, animation_system):
        """Render group of units at the same position"""
        # Group by faction
        units_by_faction = {}
        for entity in units:
            unit = self.world.get_component(entity, Unit)
            if unit:
                if unit.faction not in units_by_faction:
                    units_by_faction[unit.faction] = []
                units_by_faction[unit.faction].append(entity)

        # Get base position
        base_world_x, base_world_y = self.hex_converter.hex_to_pixel(
            pos_key[0], pos_key[1]
        )
        base_screen_x = (base_world_x * zoom) + camera_offset[0]
        base_screen_y = (base_world_y * zoom) + camera_offset[1]

        # Check if within screen bounds
        hex_size_scaled = GameConfig.HEX_SIZE * zoom
        if (
            base_screen_x < -hex_size_scaled
            or base_screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
            or base_screen_y < -hex_size_scaled
            or base_screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
        ):
            return

        factions = list(units_by_faction.keys())
        total_factions = len(factions)

        if total_factions == 1:
            # Same faction: evenly distribute within the hex
            faction = factions[0]
            faction_units = units_by_faction[faction]
            self._render_same_faction_units(
                faction_units, base_screen_x, base_screen_y, zoom, animation_system
            )
        else:
            # Multiple factions: split into halves, each half evenly distributed
            self._render_multi_faction_units(
                units_by_faction, base_screen_x, base_screen_y, zoom, animation_system
            )

    def _render_same_faction_units(self, units, base_x, base_y, zoom, animation_system):
        """Render multiple units of the same faction"""
        unit_count = len(units)
        if unit_count == 1:
            # Single unit: render normally at center
            self._render_single_unit(units[0], base_x, base_y, zoom, animation_system)
        else:
            # Multiple units: evenly distribute within the hex
            positions = self._calculate_unit_positions_in_hex(
                unit_count, base_x, base_y, zoom
            )
            for i, entity in enumerate(units):
                x, y = positions[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)

    def _render_multi_faction_units(
        self, units_by_faction, base_x, base_y, zoom, animation_system
    ):
        """Render units of multiple factions"""
        factions = list(units_by_faction.keys())

        # Calculate area for each faction
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8  # Slightly reduced to avoid overflow

        if len(factions) == 2:
            # Two factions: left/right distribution
            faction1, faction2 = factions

            # Left area center
            left_x = base_x - hex_radius * 0.3
            left_y = base_y

            # Right area center
            right_x = base_x + hex_radius * 0.3
            right_y = base_y

            # Render first faction (left)
            units1 = units_by_faction[faction1]
            positions1 = self._calculate_unit_positions_in_area(
                len(units1), left_x, left_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units1):
                x, y = positions1[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)

            # Render second faction (right)
            units2 = units_by_faction[faction2]
            positions2 = self._calculate_unit_positions_in_area(
                len(units2), right_x, right_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units2):
                x, y = positions2[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)
        else:
            # Three or more factions: circular distribution
            import math

            for i, faction in enumerate(factions):
                angle = (2 * math.pi * i) / len(factions)
                area_x = base_x + hex_radius * 0.4 * math.cos(angle)
                area_y = base_y + hex_radius * 0.4 * math.sin(angle)

                units = units_by_faction[faction]
                positions = self._calculate_unit_positions_in_area(
                    len(units), area_x, area_y, hex_radius * 0.4, zoom
                )
                for j, entity in enumerate(units):
                    x, y = positions[j]
                    self._render_single_unit(entity, x, y, zoom, animation_system)

    def _calculate_unit_positions_in_hex(self, unit_count, center_x, center_y, zoom):
        """Calculate evenly distributed unit positions inside a hex, ensuring no overlap"""
        import math

        positions = []
        # Base unit radius
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8
        # Usable hex radius (with margin)
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8

        if unit_count == 1:
            # Single unit: at center
            positions.append((center_x, center_y))
        elif unit_count == 2:
            # Two units: vertical arrangement, ensuring no overlap
            offset = max(unit_radius * 1.2, hex_radius * 0.3)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            # Three units: triangular arrangement
            offset = max(unit_radius * 1.2, hex_radius * 0.4)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        elif unit_count == 4:
            # Four units: square arrangement
            offset = max(unit_radius * 1.1, hex_radius * 0.35)
            positions.append((center_x - offset, center_y - offset))
            positions.append((center_x + offset, center_y - offset))
            positions.append((center_x - offset, center_y + offset))
            positions.append((center_x + offset, center_y + offset))
        elif unit_count == 5:
            # Five units: center + four surrounding
            center_pos = (center_x, center_y)
            positions.append(center_pos)

            offset = max(unit_radius * 1.3, hex_radius * 0.4)
            for i in range(4):
                angle = (math.pi / 2) * i  # 90-degree interval
                x = center_x + offset * math.cos(angle)
                y = center_y + offset * math.sin(angle)
                positions.append((x, y))
        elif unit_count == 6:
            # Six units: hexagonal arrangement
            radius = max(unit_radius * 1.2, hex_radius * 0.45)
            for i in range(6):
                angle = (2 * math.pi * i) / 6
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions.append((x, y))
        else:
            # More units: dual-ring arrangement
            if unit_count <= 12:
                # Single ring
                radius = max(unit_radius * 1.1, hex_radius * 0.5)
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # Dual ring: 6 in inner ring, rest in outer ring
                # Inner ring
                inner_radius = max(unit_radius * 1.0, hex_radius * 0.3)
                for i in range(6):
                    angle = (2 * math.pi * i) / 6
                    x = center_x + inner_radius * math.cos(angle)
                    y = center_y + inner_radius * math.sin(angle)
                    positions.append((x, y))

                # Outer ring
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
        """Calculate evenly distributed unit positions within a specified area, ensuring no overlap"""
        import math

        positions = []
        # Base unit radius
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8

        if unit_count == 1:
            positions.append((center_x, center_y))
        elif unit_count == 2:
            # Two units: vertical arrangement
            offset = max(unit_radius * 1.2, area_radius * 0.6)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            # Three units: triangular arrangement
            offset = max(unit_radius * 1.1, area_radius * 0.7)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        else:
            # Multiple units: circular arrangement, radius adjusted by area size
            radius = max(unit_radius * 1.0, area_radius * 0.8)
            # Ensure units do not overlap
            min_distance = unit_radius * 2.2
            circle_circumference = 2 * math.pi * radius
            max_units_on_circle = int(circle_circumference / min_distance)

            if unit_count <= max_units_on_circle:
                # Single ring
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # Multi-ring or compact arrangement
                # Simplified to compact grid arrangement
                cols = int(math.ceil(math.sqrt(unit_count)))
                rows = int(math.ceil(unit_count / cols))

                # Calculate grid spacing
                grid_spacing = max(unit_radius * 2.2, area_radius * 2 / max(cols, rows))

                # Calculate start position (centered)
                start_x = center_x - (cols - 1) * grid_spacing / 2
                start_y = center_y - (rows - 1) * grid_spacing / 2

                for i in range(unit_count):
                    row = i // cols
                    col = i % cols
                    x = start_x + col * grid_spacing
                    y = start_y + row * grid_spacing
                    positions.append((x, y))

        return positions

    def _render_single_unit(self, entity, screen_x, screen_y, zoom, animation_system):
        """Render a single unit"""
        position = self.world.get_component(entity, HexPosition)
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)

        if not position or not unit or not unit_count:
            return

        # Use animation position only when the unit is in a movement animation,
        # otherwise use the grouped layout position
        use_animation_pos = False
        if animation_system:
            render_pos = animation_system.get_unit_render_position(entity)
            if render_pos:
                # Check if the unit is moving (has animation position and is not at target position)
                world_x, world_y = render_pos
                target_world_x, target_world_y = self.hex_converter.hex_to_pixel(
                    position.col, position.row
                )

                # If animation position differs significantly from target position,
                # the unit is moving; use animation position
                distance = (
                    (world_x - target_world_x) ** 2 + (world_y - target_world_y) ** 2
                ) ** 0.5
                if distance > 5:  # Distance threshold, adjustable
                    screen_x = (world_x * zoom) + self.world.get_singleton_component(
                        Camera
                    ).offset_x
                    screen_y = (world_y * zoom) + self.world.get_singleton_component(
                        Camera
                    ).offset_y
                    use_animation_pos = True

        # Dynamically adjust unit size based on animation state and unit density
        base_radius = GameConfig.HEX_SIZE // 3
        if use_animation_pos:
            # Maintain normal size during movement animation
            scale_factor = 1.0
        else:
            # Adjust size based on number of units in the same hex when static
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

        # Try texture rendering; fall back to circle if no texture available
        texture = self._get_unit_texture(unit.faction, unit.unit_type)
        
        if texture and self.textures_loaded:
            # Use texture rendering
            self._render_unit_texture(texture, screen_x, screen_y, zoom, scale_factor)
        else:
            # Fall back to circle rendering
            print("Falling back to circle rendering")
            unit_radius = int(base_radius * zoom * scale_factor)
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

        # Draw troop count bar (using same scale)
        unit_radius = int(base_radius * zoom * scale_factor)
        self._render_unit_count_bar(
            screen_x, screen_y, unit_count, unit_radius, zoom, scale=scale_factor
        )

        # Draw unit type icon (using same scale)
        self._render_unit_icon(screen_x, screen_y, unit, zoom, scale=scale_factor)

        # Draw unit status indicator
        status = self.world.get_component(entity, UnitStatus)
        if status:
            self._render_unit_status(screen_x, screen_y, status, unit_radius, zoom)

    def _render_unit_count_bar(
        self, screen_x, screen_y, unit_count, unit_radius, zoom, scale=1.0
    ):
        """Render unit troop count bar"""
        if unit_count.current_count <= 1:
            return

        # Calculate bar size (applying scale)
        bar_width = int(unit_radius * 2 * zoom * scale)
        bar_height = int(5 * zoom * scale)
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - unit_radius - int(10 * zoom * scale)

        # Calculate full-strength ratio
        fill_ratio = unit_count.current_count / unit_count.max_count
        fill_width = int(bar_width * fill_ratio)

        # Draw background bar
        RMS.rect(
            (100, 100, 100),
            (bar_x, bar_y, bar_width, bar_height),
        )

        # Draw fill bar
        if fill_ratio > 0.7:
            fill_color = (0, 255, 0)  # green
        elif fill_ratio > 0.3:
            fill_color = (255, 255, 0)  # yellow
        else:
            fill_color = (255, 0, 0)  # red

        if fill_width > 0:
            RMS.rect(
                fill_color,
                (bar_x, bar_y, fill_width, bar_height),
            )

        # Draw border
        RMS.rect(
            (255, 255, 255),
            (bar_x, bar_y, bar_width, bar_height),
            1,
        )

    def _render_unit_icon(self, screen_x, screen_y, unit, zoom, scale=1.0):
        """Render unit type icon"""
        # Select symbol based on unit type
        unit_symbols = {
            UnitType.INFANTRY: "Inf",
            UnitType.CAVALRY: "Cav",
            UnitType.ARCHER: "Arc",
            # UnitType.SIEGE: "Sge",
        }

        symbol = unit_symbols.get(unit.unit_type, "?")

        # Calculate font size (applying scale)
        font_size = int(14 * zoom * scale)

        if font_size < 8:  # Avoid font size too small
            return

        try:
            font = pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), font_size)
            text_surface = font.render(symbol, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(int(screen_x), int(screen_y)))
            RMS.draw(text_surface, text_rect)
        except:
            # Skip if font rendering fails
            pass

    def _render_unit_texture(self, texture: pygame.Surface, screen_x: float, screen_y: float, zoom: float, scale_factor: float):
        """Render unit texture"""
        # Calculate texture size
        texture_size = int(GameConfig.HEX_SIZE * zoom * scale_factor)
        
        # Scale texture if needed
        if texture_size != texture.get_width():
            scaled_texture = pygame.transform.scale(texture, (texture_size, texture_size))
        else:
            scaled_texture = texture
        
        # Calculate texture position (center-aligned)
        texture_x = screen_x - texture_size // 2
        texture_y = screen_y - texture_size // 2
        
        # Render texture
        RMS.draw(scaled_texture, (int(texture_x), int(texture_y)))

    def _render_unit_status(
        self,
        screen_x: float,
        screen_y: float,
        status: UnitStatus,
        unit_radius: int,
        zoom: float = 1.0,
    ):
        """Render unit status indicator"""
        if not status:  # or status.current_status == "idle":  # "normal":
            return

        # Status color mapping
        # status_colors = {
        #     "moved": (100, 100, 255),      # blue - moved
        #     "attacked": (255, 100, 100),   # red - attacked
        #     "exhausted": (150, 150, 150),  # gray - exhausted
        #     "defending": (100, 255, 100),  # green - defending
        # }
        # Status color mapping
        status_colors = {
            "idle": (128, 128, 128),  # gray - idle
            "moving": (0, 255, 255),  # cyan - moving
            "combat": (255, 0, 0),  # red - combat
            "hidden": (128, 0, 128),  # purple - hidden
            "resting": (0, 255, 0),  # green - resting
        }

        status_text_map = {
            "moved": "Mov",
            "attacked": "Atk",
            "exhausted": "Exh",
            "defending": "Def",
        }

        if status.current_status in status_colors:
            # Draw status indicator circle
            # status_radius = int(8 * zoom)
            # status_x = x + radius + int(10 * zoom)
            # status_y = y - radius - int(10 * zoom)

            # RMS.circle(color, (int(status_x), int(status_y)), status_radius)
            # RMS.circle((0, 0, 0), (int(status_x), int(status_y)), status_radius, 1)

            # Draw status indicator at the top-right of the unit
            indicator_size = int(4 * zoom)
            indicator_x = screen_x + unit_radius * 0.7
            indicator_y = screen_y - unit_radius * 0.7

            color = status_colors[status.current_status]
            RMS.circle(color, (int(indicator_x), int(indicator_y)), indicator_size)
            RMS.circle(
                (0, 0, 0), (int(indicator_x), int(indicator_y)), indicator_size, 1
            )

            # Draw status text
            status_text = status_text_map.get(status.current_status, "")
            if status_text:
                font_size = max(10, int(12 * zoom))
                font = pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), font_size)

                text_surface = font.render(status_text, True, (255, 255, 255))
                # text_rect = text_surface.get_rect(center=(int(status_x), int(status_y)))
                text_rect = text_surface.get_rect(
                    center=(int(indicator_x), int(indicator_y))
                )
                RMS.draw(text_surface, text_rect)

    def _is_unit_visible(self, unit_entity: int) -> bool:
        """Check if unit is visible"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not fog_of_war or not position or not unit or not ui_state:
            return True

        # God mode: all units are visible
        if ui_state.god_mode:
            return True

        # Determine current viewing faction
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # Own faction units are always visible
        if unit.faction == view_faction:
            return True

        # Check if within the viewing faction's vision range
        current_vision = fog_of_war.faction_vision.get(view_faction, set())
        return (position.col, position.row) in current_vision

    def _get_units_in_same_hex(self, target_entity):
        """Get all units in the same hex tile as the target unit"""
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
        """Get the animation system"""
        # Get the animation system from the world
        # Returns None if AnimationSystem is not present
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None
