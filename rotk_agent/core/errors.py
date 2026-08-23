"""Error enrichment, logging, and classification.

The classifiers decide control flow in the chat loop: a context overflow is
recoverable by trimming history, an exhausted account or an unreachable LLM
endpoint is not.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from .console import console


class ProviderError(Exception):
    """A call to a model API failed.

    Defined here rather than in `adapters/` so that the core chat loop can
    reason about provider failures without importing any adapter.
    """


class RecoverableProviderError(ProviderError):
    """Failed in a way a smaller, cleaner request might survive.

    The loop responds by trimming history and retrying once, rather than
    ending the run.
    """


def create_error_details(exception: Exception, **extra_context) -> Dict[str, Any]:
    """Build a JSON-serializable record of an exception plus its context."""
    error_details: Dict[str, Any] = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "timestamp": datetime.now().isoformat(),
    }
    error_details.update(extra_context)

    tb_lines = traceback.format_exception(
        type(exception), exception, exception.__traceback__
    )
    error_details["full_traceback"] = "".join(tb_lines)

    def request_url(exc: Exception) -> str:
        # httpx exposes `.request` as a property that *raises* when the request
        # was never attached, so `getattr(..., None)` does not shield the caller.
        try:
            return str(exc.request.url)
        except Exception:
            return "unknown"

    if isinstance(exception, httpx.HTTPStatusError):
        error_details["http_status_code"] = exception.response.status_code
        error_details["response_headers"] = dict(exception.response.headers)
        try:
            error_details["response_body"] = exception.response.text
        except Exception:
            error_details["response_body"] = "Cannot read response body"
    elif isinstance(exception, httpx.ConnectError):
        error_details["connection_error"] = "Cannot connect to server"
        error_details["request_url"] = request_url(exception)
    elif isinstance(exception, httpx.TimeoutException):
        error_details["timeout_error"] = "Request timeout"
        error_details["request_url"] = request_url(exception)
    elif isinstance(exception, httpx.RequestError):
        error_details["request_error"] = "Request error"
        error_details["request_url"] = request_url(exception)
    elif isinstance(exception, TimeoutError):
        error_details["timeout_error"] = "Operation timeout"
    elif "json" in str(exception).lower():
        error_details["json_error"] = "JSON parsing error, API return format may be wrong"

    return error_details


def log_error_to_file(
    error_details: Dict[str, Any], display_console: bool = True
) -> Optional[str]:
    """Print an error report and persist it next to the run."""
    if display_console:
        console.print("=" * 80, style="red")
        console.print("🚨 Detailed error information", style="red bold")
        console.print("=" * 80, style="red")
        console.print(
            f"📍 Exception type: {error_details.get('exception_type', 'Unknown')}",
            style="red",
        )
        console.print(
            f"📝 Error message: {error_details.get('exception_message', 'Unknown')}",
            style="red",
        )
        console.print(
            f"⏰ Occurrence time: {error_details.get('timestamp', 'Unknown')}",
            style="red",
        )

        if "function_name" in error_details:
            console.print(
                f"🔧 Occurred function: {error_details['function_name']}", style="red"
            )
        if "iteration" in error_details:
            console.print(
                f"🔄 Current iteration: {error_details['iteration']}", style="red"
            )

        if "http_status_code" in error_details:
            console.print(
                f"🌐 HTTP status code: {error_details['http_status_code']}", style="red"
            )
            console.print(
                f"📤 Response headers: {error_details['response_headers']}",
                style="yellow",
            )
            console.print(
                f"📥 Response body: {str(error_details['response_body'])[:500]}...",
                style="yellow",
            )

        if "connection_error" in error_details:
            console.print(
                f"🔌 Connection error: {error_details['connection_error']}", style="red"
            )
            console.print(
                f"🎯 Request URL: {error_details.get('request_url')}", style="yellow"
            )

        if "timeout_error" in error_details:
            console.print(
                f"⏱️ Timeout error: {error_details['timeout_error']}", style="red"
            )
            if "request_url" in error_details:
                console.print(
                    f"🎯 Request URL: {error_details['request_url']}", style="yellow"
                )

        if "json_error" in error_details:
            console.print(f"📋 JSON error: {error_details['json_error']}", style="red")

        console.print("\n🔍 Complete stack trace:", style="red")
        console.print(error_details.get("full_traceback", ""), style="dim red")

    try:
        error_log_file = f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(error_log_file, "w", encoding="utf-8") as f:
            json.dump(error_details, f, ensure_ascii=False, indent=2)

        if display_console:
            console.print(f"💾 Error details saved to: {error_log_file}", style="blue")
            console.print("=" * 80, style="red")

        return error_log_file
    except Exception as log_error:
        if display_console:
            console.print(f"⚠️ Cannot save error log: {log_error}", style="yellow")
        return None


def handle_error_with_logging(exception: Exception, **extra_context) -> Dict[str, Any]:
    """Enrich, log, and wrap an exception as a failure result."""
    error_details = create_error_details(exception, **extra_context)
    log_file = log_error_to_file(error_details, display_console=True)
    return {
        "success": False,
        "error": str(exception),
        "error_details": error_details,
        "error_log_file": log_file,
    }


def _blob(exc: Exception, error_details: dict | None) -> str:
    text = str(exc) if exc else ""
    if error_details:
        try:
            text += " " + json.dumps(error_details, ensure_ascii=False)
        except Exception:
            text += " " + str(error_details)
    return text.lower()


def _message_text(exc: Exception, error_details: dict | None) -> str:
    """Provider-facing text only. Never the traceback — it mentions `tokens`."""
    parts = [str(exc) if exc else ""]
    details = error_details or {}
    for key in ("exception_message", "response_body"):
        value = details.get(key)
        if value:
            parts.append(str(value))
    rsp = details.get("response_json")
    if isinstance(rsp, dict):
        message = (rsp.get("error") or {}).get("message", "")
        if message:
            parts.append(str(message))
    return " ".join(parts).lower()


# Phrases that mean the prompt itself was too big. Keep them paired so a
# rate-limit or quota error that merely mentions "tokens" does not match.
OVERFLOW_PHRASES = (
    "maximum context length",
    "max context length",
    "context length is",
    "context window",
    "prompt is too long",
    "too many tokens",
    "context_length_exceeded",
    "exceeds the maximum context",
    "this model's maximum context",
    "reduce the length of the messages",
)


def is_context_overflow_error(
    exc: Exception, error_details: dict | None = None
) -> bool:
    """Recoverable: the prompt outgrew the model's context window."""
    return any(phrase in _message_text(exc, error_details) for phrase in OVERFLOW_PHRASES)


