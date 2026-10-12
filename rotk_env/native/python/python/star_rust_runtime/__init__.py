"""STAR Rust ECS/ENV runtime exposed to Python. Import errors remain visible."""
from ._native import NativeRuntime, RULES_VERSION, API_VERSION
__all__ = ["NativeRuntime", "RULES_VERSION", "API_VERSION"]
