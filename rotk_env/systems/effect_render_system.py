"""
Effect Render System - Handles rendering of selection highlights, movement range,
attack range, tile hover effects, and visual effect animations
"""

import pygame
from typing import List, Set, Tuple
from framework import System, RMS
from ..components import (
    UIState,
    InputState,
    HexPosition,
    Unit,
    MovementPoints,
    Combat,
    Camera,
    FogOfWar,
    GameState,
    EffectAnimation,
    AttackAnimation,
    ProjectileAnimation,
)
from ..prefabs.config import GameConfig, HexOrientation
from ..utils.hex_utils import HexConverter, HexMath, PathFinding


class EffectRenderSystem(System):
    """Effect rendering system"""

    def __init__(self):
        super().__init__(priority=3)  # Render effects above the unit layer
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )

    def initialize(self, world) -> None:
        """Initialize the effect render system"""
        self.world = world

    def subscribe_events(self):
        """Subscribe to events (effect render system requires none)"""
        pass

    def update(self, delta_time: float) -> None:
        """Update effect rendering for the current frame"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # Compute camera offset and zoom
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # Render all effect layers
        self._render_selection_effects(camera_offset, zoom)
        self._render_attack_effects(camera_offset, zoom)
        self._render_attack_indicators(camera_offset, zoom)
        self._render_projectiles(camera_offset, zoom)
        self._render_tile_hover(camera_offset, zoom)

    def _render_selection_effects(self, camera_offset: List[float], zoom: float = 1.0):
        """Render unit selection highlights and range overlays"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return

        # Render selected unit highlight
        if ui_state.selected_unit:
            self._render_unit_selection(ui_state.selected_unit, camera_offset, zoom)

            # Fetch selected unit components
            movement = self.world.get_component(ui_state.selected_unit, MovementPoints)
            combat = self.world.get_component(ui_state.selected_unit, Combat)

            # Show movement range if the unit hasn't moved yet
            if movement and not movement.has_moved:
                self._render_movement_range(ui_state.selected_unit, camera_offset, zoom)

            # Show attack range if the unit hasn't attacked yet
            if combat and not combat.has_attacked:
                self._render_attack_range(ui_state.selected_unit, camera_offset, zoom)

    def _render_unit_selection(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """Render selection ring and pulse effect for the selected unit"""
        position = self.world.get_component(unit_entity, HexPosition)
        if not position:
            return

        # Convert to screen coordinates
        world_x, world_y = self.hex_converter.hex_to_pixel(position.col, position.row)
        screen_x = world_x * zoom + camera_offset[0]
        screen_y = world_y * zoom + camera_offset[1]

        # Draw selection ring
        radius = int(GameConfig.HEX_SIZE * 0.8 * zoom)
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 0), (int(screen_x), int(screen_y)), radius, 3
        # )
        RMS.circle((255, 255, 0), (int(screen_x), int(screen_y)), radius, 3)

        # Draw pulsing fill circle
        import time

        pulse = abs(0.5 - (time.time() % 1.0)) * 0.4 + 0.6
        inner_radius = int(radius * pulse)
        # pygame circles don't support alpha; use a temporary SRCALPHA surface instead
        s = pygame.Surface((inner_radius * 2, inner_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            s, (255, 255, 0, 50), (inner_radius, inner_radius), inner_radius
        )
        RMS.screen.blit(s, (int(screen_x - inner_radius), int(screen_y - inner_radius)))

    def _render_movement_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """Render reachable movement tiles as blue overlays"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not movement or not unit:
            return

        # Gather obstacle positions
        obstacles = self._get_obstacles()
        # Compute reachable tiles
        movement_range = PathFinding().get_movement_range(
            (position.col, position.row), movement.current_mp, obstacles
        )

        # # Get all tiles within movement range
        # reachable_tiles = set()
        # for distance in range(1, movement.current_movement + 1):
        #     ring_tiles = HexMath.hex_ring(position.col, position.row, distance)
        #     for tile_col, tile_row in ring_tiles:
        #         # Check if path is reachable
        #         path = pathfinding.find_path(
        #             (position.col, position.row),
        #             (tile_col, tile_row),
        #             obstacles,
        #             movement.current_movement,
        #         )
        #         if path and len(path) - 1 <= movement.current_movement:
        #             reachable_tiles.add((tile_col, tile_row))

        # # Render reachable area
        # for tile_col, tile_row in reachable_tiles:
        #     # Check if within map bounds
        #     if not (
        #         -GameConfig.MAP_WIDTH // 2 <= tile_col < GameConfig.MAP_WIDTH // 2
        #         and -GameConfig.MAP_HEIGHT // 2 <= tile_row < GameConfig.MAP_HEIGHT // 2
        #     ):
        #         continue

        #     # Convert to screen coordinates
        #     world_x, world_y = self.hex_converter.hex_to_pixel(tile_col, tile_row)
        #     screen_x = world_x * zoom + camera_offset[0]
        #     screen_y = world_y * zoom + camera_offset[1]

        #     # Check if within screen bounds
        #     if not (
        #         0 <= screen_x < GameConfig.WINDOW_WIDTH
        #         and 0 <= screen_y < GameConfig.WINDOW_HEIGHT
        #     ):
        #         continue

        #     # pygame.draw.circle(
        #     #     RMS.screen, (0, 255, 0, 100), (int(screen_x), int(screen_y)), radius
        #     # )
        #     # pygame.draw.circle(
        #     #     RMS.screen, (0, 255, 0), (int(screen_x), int(screen_y)), radius, 2
        #     # )
        # Draw movement range tiles
        for q, r in movement_range:
            if (q, r) == (position.col, position.row):
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # Draw semi-transparent blue overlay (zoom-aware)
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
                for x, y in corners
            ]

            hex_size_scaled = int(GameConfig.HEX_SIZE * zoom)
            overlay = pygame.Surface((hex_size_scaled * 2, hex_size_scaled * 2))
            overlay.set_alpha(100)
            overlay.fill((0, 0, 255))

            # Create a hexagon-shaped mask
            mask_surface = pygame.Surface(
                (hex_size_scaled * 2, hex_size_scaled * 2), pygame.SRCALPHA
            )
            mask_corners = [
                (
                    (x * zoom) - (world_x * zoom) + hex_size_scaled,
                    (y * zoom) - (world_y * zoom) + hex_size_scaled,
                )
                for x, y in corners
            ]
            pygame.draw.polygon(mask_surface, (0, 0, 255, 100), mask_corners)

            RMS.draw(
                mask_surface,
                (screen_x - hex_size_scaled, screen_y - hex_size_scaled),
            )

    def _render_attack_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """Render attack range highlighting"""
        position = self.world.get_component(unit_entity, HexPosition)
        combat = self.world.get_component(unit_entity, Combat)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not combat or not unit:
            return

        # Get tiles within attack range
        attack_tiles = HexMath.hex_in_range(
            position.col, position.row, combat.attack_range
        )

        # Render attack range overlays
        for tile_col, tile_row in attack_tiles:
            # Skip the unit's own tile
            if tile_col == position.col and tile_row == position.row:
                continue

            # Skip tiles outside map bounds
            if not (
                -GameConfig.MAP_WIDTH // 2 <= tile_col < GameConfig.MAP_WIDTH // 2
                and -GameConfig.MAP_HEIGHT // 2 <= tile_row < GameConfig.MAP_HEIGHT // 2
            ):
                continue

            # Convert to screen coordinates
            world_x, world_y = self.hex_converter.hex_to_pixel(tile_col, tile_row)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]

            # Skip tiles off-screen
            if not (
                0 <= screen_x < GameConfig.WINDOW_WIDTH
                and 0 <= screen_y < GameConfig.WINDOW_HEIGHT
            ):
                continue

            # Check for enemy unit at this tile
            enemy_unit = self._get_enemy_unit_at_position(
                (tile_col, tile_row), unit.faction
            )
            if enemy_unit:
                # Highlight in red if an enemy is present
                radius = int(GameConfig.HEX_SIZE * 0.7 * zoom)
                # pygame.draw.circle(
                #     RMS.screen, (255, 0, 0, 150), (int(screen_x), int(screen_y)), radius
                # )
                # pygame.draw.circle(
                #     RMS.screen, (255, 0, 0), (int(screen_x), int(screen_y)), radius, 3
                # )
                RMS.circle(
                    (255, 0, 0, 150),
                    (int(screen_x), int(screen_y)),
                    radius,
                )
                # RMS.circle(
                #     (255, 0, 0),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                #     1,
                # )
            else:
                # Show orange range indicator if tile is empty
                radius = int(GameConfig.HEX_SIZE * 0.5 * zoom)
                # pygame.draw.circle(
                #     RMS.screen,
                #     (255, 165, 0, 80),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                # )
                # pygame.draw.circle(
                #     RMS.screen, (255, 165, 0), (int(screen_x), int(screen_y)), radius, 2
                # )
                RMS.circle(
                    (255, 165, 0, 80),
                    (int(screen_x), int(screen_y)),
                    radius,
                )
                # RMS.circle(
                #     (255, 165, 0),
                #     (int(screen_x), int(screen_y)),
                #     radius,
                #     1,
                # )

    def _render_tile_hover(self, camera_offset: List[float], zoom: float = 1.0):
        """Render tile hover highlight effect"""
        # input_state = self.world.get_singleton_component(InputState)
        # if not input_state:
        #     return

        # Get the tile position under the mouse cursor
        # mouse_x, mouse_y = pygame.mouse.get_pos()

        # # Convert to world coordinates
        # world_x = (mouse_x - camera_offset[0]) / zoom
        # world_y = (mouse_y - camera_offset[1]) / zoom

        # # Convert to hex coordinates
        # hex_col, hex_row = self.hex_converter.pixel_to_hex(world_x, world_y)

        # # Check if within map bounds
        # if not (
        #     -GameConfig.MAP_WIDTH // 2 <= hex_col < GameConfig.MAP_WIDTH // 2
        #     and -GameConfig.MAP_HEIGHT // 2 <= hex_row < GameConfig.MAP_HEIGHT // 2
        # ):
        #     return

        # # Convert back to screen coordinates for rendering
        # world_x, world_y = self.hex_converter.hex_to_pixel(hex_col, hex_row)
        # screen_x = world_x * zoom + camera_offset[0]
        # screen_y = world_y * zoom + camera_offset[1]

        # Draw hover effect
        # radius = int(GameConfig.HEX_SIZE * 0.9 * zoom)
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 255, 100), (int(screen_x), int(screen_y)), radius
        # )
        # pygame.draw.circle(
        #     RMS.screen, (255, 255, 255), (int(screen_x), int(screen_y)), radius, 1
        # )
        # RMS.circle(
        #     (255, 255, 255, 100),
        #     (int(screen_x), int(screen_y)),
        #     radius,
        # )
        # RMS.circle(
        #     (255, 255, 255),
        #     (int(screen_x), int(screen_y)),
        #     radius,
        #     1,
        # )
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state.hovered_tile:
            return
        (q, r) = ui_state.hovered_tile
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        screen_x = (world_x * zoom) + camera_offset[0]
        screen_y = (world_y * zoom) + camera_offset[1]

        # Draw hover outline (zoom-aware)
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            ((x * zoom) + camera_offset[0], (y * zoom) + camera_offset[1])
            for x, y in corners
        ]
        # pygame.draw.polygon(self.screen, (255, 255, 255), screen_corners, 2)
        RMS.polygon((255, 255, 255), screen_corners, 2)

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """Collect obstacle positions (all unit locations)"""
        obstacles = set()

        # Mark all unit positions as obstacles
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            if position:
                obstacles.add((position.col, position.row))

        return obstacles

    def _get_enemy_unit_at_position(self, position: Tuple[int, int], friendly_faction):
        """Get the enemy unit entity at the specified tile position, if any"""
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if (
                pos
                and unit
                and (pos.col, pos.row) == position
                and unit.faction != friendly_faction
            ):
                return entity

        return None

    def _render_attack_effects(self, camera_offset: List[float], zoom: float = 1.0):
        """Render active attack visual effects"""
        for entity in self.world.query().with_all(EffectAnimation).entities():
            effect = self.world.get_component(entity, EffectAnimation)
            if not effect or not effect.is_playing:
                continue

            # Convert to screen coordinates
            world_x, world_y = effect.effect_position
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]

            # Skip off-screen effects
            if not (
                -100 <= screen_x <= GameConfig.WINDOW_WIDTH + 100
                and -100 <= screen_y <= GameConfig.WINDOW_HEIGHT + 100
            ):
                continue

            # Dispatch to type-specific renderer
            self._render_single_effect(effect, screen_x, screen_y, zoom)

    def _render_single_effect(
        self, effect: EffectAnimation, screen_x: float, screen_y: float, zoom: float
    ):
        """Render a single visual effect"""
        # Compute alpha (fades out over time)
        alpha_ratio = 1.0 - effect.progress
        alpha = max(0, min(255, int(255 * alpha_ratio)))

        if alpha <= 0:
            return

        # Compute size (may grow or shrink over time)
        size_multiplier = effect.effect_size * zoom

        if effect.effect_type == "slash":
            self._render_slash_effect(
                screen_x, screen_y, size_multiplier, alpha, effect
            )
        elif effect.effect_type == "impact":
            self._render_impact_effect(
                screen_x, screen_y, size_multiplier, alpha, effect
            )
        elif effect.effect_type == "explosion":
            self._render_explosion_effect(
                screen_x, screen_y, size_multiplier, alpha, effect
            )
        else:
            # Default: circle effect
            self._render_default_effect(
                screen_x, screen_y, size_multiplier, alpha, effect
            )

    def _render_slash_effect(
        self,
        screen_x: float,
        screen_y: float,
        size: float,
        alpha: int,
        effect: EffectAnimation,
    ):
        """Render a slash attack visual effect"""
        import math

        # Create an SRCALPHA surface for the effect
        effect_surface = pygame.Surface(
            (int(size * 60), int(size * 20)), pygame.SRCALPHA
        )

        # Draw slash lines
        color = (*effect.effect_color, alpha)
        thickness = max(1, int(3 * size))

        # Draw multiple diagonal lines to simulate a slash
        for i in range(3):
            start_x = i * 15 * size
            start_y = 5 * size
            end_x = start_x + 30 * size
            end_y = start_y + 10 * size

            pygame.draw.line(
                effect_surface, color, (start_x, start_y), (end_x, end_y), thickness
            )

        # Blit to screen
        rect = effect_surface.get_rect(center=(int(screen_x), int(screen_y)))
        RMS.draw(effect_surface, rect)

    def _render_impact_effect(
        self,
        screen_x: float,
        screen_y: float,
        size: float,
        alpha: int,
        effect: EffectAnimation,
    ):
        """Render an impact (shockwave) visual effect"""
        # Create expanding shockwave ring
        radius = int(20 * size * (1 + effect.progress))
        color = (*effect.effect_color, alpha)

        # Draw multiple concentric rings
        for i in range(3):
            ring_radius = radius - i * 5
            if ring_radius > 0:
                ring_alpha = max(0, alpha - i * 50)
                if ring_alpha > 0:
                    RMS.circle(
                        (*effect.effect_color, ring_alpha),
                        (int(screen_x), int(screen_y)),
                        ring_radius,
                        2,
                    )

    def _render_explosion_effect(
        self,
        screen_x: float,
        screen_y: float,
        size: float,
        alpha: int,
        effect: EffectAnimation,
    ):
        """Render an explosion visual effect"""
        import math
        import random

        # Radius grows over time
        explosion_radius = int(30 * size * effect.progress)

        # Draw explosion particles
        num_particles = 8
        for i in range(num_particles):
            angle = (2 * math.pi * i) / num_particles
            particle_distance = explosion_radius * (0.5 + 0.5 * effect.progress)

            particle_x = screen_x + math.cos(angle) * particle_distance
            particle_y = screen_y + math.sin(angle) * particle_distance

            particle_size = max(1, int(3 * size * (1 - effect.progress)))

            # Random warm color (red, yellow, or orange)
            colors = [(255, 0, 0), (255, 255, 0), (255, 165, 0)]
            color = random.choice(colors)

            RMS.circle(
                (*color, alpha), (int(particle_x), int(particle_y)), particle_size
            )

        # Center flash
        center_radius = int(15 * size * (1 - effect.progress))
        if center_radius > 0:
            RMS.circle(
                (255, 255, 255, alpha), (int(screen_x), int(screen_y)), center_radius
            )

    def _render_default_effect(
        self,
        screen_x: float,
        screen_y: float,
        size: float,
        alpha: int,
        effect: EffectAnimation,
    ):
        """Render a simple default (circle) effect"""
        radius = int(25 * size)
        color = (*effect.effect_color, alpha)
        RMS.circle(color, (int(screen_x), int(screen_y)), radius)

    def _render_attack_indicators(self, camera_offset: List[float], zoom: float = 1.0):
        """Render attack aim-line indicators"""
        for entity in (
            self.world.query().with_all(HexPosition, AttackAnimation).entities()
        ):
            attack_anim = self.world.get_component(entity, AttackAnimation)
            if (
                not attack_anim
                or not attack_anim.is_attacking
                or not attack_anim.show_aim_line
            ):
                continue

            if not attack_anim.start_pixel_pos or not attack_anim.target_pixel_pos:
                continue

            # Convert to screen coordinates
            start_x, start_y = attack_anim.start_pixel_pos
            target_x, target_y = attack_anim.target_pixel_pos

            screen_start_x = start_x * zoom + camera_offset[0]
            screen_start_y = start_y * zoom + camera_offset[1]
            screen_target_x = target_x * zoom + camera_offset[0]
            screen_target_y = target_y * zoom + camera_offset[1]

            # Compute alpha
            alpha = int(255 * attack_anim.aim_line_alpha)
            if alpha <= 0:
                continue

            # Draw type-appropriate aim line
            if attack_anim.attack_type == "ranged":
                self._render_ranged_aim_line(
                    screen_start_x,
                    screen_start_y,
                    screen_target_x,
                    screen_target_y,
                    attack_anim.aim_line_color,
                    alpha,
                    zoom,
                )
            else:
                self._render_melee_aim_line(
                    screen_start_x,
                    screen_start_y,
                    screen_target_x,
                    screen_target_y,
                    attack_anim.aim_line_color,
                    alpha,
                    zoom,
                )

    def _render_ranged_aim_line(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        color: Tuple[int, int, int],
        alpha: int,
        zoom: float,
    ):
        """Render a curved aim line for ranged attacks"""
        import math

        # Create surface with alpha support
        line_surface = pygame.Surface(
            (abs(target_x - start_x) + 100, abs(target_y - start_y) + 100),
            pygame.SRCALPHA,
        )

        # Compute bezier control point for arc
        mid_x = (start_x + target_x) / 2
        mid_y = (start_y + target_y) / 2

        # Compute arc height based on distance
        distance = ((target_x - start_x) ** 2 + (target_y - start_y) ** 2) ** 0.5
        arc_height = min(50 * zoom, distance * 0.2)

        # Compute offset direction perpendicular to the line
        dx = target_x - start_x
        dy = target_y - start_y
        length = (dx**2 + dy**2) ** 0.5
        if length > 0:
            offset_x = -dy / length * arc_height
            offset_y = dx / length * arc_height
        else:
            offset_x = offset_y = 0

        control_x = mid_x + offset_x
        control_y = mid_y + offset_y

        # Draw dashed arc as multiple short line segments
        num_segments = 20
        points = []
        for i in range(num_segments + 1):
            t = i / num_segments
            # Quadratic Bezier curve
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_x + t**2 * target_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_y + t**2 * target_y
            points.append((x, y))

        # Draw dashes (skip alternate segments for dashed appearance)
        line_color = (*color, alpha)
        for i in range(0, len(points) - 1, 2):
            if i + 1 < len(points):
                RMS.line(
                    line_color,
                    points[i],
                    points[i + 1],
                    max(1, int(2 * zoom)),
                )

    def _render_melee_aim_line(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        color: Tuple[int, int, int],
        alpha: int,
        zoom: float,
    ):
        """Render a straight flashing aim line for melee attacks"""
        import math

        # Draw flashing straight line
        line_color = (*color, alpha)
        thickness = max(1, int(3 * zoom))

        # Flash effect using sine wave (oscillates 0–1)
        import time

        flash = (math.sin(time.time() * 10) + 1) / 2
        if flash > 0.3:  # Only render at the bright phase of the flash cycle
            RMS.line(
                line_color,
                (start_x, start_y),
                (target_x, target_y),
                thickness,
            )

            # Draw impact marker at target position
            target_radius = int(15 * zoom)
            RMS.circle(
                line_color, (int(target_x), int(target_y)), target_radius, thickness
            )

    def _render_projectiles(self, camera_offset: List[float], zoom: float = 1.0):
        """Render all active projectiles"""
        for entity in self.world.query().with_all(ProjectileAnimation).entities():
            projectile = self.world.get_component(entity, ProjectileAnimation)
            if not projectile or not projectile.is_flying:
                continue

            # Convert to screen coordinates
            world_x, world_y = projectile.current_pos
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]

            # Skip off-screen projectiles
            if not (
                -50 <= screen_x <= GameConfig.WINDOW_WIDTH + 50
                and -50 <= screen_y <= GameConfig.WINDOW_HEIGHT + 50
            ):
                continue

            # Dispatch to type-specific renderer
            self._render_single_projectile(projectile, screen_x, screen_y, zoom)

    def _render_single_projectile(
        self,
        projectile: ProjectileAnimation,
        screen_x: float,
        screen_y: float,
        zoom: float,
    ):
        """Render a single projectile"""
        import math

        size = projectile.size * zoom

        if projectile.projectile_type == "arrow":
            self._render_arrow(projectile, screen_x, screen_y, size)
        elif projectile.projectile_type == "bolt":
            self._render_bolt(projectile, screen_x, screen_y, size)
        elif projectile.projectile_type == "stone":
            self._render_stone(projectile, screen_x, screen_y, size)
        else:
            # Default: circle projectile
            radius = int(3 * size)
            RMS.circle(projectile.color, (int(screen_x), int(screen_y)), radius)

    def _render_arrow(
        self,
        projectile: ProjectileAnimation,
        screen_x: float,
        screen_y: float,
        size: float,
    ):
        """Render an arrow projectile"""
        import math

        # Arrow length and width
        length = int(20 * size)
        width = int(3 * size)

        # Compute head and tail positions
        cos_rot = math.cos(projectile.rotation)
        sin_rot = math.sin(projectile.rotation)

        # Arrow tip (head)
        head_x = screen_x + cos_rot * length / 2
        head_y = screen_y + sin_rot * length / 2

        # Arrow tail
        tail_x = screen_x - cos_rot * length / 2
        tail_y = screen_y - sin_rot * length / 2

        # Draw arrow shaft
        RMS.line(projectile.color, (tail_x, tail_y), (head_x, head_y), max(1, width))

        # Draw arrowhead
        arrow_size = int(8 * size)
        arrow_angle = math.pi / 6  # 30 degrees

        # Compute arrowhead wing positions
        wing1_x = (
            head_x
            - cos_rot * arrow_size
            + math.cos(projectile.rotation + arrow_angle) * arrow_size
        )
        wing1_y = (
            head_y
            - sin_rot * arrow_size
            + math.sin(projectile.rotation + arrow_angle) * arrow_size
        )

        wing2_x = (
            head_x
            - cos_rot * arrow_size
            + math.cos(projectile.rotation - arrow_angle) * arrow_size
        )
        wing2_y = (
            head_y
            - sin_rot * arrow_size
            + math.sin(projectile.rotation - arrow_angle) * arrow_size
        )

        # Draw arrowhead wings
        RMS.line(
            projectile.color,
            (head_x, head_y),
            (wing1_x, wing1_y),
            max(1, width),
        )
        RMS.line(
            projectile.color,
            (head_x, head_y),
            (wing2_x, wing2_y),
            max(1, width),
        )

    def _render_bolt(
        self,
        projectile: ProjectileAnimation,
        screen_x: float,
        screen_y: float,
        size: float,
    ):
        """Render a crossbow bolt projectile"""
        # Bolts are shorter and thicker than arrows
        import math

        length = int(15 * size)
        width = int(4 * size)

        cos_rot = math.cos(projectile.rotation)
        sin_rot = math.sin(projectile.rotation)

        head_x = screen_x + cos_rot * length / 2
        head_y = screen_y + sin_rot * length / 2
        tail_x = screen_x - cos_rot * length / 2
        tail_y = screen_y - sin_rot * length / 2

        RMS.line(
            projectile.color,
            (tail_x, tail_y),
            (head_x, head_y),
            max(1, width),
        )

    def _render_stone(
        self,
        projectile: ProjectileAnimation,
        screen_x: float,
        screen_y: float,
        size: float,
    ):
        """Render a stone (catapult) projectile"""
        radius = int(5 * size)
        RMS.circle((128, 128, 128), (int(screen_x), int(screen_y)), radius)
        RMS.circle((64, 64, 64), (int(screen_x), int(screen_y)), radius, 1)
