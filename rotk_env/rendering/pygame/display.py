"""pygame display measurements kept outside rules and configuration."""
from rotk_env.prefabs.config import GameConfig


def sync_game_config_from_display():
    try:
        import pygame
        surface = pygame.display.get_surface()
    except Exception:
        return
    if surface is not None:
        GameConfig.set_viewport_size(*surface.get_size())
