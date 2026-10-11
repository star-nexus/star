"""Compiled STAR kernel. Import errors are deliberately visible to callers."""
from ._native import NativeRuntime, RULES_VERSION, API_VERSION
__all__ = ["NativeRuntime", "RULES_VERSION", "API_VERSION"]
