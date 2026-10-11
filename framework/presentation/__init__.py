"""Display contracts and bounded delivery, independent of SDL and game rules."""

from .contracts import FrameProvider, RendererAdapter
from .stream import SnapshotMailbox

__all__ = ['FrameProvider', 'RendererAdapter', 'SnapshotMailbox']
