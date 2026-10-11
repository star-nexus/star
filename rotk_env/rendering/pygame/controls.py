"""Translate pygame events to renderer-independent human control bindings."""
import pygame
from rotk_env.prefabs.controls import KEY_BINDINGS, binding_for_key as semantic_binding

_KEY_NAMES = {getattr(pygame, 'K_' + binding.key): binding.key for binding in KEY_BINDINGS}


def binding_for_key(key: int, modifiers: int = 0):
    if modifiers & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_GUI):
        return None
    return semantic_binding(_KEY_NAMES.get(key), bool(modifiers & pygame.KMOD_SHIFT))
