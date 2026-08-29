"""ENV tests run without a display or hub.

There is deliberately no `SDL_VIDEODRIVER=dummy` here any more. It used to be
required because `import framework` constructed the engine and opened a window,
and because `GameEngine._init_pygame` set the driver *after* `pygame.init()`.
Both are fixed, so the rule layer no longer needs a display at all -- and this
file staying empty of SDL setup is what proves it.

Tests that genuinely need a surface (`display="dummy"`/`"window"`) construct the
engine themselves, which sets the driver at the right time.
"""
