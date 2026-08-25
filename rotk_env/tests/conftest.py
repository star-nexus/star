"""ENV tests run without a display or hub."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
