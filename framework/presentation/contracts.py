"""Renderer ownership boundary; adapters receive owned data, never native ECS refs."""

from typing import Any, Mapping, Protocol


class RendererAdapter(Protocol):
    renderer_id: str
    visual_version: str

    def apply(self, delta: Mapping[str, Any]) -> list[dict]:
        """Consume one ordered publication; return presentation events."""
        ...

    def render(self, dt: float, *, inputs: bool = False) -> None:
        """Draw derived state without stepping authoritative gameplay."""
        ...

    def close(self) -> None: ...


class FrameProvider(Protocol):
    """Called after the host's state fence; may not admit input or advance time."""

    renderer_id: str
    visual_version: str

    def capture(self) -> tuple[str | None, str | None]: ...
