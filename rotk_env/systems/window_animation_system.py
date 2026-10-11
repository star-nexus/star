"""pygame interactive animation: pure trajectories plus renderer resources."""
from .interactive_animation_lifecycle import AnimationSystem as InteractiveLifecycle
from .animation_system import AnimationSystem as PygameAnimationSystem

class AnimationSystem(InteractiveLifecycle, PygameAnimationSystem):
    """Preserve the interactive reference semantics and pygame damage text."""
