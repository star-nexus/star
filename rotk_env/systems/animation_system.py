"""Compatibility import for the pygame animation system.

Renderer-independent callers use animation_lifecycle instead.
"""
from rotk_env.rendering.pygame.animation import AnimationSystem

__all__ = ['AnimationSystem']