def is_account_balance_error(exc: Exception, error_details: dict | None = None) -> bool:
    """Terminal: the provider account cannot pay for more calls."""
    s = _blob(exc, error_details)
    return (
        ("balance" in s and "insufficient" in s)
        or "account balance" in s
        or "30001" in s
    )


def is_network_unreachable_error(
    exc: Exception, error_details: dict | None = None
) -> bool:
    """Terminal: retrying the LLM endpoint cannot succeed."""
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError)):
        return True

    details = error_details or {}
    if any(k in details for k in ("connection_error", "timeout_error", "request_error")):
        return True

    msg = (details.get("exception_message") or str(exc)).lower()
    phrases = (
        "cannot connect",
        "connection refused",
        "getaddrinfo failed",
        "network is unreachable",
        "connection error",
        "timeout",
        "timed out",
        "connecterror",
        "timeoutexception",
    )
    return any(p in msg for p in phrases)


TERMINAL_CHAT_REASONS = frozenset(
    {
        "game_ended",
        "account_balance_insufficient",
        "llm_unreachable",
    }
)


def is_terminal_chat_result(result: Any) -> bool:
    """Whether a `chat()` result means the expedition loop should stop.

    The runner relaunches an agent after every `chat()` return, so it needs an
    explicit stop signal rather than relying on the process dying.
    """
    if not isinstance(result, dict):
        return False
    return result.get("reason") in TERMINAL_CHAT_REASONS


__all__ = [
    "ProviderError",
    "RecoverableProviderError",
    "create_error_details",
    "log_error_to_file",
    "handle_error_with_logging",
    "is_context_overflow_error",
    "is_account_balance_error",
    "is_network_unreachable_error",
    "is_terminal_chat_result",
    "TERMINAL_CHAT_REASONS",
    "OVERFLOW_PHRASES",
]
