"""API call, token, and error accounting, reported to the ENV at game end.

Every agent shares one collector instance so that the totals reported to the
ENV cover the whole run regardless of which component saw the failure. The
per-file agents used to disagree about which of these counters existed at
all, which made error metrics incomparable between models and between modes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .console import console


def _read(obj: Any, *keys: str) -> Optional[int]:
    """Walk a dict or attribute chain and return an int, or None if absent."""
    cur: Any = obj
    for key in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    if cur is None:
        return None
    try:
        return int(cur)
    except (TypeError, ValueError):
        return None


def parse_usage(usage: Any) -> Dict[str, int]:
    """Normalise chat-completions and Responses API usage into one shape."""
    empty = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "reasoning_tokens": 0,
    }
    if not usage:
        return empty

    prompt = _read(usage, "prompt_tokens") or _read(usage, "input_tokens") or 0
    completion = (
        _read(usage, "completion_tokens") or _read(usage, "output_tokens") or 0
    )
    hit = _read(usage, "prompt_cache_hit_tokens")
    if hit is None:
        hit = _read(usage, "input_tokens_details", "cached_tokens") or 0
    miss = _read(usage, "prompt_cache_miss_tokens")
    if miss is None:
        miss = max(0, prompt - hit)
    reasoning = (
        _read(usage, "completion_tokens_details", "reasoning_tokens")
        or _read(usage, "output_tokens_details", "reasoning_tokens")
        or 0
    )
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "prompt_cache_hit_tokens": hit,
        "prompt_cache_miss_tokens": miss,
        "reasoning_tokens": reasoning,
    }


class ErrorStatsCollector:
    """Counts API calls plus HTTP, tool-call, and model-capability failures."""

    def __init__(self):
        self.total_api_call_count = 0

        # Transport-level failures.
        self.http_connect_error = 0
        self.http_timeout = 0
        self.http_4xx = 0
        self.http_5xx = 0
        self.http_bad_json = 0
        self.http_other = 0

        # The model emitted a tool call the harness could not use.
        self.tool_in_content = 0
        self.tool_invalid_tool = 0
        self.tool_param_error = 0

        # The model misjudged the game world (distance, reachability, vision).
        self.spatial_awareness_error = 0

        # Token accounting across successful responses.
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.prompt_cache_hit_tokens = 0
        self.prompt_cache_miss_tokens = 0
        self.reasoning_tokens = 0

    def add_total_api_call_count(self):
        self.total_api_call_count += 1

    def add_http_connect_error(self):
        self.http_connect_error += 1

    def add_http_timeout(self):
        self.http_timeout += 1

    def add_http_4xx(self):
        self.http_4xx += 1

    def add_http_5xx(self):
        self.http_5xx += 1

    def add_http_bad_json(self):
        self.http_bad_json += 1

    def add_http_other(self):
        self.http_other += 1

    def add_tool_in_content(self):
        self.tool_in_content += 1

    def add_tool_invalid_tool(self):
        self.tool_invalid_tool += 1

    def add_tool_param_error(self):
        self.tool_param_error += 1

    def add_spatial_awareness_error(self):
        self.spatial_awareness_error += 1

    def record_usage(self, usage: Any) -> Dict[str, int]:
        """Fold one response's usage into the run totals and log the hit rate."""
        parsed = parse_usage(usage)
        self.prompt_tokens += parsed["prompt_tokens"]
        self.completion_tokens += parsed["completion_tokens"]
        self.prompt_cache_hit_tokens += parsed["prompt_cache_hit_tokens"]
        self.prompt_cache_miss_tokens += parsed["prompt_cache_miss_tokens"]
        self.reasoning_tokens += parsed["reasoning_tokens"]

        call_prompt = parsed["prompt_tokens"]
        call_hit = parsed["prompt_cache_hit_tokens"]
        call_rate = (call_hit / call_prompt * 100) if call_prompt else 0.0
        reasoning_bit = (
            f" reasoning={parsed['reasoning_tokens']}"
            if parsed["reasoning_tokens"]
            else ""
        )
        console.print(
            f"💾 tokens prompt={call_prompt} hit={call_hit} "
            f"miss={parsed['prompt_cache_miss_tokens']} "
            f"completion={parsed['completion_tokens']}{reasoning_bit} "
            f"cache_hit={call_rate:.1f}%  "
            f"(run hit={self.prompt_cache_hit_tokens} "
            f"miss={self.prompt_cache_miss_tokens})",
            style="cyan",
        )
        return parsed

    def get_total_api_call_count(self) -> int:
        return self.total_api_call_count

    def get_http_errors_total(self) -> int:
        return (
            self.http_connect_error
            + self.http_timeout
            + self.http_4xx
            + self.http_5xx
            + self.http_bad_json
            + self.http_other
        )

    def get_tool_call_gen_errors_total(self) -> int:
        return self.tool_in_content + self.tool_invalid_tool + self.tool_param_error

    def get_llm_capability_errors_total(self) -> int:
        return self.spatial_awareness_error

    def get_error_api_call_count(self) -> int:
        return (
            self.get_http_errors_total()
            + self.get_tool_call_gen_errors_total()
            + self.get_llm_capability_errors_total()
        )

    def get_successful_api_call_count(self) -> int:
        return self.get_total_api_call_count() - self.get_error_api_call_count()

    def cache_hit_rate(self) -> float:
        prompt = self.prompt_tokens
        if prompt <= 0:
            return 0.0
        return round(self.prompt_cache_hit_tokens / prompt * 100, 2)

    def _rate(self, numerator: int) -> float:
        total = self.get_total_api_call_count()
        if total <= 0:
            return 0.0
        return round(numerator / total * 100, 2)

    def get_api_stats(self) -> Dict[str, Any]:
        """Compact summary reported alongside the error breakdown."""
        return {
            "total_calls": self.get_total_api_call_count(),
            "successful_calls": self.get_successful_api_call_count(),
            "failed_calls": self.get_error_api_call_count(),
            "success_rate": self._rate(self.get_successful_api_call_count()),
            "error_rate": self._rate(self.get_error_api_call_count()),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cache_hit_rate": self.cache_hit_rate(),
        }

    def get_error_breakdown(self) -> Dict[str, Any]:
        """Full breakdown, for the settlement report."""
        return {
            "total_api_call_count": self.get_total_api_call_count(),
            "error_api_call_count": self.get_error_api_call_count(),
            "successful_api_call_count": self.get_successful_api_call_count(),
            "error_rate": self._rate(self.get_error_api_call_count()),
            "successful_rate": self._rate(self.get_successful_api_call_count()),
            "http_errors_total": self.get_http_errors_total(),
            "http": {
                "connect_error": self.http_connect_error,
                "timeout": self.http_timeout,
                "http_4xx": self.http_4xx,
                "http_5xx": self.http_5xx,
                "bad_json": self.http_bad_json,
                "other": self.http_other,
            },
            "tool_call_gen_errors_total": self.get_tool_call_gen_errors_total(),
            "tool_call_gen": {
                "tool_in_content": self.tool_in_content,
                "tool_invalid_tool": self.tool_invalid_tool,
                "tool_param_error": self.tool_param_error,
            },
            "llm_capability_errors_total": self.get_llm_capability_errors_total(),
            "llm_capability": {
                "spatial_awareness_error": self.spatial_awareness_error,
            },
        }


__all__ = ["ErrorStatsCollector", "parse_usage"]
