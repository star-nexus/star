"""OpenAI Responses API transport.

The Responses API differs from chat completions in three ways that matter here:
the system prompt is a separate `instructions` argument rather than a message,
tool traffic is expressed as `function_call` / `function_call_output` items
instead of an assistant `tool_calls` array, and models in the GPT-OSS family
leak Harmony control tokens (`<|channel|>`, `<|end|>`) into their output. Those
tokens make the next request fail with a 400, so they are stripped on the way
back in.

The old implementation kept a second, parallel `input_items` history alongside
the normal message history and let them drift. Here `input_items` is derived
from the message history on every call, so there is one source of truth.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
)

from ..core.config import DEFAULT_REASONING_EFFORT
from ..core.console import console, console_system
from ..core.types import Message, NormalizedReply, ToolCall, ToolDefinition
from .base import ModelAdapter, ProviderError, RecoverableProviderError

MAX_ASSISTANT_CONTENT = 8000

# Harmony control tokens. The first two also mark the point past which the rest
# of the message is malformed, so content is truncated there.
TRUNCATE_AT_TOKENS = ("<|end|>", "<|start|>")
STRIP_TOKENS = ("<|channel|>commentary", "<|channel|>", "<|end|>", "<|start|>")


def sanitize_model_text(text: str, max_len: int = MAX_ASSISTANT_CONTENT) -> str:
    """Remove Harmony control tokens and cap length."""
    if not text or not isinstance(text, str):
        return text

    cleaned = text
    for sep in TRUNCATE_AT_TOKENS:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    for token in STRIP_TOKENS:
        cleaned = cleaned.replace(token, "")

    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned


def clean_tool_name(name: str) -> str:
    """Drop a trailing control token from a tool name, e.g. `foo<|channel|>`."""
    return name.split("<|", 1)[0].strip() if name else name


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or a pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ResponsesAdapter(ModelAdapter):
    """OpenAI Responses API, including vLLM servers that emulate it."""

    name = "responses"

    # GPT-OSS models copy bare JSON booleans out of tool results into their next
    # tool arguments, which the ENV then rejects.
    booleans_as_strings = True

    def __init__(self, config, stats, carry_reasoning: bool = True):
        super().__init__(config, stats)
        self.carry_reasoning = carry_reasoning
        self.client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        # "none" is how this API spells thinking-off, so the on/off switch and
        # the intensity knob collapse into one value here.
        self.reasoning_effort = (
            (config.reasoning_effort or DEFAULT_REASONING_EFFORT)
            if config.enable_thinking
            else "none"
        )

        console_system.print("=" * 39, style="yellow")
        console_system.print(self.config, style="yellow")
        console_system.print(
            f"reasoning_effort: {self.reasoning_effort}", style="yellow"
        )
        console_system.print("=" * 39, style="yellow")

    def _format_tools(self, tools: Optional[List[ToolDefinition]]) -> List[Dict[str, Any]]:
        formatted = []
        for tool in tools or []:
            item: Dict[str, Any] = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            # Strict mode requires a closed object schema with explicit requireds.
            params = tool.parameters or {}
            if (
                params.get("type") == "object"
                and params.get("additionalProperties") is False
                and isinstance(params.get("required"), list)
            ):
                item["strict"] = True
            formatted.append(item)
        return formatted

    @staticmethod
    def _build_input_items(
        messages: List[Message], carry_reasoning: bool = True
    ) -> List[Dict[str, Any]]:
        """Project the message history onto Responses API input items."""
        items: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                continue  # carried by `instructions`

            if msg.role == "tool":
                output = msg.content
                if not isinstance(output, str):
                    output = json.dumps(output, ensure_ascii=False)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id,
                        "output": output,
                    }
                )
                continue

            if msg.role == "assistant":
                if carry_reasoning and msg.reasoning:
                    items.append(
                        {
                            "type": "reasoning",
                            "content": [
                                {"type": "reasoning_text", "text": msg.reasoning}
                            ],
                        }
                    )
                text = sanitize_model_text(msg.content or "")
                if text:
                    items.append({"role": "assistant", "content": text})
                for call in msg.tool_calls or []:
                    function = call.get("function") or {}
                    arguments = function.get("arguments") or "{}"
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments, ensure_ascii=False)
                    items.append(
                        {
                            "type": "function_call",
                            "name": clean_tool_name(function.get("name", "")),
                            "call_id": call.get("id"),
                            "arguments": arguments,
                        }
                    )
                continue

            items.append({"role": msg.role, "content": msg.content})

        return items

    @staticmethod
    def _normalize(response: Any) -> NormalizedReply:
        reasoning_parts: List[str] = []
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for item in _attr(response, "output", []) or []:
            item_type = _attr(item, "type")

            if item_type == "reasoning":
                for chunk in _attr(item, "content", []) or []:
                    if _attr(chunk, "type") == "reasoning_text":
                        reasoning_parts.append(_attr(chunk, "text", "") or "")

            elif item_type in ("message", "output_text"):
                for chunk in _attr(item, "content", []) or []:
                    if item_type == "output_text" or _attr(chunk, "type") == "output_text":
                        text_parts.append(_attr(chunk, "text", "") or "")

            elif item_type == "function_call":
                arguments = _attr(item, "arguments")
                if arguments is None:
                    arguments = "{}"
                elif not isinstance(arguments, str):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                tool_calls.append(
                    ToolCall(
                        id=_attr(item, "call_id", "") or "",
                        name=clean_tool_name(_attr(item, "name", "") or ""),
                        arguments=arguments,
                    )
                )

        # `status` is "completed" | "incomplete" | "failed"; the reason for an
        # incomplete response is what maps onto a chat-completions finish reason.
        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        if _attr(response, "status") == "incomplete":
            reason = _attr(_attr(response, "incomplete_details"), "reason")
            if reason == "max_output_tokens":
                finish_reason = "length"
            elif reason == "content_filter":
                finish_reason = "content_filter"

        return NormalizedReply(
            text=sanitize_model_text("".join(text_parts).strip()),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw=response,
            reasoning="\n".join(p for p in reasoning_parts if p).strip(),
        )

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: str = "",
    ) -> NormalizedReply:
        input_items = self._build_input_items(
            messages, carry_reasoning=self.carry_reasoning
        )

        self.stats.add_total_api_call_count()
        console.print(
            f"🔍 API call count: {self.stats.get_total_api_call_count()}", style="cyan"
        )

        try:
            create_kwargs: Dict[str, Any] = {
                "model": self.config.model_id,
                "input": input_items,
                "tools": self._format_tools(tools),
                "instructions": instructions,
                "stream": False,
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "reasoning": (
                    {"effort": self.reasoning_effort}
                    if self.reasoning_effort != "none"
                    else None
                ),
            }
            if self.config.max_tokens:
                create_kwargs["max_output_tokens"] = self.config.max_tokens

            response = await self.client.responses.create(**create_kwargs)

            console.print("── LLM response ──", style="magenta")
            console.print(
                json.dumps(response.model_dump(), indent=2, ensure_ascii=False),
                style="yellow",
                highlight=False,
                markup=False,
            )

            self.stats.record_usage(getattr(response, "usage", None))
            return self._normalize(response)

        except APIConnectionError as e:
            self.stats.add_http_connect_error()
            msg = (
                f"Cannot connect to {self.config.provider} API server: "
                f"{self.config.base_url}"
            )
            console.print(f"🔌 Connection error: {msg}", style="red")
            raise ProviderError(msg) from e

        except APITimeoutError as e:
            self.stats.add_http_timeout()
            msg = f"{self.config.provider} API request timeout"
            console.print(f"⏱️ Timeout error: {msg}", style="red")
            raise ProviderError(msg) from e

        except BadRequestError as e:
            # Usually a leaked control token or an over-long history; a trimmed,
            # sanitized retry can succeed.
            self.stats.add_http_4xx()
            msg = f"{self.config.provider} API rejected the request: {e}"
            console.print(f"🔄 Bad request: {msg}", style="yellow")
            raise RecoverableProviderError(msg) from e

        except APIStatusError as e:
            status = getattr(e, "status_code", None)
            if status is not None and 400 <= status < 500:
                self.stats.add_http_4xx()
            elif status is not None and 500 <= status < 600:
                self.stats.add_http_5xx()
            else:
                self.stats.add_http_other()
            msg = f"{self.config.provider} API HTTP error: {status}"
            console.print(f"🌐 HTTP error: {msg}", style="red")
            raise ProviderError(msg) from e

        except json.JSONDecodeError as e:
            self.stats.add_http_bad_json()
            msg = f"Failed to parse JSON response from {self.config.provider}: {e}"
            console.print(f"📋 JSON parse error: {msg}", style="red")
            raise ProviderError(msg) from e

        except Exception as e:
            if "json" in str(e).lower():
                self.stats.add_http_bad_json()
            else:
                self.stats.add_http_other()
            msg = f"Unknown error while calling {self.config.provider}: {e}"
            console.print(f"❌ {msg}", style="red")
            raise ProviderError(msg) from e

    async def close(self) -> None:
        await self.client.close()


__all__ = ["ResponsesAdapter", "sanitize_model_text", "clean_tool_name"]
