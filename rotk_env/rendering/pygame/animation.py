"""pygame fonts and damage-number drawing over the shared pure lifecycle."""
from pathlib import Path
import pygame
from framework.engine import RMS
from rotk_env.components import Camera, DamageNumber
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.animation_lifecycle import AnimationSystem as LifecycleAnimationSystem

class AnimationSystem(LifecycleAnimationSystem):
    def __init__(self):
        super().__init__()
        self.damage_font = None
        self._damage_text_cache = {}

    def initialize(self, world) -> None:
        super().initialize(world)
        # Framework import is side-effect free, so each font-using system
        # initializes Pygame's font module explicitly.
        pygame.font.init()
        self.font_file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.damage_font = pygame.font.Font(self.font_file_path, 24)
        self.font_dict = {}
        self._damage_text_cache.clear()


    def render_damage_numbers(self):
        """Reuse per-effect text pixels; scan only active effects and cull blits."""
        if not self.damage_font:
            self._damage_text_cache.clear()
            return

        camera = self.world.get_singleton_component(Camera)
        if not camera:
            self._damage_text_cache.clear()
            return

        camera_offset = camera.get_offset()
        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        previous = self._damage_text_cache
        current = {}

        for entity in self.world.query().with_all(DamageNumber).ordered_entities():
            damage_num = self.world.get_component(entity, DamageNumber)
            if not damage_num:
                continue

            # Calculate alpha (fade out over time)
            alpha_ratio = 1.0 - (damage_num.elapsed_time / damage_num.lifetime)
            alpha = int(255 * alpha_ratio)

            if alpha <= 0:
                continue

            screen_x = int(damage_num.position[0] + camera_offset[0])
            screen_y = int(damage_num.position[1] + camera_offset[1])
            cached = previous.get(entity)
            if screen_x >= width or screen_y >= height:
                # No font/size/raster work for a new effect beyond these edges.
                if cached is not None and cached[0] is damage_num:
                    current[entity] = cached
                continue

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

            signature = (text, tuple(damage_num.color), font_to_use)
            if (cached is None or cached[0] is not damage_num
                    or cached[1] != signature):
                cached = (damage_num, signature, font_to_use.size(text), None)
            current[entity] = cached
            text_width, text_height = cached[2]
            if screen_x + text_width <= 0 or screen_y + text_height <= 0:
                continue

            text_surface = cached[3]
            if text_surface is None:
                text_surface = font_to_use.render(text, True, damage_num.color)
                current[entity] = (damage_num, signature, cached[2], text_surface)
            # Each effect owns its surface: two CRITs at different ages must
            # never overwrite each other's alpha in the deferred render queue.
            text_surface.set_alpha(alpha)

            RMS.draw(text_surface, (screen_x, screen_y))

        # Replaced components, expired effects and external deletions disappear
        # here without an all-resident query or a growing historical cache.
        self._damage_text_cache = current


