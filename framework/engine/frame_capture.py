"""Capture the existing display buffer with legacy RoTK image/error semantics.

No rendering, perspective selection, or world access occurs here. The legacy
encoder has no filename hint (TGA on pygame 2.6.1), despite the historical PNG
response label. Changing that wire contract is a separate compatibility decision.
"""
import base64
import io


def capture_rendered_frame():
    # pygame and the render stack are imported here rather than at module
    # scope: this is the only path in the handler that needs a display, and
    # `get_faction_state_vlm` is not in the skirmish action set. A top-level
    # import would pull SDL into every headless rule test.
    try:
        import pygame
        from framework.engine.renders import RenderEngine
    except ImportError as e:
        return None, f"Display stack unavailable: {e}"

    try:
        re = RenderEngine()
        screen = re.screen
    except Exception as e:
        return None, f"RenderEngine/screen not available: {e}"

    try:
        surf = screen.copy()
    except Exception as e:
        return None, f"Screen copy failed: {e}"

    try:
        buf = io.BytesIO()
        pygame.image.save(surf, buf)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, None
    except Exception as e:
        return None, f"Encode frame to base64 failed: {e}"
