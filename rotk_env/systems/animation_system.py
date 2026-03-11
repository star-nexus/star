"""
Animation system - handles unit movement animations and visual effects
"""

from pathlib import Path
import pygame
from typing import Tuple, Optional
from framework import System, World, RMS
from ..components import (
    HexPosition,
    MovementAnimation,
    AttackAnimation,
    EffectAnimation,
    ProjectileAnimation,
    UnitStatus,
    DamageNumber,
    Camera,
    Unit,
)
from ..utils.hex_utils import HexConverter
from ..prefabs.config import GameConfig, HexOrientation


class AnimationSystem(System):
    """Animation system"""

    def __init__(self):
        super().__init__(priority=15)  # Processes animations before rendering
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.damage_font = None

    def initialize(self, world: World) -> None:
        self.world = world
        # Initialize font
        # pygame.font.init()
        self.font_file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.damage_font = pygame.font.Font(self.font_file_path, 24)
        self.font_dict = {}

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update the animation system"""
        self._update_movement_animations(delta_time)
        self._update_attack_animations(delta_time)
        self._update_projectile_animations(delta_time)
        self._update_effect_animations(delta_time)
        self._update_unit_status(delta_time)
        self._update_damage_numbers(delta_time)

    def _update_movement_animations(self, delta_time: float):
        """Update movement animations"""
        for entity in (
            self.world.query().with_all(HexPosition, MovementAnimation).entities()
        ):
            pos = self.world.get_component(entity, HexPosition)
            anim = self.world.get_component(entity, MovementAnimation)

            if not pos or not anim or not anim.is_moving:
                continue

            if not anim.path or anim.current_target_index >= len(anim.path):
                # Movement complete
                anim.is_moving = False
                anim.progress = 0.0
                anim.current_target_index = 0
                anim.path.clear()
                continue

            # Update movement progress
            anim.progress += anim.speed * delta_time

            if anim.progress >= 1.0:
                # Reached current target point
                target_hex = anim.path[anim.current_target_index]
                pos.col, pos.row = target_hex
                anim.current_target_index += 1
                anim.progress = 0.0

                if anim.current_target_index >= len(anim.path):
                    # All path segments complete
                    anim.is_moving = False
                else:
                    # Set start and target pixel coordinates for the next segment
                    self._setup_movement_segment(anim, pos)

    def _setup_movement_segment(self, anim: MovementAnimation, pos: HexPosition):
        """Set pixel coordinates for a movement segment"""
        if anim.current_target_index < len(anim.path):
            # Current position
            start_x, start_y = self.hex_converter.hex_to_pixel(pos.col, pos.row)
            anim.start_pixel_pos = (start_x, start_y)

            # Target position
            target_hex = anim.path[anim.current_target_index]
            target_x, target_y = self.hex_converter.hex_to_pixel(
                target_hex[0], target_hex[1]
            )
            anim.target_pixel_pos = (target_x, target_y)

    def _update_unit_status(self, delta_time: float):
        """Update unit status"""
        for entity in self.world.query().with_all(UnitStatus).entities():
            status = self.world.get_component(entity, UnitStatus)
            if not status:
                continue

            status.status_duration += delta_time

            # Check movement status
            anim = self.world.get_component(entity, MovementAnimation)
            if anim and anim.is_moving:
                status.current_status = "moving"
            elif status.current_status == "moving" and (not anim or not anim.is_moving):
                status.current_status = "idle"

    def _update_damage_numbers(self, delta_time: float):
        """Update damage number display"""
        entities_to_remove = []

        for entity in self.world.query().with_all(DamageNumber).entities():
            damage_num = self.world.get_component(entity, DamageNumber)
            if not damage_num:
                continue

            damage_num.elapsed_time += delta_time

            if damage_num.elapsed_time >= damage_num.lifetime:
                entities_to_remove.append(entity)
                continue

            # Update position
            new_x = damage_num.position[0] + damage_num.velocity[0] * delta_time
            new_y = damage_num.position[1] + damage_num.velocity[1] * delta_time
            damage_num.position = (new_x, new_y)

        # Remove expired damage numbers
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def render_damage_numbers(self):
        """Render damage numbers"""
        if not self.damage_font:
            return

        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        camera_offset = camera.get_offset()

        for entity in self.world.query().with_all(DamageNumber).entities():
            damage_num = self.world.get_component(entity, DamageNumber)
            if not damage_num:
                continue

            # Calculate alpha (fade out over time)
            alpha_ratio = 1.0 - (damage_num.elapsed_time / damage_num.lifetime)
            alpha = int(255 * alpha_ratio)

            if alpha <= 0:
                continue

            # Create color with alpha
            color = (*damage_num.color, alpha)

            # Render text
            text = damage_num.text

            # Create a font for the given size if needed
            font_to_use = self.damage_font
            if hasattr(damage_num, "font_size") and damage_num.font_size != 24:
                try:
                    if damage_num.font_size not in self.font_dict:
                        # If font size is not in cache, create a new font
                        if not self.font_file_path.exists():
                            raise FileNotFoundError(
                                f"Font file not found: {self.font_file_path}"
                            )
                        self.font_dict[damage_num.font_size] = pygame.font.Font(
                            self.font_file_path, damage_num.font_size
                        )
                    font_to_use = self.font_dict[damage_num.font_size]
                except:
                    font_to_use = self.damage_font

            text_surface = font_to_use.render(text, True, damage_num.color)

            # Apply alpha
            if alpha < 255:
                text_surface.set_alpha(alpha)

            # Calculate screen position
            screen_x = damage_num.position[0] + camera_offset[0]
            screen_y = damage_num.position[1] + camera_offset[1]

            RMS.draw(text_surface, (screen_x, screen_y))

    def get_unit_render_position(self, entity: int) -> Optional[Tuple[float, float]]:
        """Get the render position of a unit (accounting for movement and attack animations)"""
        pos = self.world.get_component(entity, HexPosition)
        if not pos:
            return None

        # Check attack animation first
        attack_anim = self.world.get_component(entity, AttackAnimation)
        if attack_anim and attack_anim.is_attacking and attack_anim.current_render_pos:
            return attack_anim.current_render_pos

        # Check movement animation
        move_anim = self.world.get_component(entity, MovementAnimation)
        if (
            not move_anim
            or not move_anim.is_moving
            or not move_anim.start_pixel_pos
            or not move_anim.target_pixel_pos
        ):
            # No animation: return static position
            return self.hex_converter.hex_to_pixel(pos.col, pos.row)

        # Interpolate current render position
        start_x, start_y = move_anim.start_pixel_pos
        target_x, target_y = move_anim.target_pixel_pos

        current_x = start_x + (target_x - start_x) * move_anim.progress
        current_y = start_y + (target_y - start_y) * move_anim.progress

        return (current_x, current_y)

    def start_unit_movement(self, entity: int, path: list):
        """Start unit movement animation"""
        if not path or len(path) < 2:
            return

        pos = self.world.get_component(entity, HexPosition)
        if not pos:
            return

        # Get or create movement animation component
        anim = self.world.get_component(entity, MovementAnimation)
        if not anim:
            anim = MovementAnimation()
            self.world.add_component(entity, anim)

        # Set path (skip the starting position)
        anim.path = path[1:]  # skip current position
        anim.current_target_index = 0
        anim.progress = 0.0
        anim.is_moving = True

        # Set up the first movement segment
        self._setup_movement_segment(anim, pos)

    def start_attack_animation(
        self, attacker_entity: int, target_entity: int, attack_type: str = "melee"
    ):
        """Start an attack animation."""
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)

        if not attacker_pos or not target_pos:
            return

        # Get or create attack animation component
        anim = self.world.get_component(attacker_entity, AttackAnimation)
        if not anim:
            anim = AttackAnimation()
            self.world.add_component(attacker_entity, anim)

        # Set target position
        anim.target_position = (target_pos.col, target_pos.row)
        anim.attack_type = attack_type
        anim.is_attacking = True
        anim.progress = 0.0
        anim.phase = "prepare"
        anim.show_aim_line = False
        anim.aim_line_alpha = 0.0

        # Compute world pixel coordinates
        start_x, start_y = self.hex_converter.hex_to_pixel(
            attacker_pos.col, attacker_pos.row
        )
        target_x, target_y = self.hex_converter.hex_to_pixel(
            target_pos.col, target_pos.row
        )

        anim.start_pixel_pos = (start_x, start_y)
        anim.target_pixel_pos = (target_x, target_y)
        anim.current_render_pos = (start_x, start_y)

        # Tune animation parameters based on attack type
        if attack_type == "ranged":
            anim.speed = 5.0  # ranged attacks are slightly slower
            anim.total_duration = 1.0
            anim.prepare_ratio = 0.15
            anim.aim_ratio = 0.25  # longer aim phase
            anim.strike_ratio = 0.45
            anim.return_ratio = 0.15
            anim.aim_line_color = (255, 100, 100)  # red aim line
        else:  # melee
            anim.speed = 8.0
            anim.total_duration = 0.8
            anim.prepare_ratio = 0.2
            anim.aim_ratio = 0.15  # shorter aim phase
            anim.strike_ratio = 0.45
            anim.return_ratio = 0.2
            anim.aim_line_color = (255, 255, 100)  # yellow aim line

        # Reset projectile-created flag
        if hasattr(anim, "_projectile_created"):
            delattr(anim, "_projectile_created")

    def create_attack_effect(
        self, world_pos: Tuple[float, float], effect_type: str = "slash"
    ):
        """Create an attack visual effect."""
        entity = self.world.create_entity()

        effect = EffectAnimation(
            effect_type=effect_type,
            effect_position=world_pos,
            effect_size=1.0,
            effect_color=(255, 255, 255),
            duration=0.5,
            is_playing=True,
            progress=0.0,
            elapsed_time=0.0,
        )

        self.world.add_component(entity, effect)

    def _update_attack_animations(self, delta_time: float):
        """Update all active attack animations."""
        entities_to_complete = []

        for entity in (
            self.world.query().with_all(HexPosition, AttackAnimation).entities()
        ):
            pos = self.world.get_component(entity, HexPosition)
            anim = self.world.get_component(entity, AttackAnimation)

            if not pos or not anim or not anim.is_attacking:
                continue

            # Advance animation progress
            anim.progress += anim.speed * delta_time

            if anim.progress >= anim.total_duration:
                # Attack animation complete
                anim.is_attacking = False
                anim.progress = 0.0
                anim.phase = "prepare"
                anim.current_render_pos = None
                entities_to_complete.append(entity)
                continue

            # Determine current phase and phase-relative progress
            self._update_attack_phase(anim)

        # Remove completed attack animation components
        for entity in entities_to_complete:
            if self.world.has_component(entity, AttackAnimation):
                self.world.remove_component(entity, AttackAnimation)

    def _update_attack_phase(self, anim: AttackAnimation):
        """Update the current attack animation phase and rendered position."""
        progress_ratio = anim.progress / anim.total_duration

        if progress_ratio <= anim.prepare_ratio:
            # Prepare phase: slight forward movement toward target
            anim.phase = "prepare"
            phase_progress = progress_ratio / anim.prepare_ratio
            if anim.attack_type == "melee":
                self._calculate_attack_position(anim, phase_progress * 0.1)  # slight shift
            else:
                # Ranged attack: no movement, just ready stance
                self._calculate_attack_position(anim, 0)
            anim.show_aim_line = False

        elif progress_ratio <= anim.prepare_ratio + anim.aim_ratio:
            # Aim phase: show attack indicator line
            anim.phase = "aim"
            aim_start = anim.prepare_ratio
            phase_progress = (progress_ratio - aim_start) / anim.aim_ratio

            # Show aim line with increasing opacity
            anim.show_aim_line = True
            anim.aim_line_alpha = min(1.0, phase_progress * 2.0)

            if anim.attack_type == "melee":
                self._calculate_attack_position(anim, 0.1)  # hold prepare position
            else:
                self._calculate_attack_position(anim, 0)

        elif progress_ratio <= anim.prepare_ratio + anim.aim_ratio + anim.strike_ratio:
            # Strike/shoot phase
            anim.phase = "strike" if anim.attack_type == "melee" else "shoot"
            strike_start = anim.prepare_ratio + anim.aim_ratio
            phase_progress = (progress_ratio - strike_start) / anim.strike_ratio

            anim.show_aim_line = False  # hide aim line

            if anim.attack_type == "melee":
                # Melee: rush toward the target
                eased_progress = self._ease_out_back(phase_progress)
                self._calculate_attack_position(
                    anim, 0.1 + eased_progress * 0.7
                )  # from 10% to 80%
            else:
                # Ranged: spawn projectile and hold position
                if phase_progress == 0 or not hasattr(anim, "_projectile_created"):
                    self._create_projectile(anim)
                    anim._projectile_created = True
                self._calculate_attack_position(anim, 0)

        else:
            # Return phase: return to original position
            anim.phase = "return"
            return_start = anim.prepare_ratio + anim.aim_ratio + anim.strike_ratio
            phase_progress = (progress_ratio - return_start) / anim.return_ratio

            anim.show_aim_line = False

            if anim.attack_type == "melee":
                # Use easing for a smoother return
                eased_progress = self._ease_in_out(phase_progress)
                self._calculate_attack_position(
                    anim, 0.8 - eased_progress * 0.8
                )  # from 80% back to 0%
            else:
                self._calculate_attack_position(anim, 0)

    def _calculate_attack_position(self, anim: AttackAnimation, progress: float):
        """Calculate the current rendered position for the attack animation."""
        if not anim.start_pixel_pos or not anim.target_pixel_pos:
            return

        start_x, start_y = anim.start_pixel_pos
        target_x, target_y = anim.target_pixel_pos

        # Interpolate position based on progress
        current_x = start_x + (target_x - start_x) * progress
        current_y = start_y + (target_y - start_y) * progress

        anim.current_render_pos = (current_x, current_y)

    def _ease_out_back(self, t: float) -> float:
        """Overshoot/bounce ease-out (well-suited for strike impact feel)."""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

    def _ease_in_out(self, t: float) -> float:
        """Smooth ease-in-out (SmoothStep)."""
        return t * t * (3.0 - 2.0 * t)

    def _update_effect_animations(self, delta_time: float):
        """Update all active effect animations."""
        entities_to_remove = []

        for entity in self.world.query().with_all(EffectAnimation).entities():
            effect = self.world.get_component(entity, EffectAnimation)
            if not effect or not effect.is_playing:
                continue

            effect.elapsed_time += delta_time
            effect.progress = min(effect.elapsed_time / effect.duration, 1.0)

            if effect.elapsed_time >= effect.duration:
                entities_to_remove.append(entity)

        # Remove completed effects
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _update_projectile_animations(self, delta_time: float):
        """Update all active projectile animations."""
        entities_to_remove = []

        for entity in self.world.query().with_all(ProjectileAnimation).entities():
            projectile = self.world.get_component(entity, ProjectileAnimation)
            if not projectile or not projectile.is_flying:
                continue

            # Compute flight distance
            start_x, start_y = projectile.start_pos
            target_x, target_y = projectile.target_pos
            total_distance = (
                (target_x - start_x) ** 2 + (target_y - start_y) ** 2
            ) ** 0.5

            if total_distance <= 0:
                entities_to_remove.append(entity)
                continue

            # Advance flight progress
            distance_per_second = projectile.flight_speed
            progress_per_second = distance_per_second / total_distance
            projectile.flight_progress += progress_per_second * delta_time

            if projectile.flight_progress >= 1.0:
                # Projectile reached target
                projectile.is_flying = False
                entities_to_remove.append(entity)
                continue

            # Calculate current position with arc trajectory
            self._calculate_projectile_position(projectile)

        # Remove completed projectiles
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _calculate_projectile_position(self, projectile: ProjectileAnimation):
        """Calculate the current position of a projectile with arc trajectory."""
        start_x, start_y = projectile.start_pos
        target_x, target_y = projectile.target_pos
        progress = projectile.flight_progress

        # Linear interpolation base position
        current_x = start_x + (target_x - start_x) * progress
        current_y = start_y + (target_y - start_y) * progress

        # Apply arc offset (peaks at mid-flight)
        arc_offset = projectile.arc_height * 4 * progress * (1 - progress)
        current_y -= arc_offset

        projectile.current_pos = (current_x, current_y)

        # Calculate rotation angle to face the direction of flight
        import math

        if progress < 1.0:
            # Sample a slightly ahead position to determine heading
            next_progress = min(1.0, progress + 0.01)
            next_x = start_x + (target_x - start_x) * next_progress
            next_y = (
                start_y
                + (target_y - start_y) * next_progress
                - projectile.arc_height * 4 * next_progress * (1 - next_progress)
            )

            dx = next_x - current_x
            dy = next_y - current_y
            projectile.rotation = math.atan2(dy, dx)

    def _create_projectile(self, attack_anim: AttackAnimation):
        """Create a projectile entity for a ranged attack."""
        if not attack_anim.start_pixel_pos or not attack_anim.target_pixel_pos:
            return

        entity = self.world.create_entity()

        # Determine projectile properties based on attack type
        if attack_anim.attack_type == "ranged":
            projectile_type = "arrow"
            color = (139, 69, 19)  # brown arrow
            arc_height = 30.0
            speed = 600.0
        else:
            projectile_type = "bolt"
            color = (192, 192, 192)  # silver bolt
            arc_height = 20.0
            speed = 800.0

        projectile = ProjectileAnimation(
            start_pos=attack_anim.start_pixel_pos,
            target_pos=attack_anim.target_pixel_pos,
            current_pos=attack_anim.start_pixel_pos,
            flight_progress=0.0,
            flight_speed=speed,
            is_flying=True,
            projectile_type=projectile_type,
            arc_height=arc_height,
            size=1.0,
            color=color,
            rotation=0.0,
        )

        self.world.add_component(entity, projectile)

    def create_damage_number(self, damage: int, world_pos: Tuple[float, float]):
        """Spawn a floating damage number at world_pos."""
        entity = self.world.create_entity()

        damage_num = DamageNumber(
            text=str(damage),
            position=world_pos,
            lifetime=2.0,
            velocity=(0, -50),  # float upward
            color=(255, 0, 0) if damage > 0 else (0, 255, 0),  # red for damage, green for healing
            font_size=24,
        )

        self.world.add_component(entity, damage_num)

    def create_miss_indicator(self, world_pos: Tuple[float, float]):
        """Spawn a floating MISS indicator at world_pos."""
        entity = self.world.create_entity()

        miss_indicator = DamageNumber(
            text="MISS",
            position=world_pos,
            lifetime=1.5,
            velocity=(0, -30),  # float upward slowly
            color=(128, 128, 128),  # grey
            font_size=20,
        )

        self.world.add_component(entity, miss_indicator)

    def create_crit_indicator(self, world_pos: Tuple[float, float]):
        """Spawn a floating CRIT! indicator at world_pos."""
        entity = self.world.create_entity()

        crit_indicator = DamageNumber(
            text="CRIT!",
            position=world_pos,
            lifetime=2.5,
            velocity=(0, -60),  # float upward quickly
            color=(255, 255, 0),  # yellow
            font_size=28,
        )

        self.world.add_component(entity, crit_indicator)

    def create_healing_number(self, healing: int, world_pos: Tuple[float, float]):
        """Spawn a floating healing number at world_pos."""
        entity = self.world.create_entity()

        healing_num = DamageNumber(
            text=f"+{healing}",
            position=world_pos,
            lifetime=2.0,
            velocity=(0, -40),  # float upward
            color=(0, 255, 0),  # green healing
            font_size=24,
        )

        self.world.add_component(entity, healing_num)

    def create_text_indicator(
        self,
        text: str,
        world_pos: Tuple[float, float],
        color: Tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
        lifetime: float = 2.0,
        velocity: Tuple[float, float] = (0, -50),
    ):
        """Spawn a generic floating text indicator at world_pos."""
        entity = self.world.create_entity()

        text_indicator = DamageNumber(
            text=text,
            position=world_pos,
            lifetime=lifetime,
            velocity=velocity,
            color=color,
            font_size=font_size,
        )

        self.world.add_component(entity, text_indicator)
