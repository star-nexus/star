"""OpenAI-compatible `/chat/completions` transport over httpx.

Covers vLLM, DeepSeek, SiliconFlow, Infinigence, and OpenAI itself. The
`enable_thinking` switch has no standard spelling, so each family gets its own
payload key.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from ..core.console import console, console_system
from ..core.types import Message, NormalizedReply, ToolCall, ToolDefinition
from .base import ModelAdapter, ProviderError

REQUEST_TIMEOUT_SECONDS = 600.0

# Providers that reject an assistant message unless the reasoning that produced
# it comes back as `reasoning_content`. DeepSeek enforces this on every assistant
# message once a request carries `tools`, even turns with no tool call, which is
# why plain chat works and a tool-driven loop dies on its second request.
#
# An empty string satisfies the check (`--no-carry-reasoning`), but the default
# is to send the chain back verbatim: that is what the docs require, it lets
# the model continue its previous thought, and the prior output can hit the
# disk cache on the next request instead of being regenerated as output tokens.
REASONING_ROUND_TRIP_FAMILIES = ("deepseek",)

# Used only when the config leaves `base_url` empty.
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "infinigence": "https://cloud.infini-ai.com/maas/v1/chat/completions",
    "siliconflow": "https://api.siliconflow.cn/v1/chat/completions",
}


def resolve_base_url(provider: str, configured: Optional[str]) -> str:
    """An explicit `base_url` always wins; otherwise fall back by family."""
    if configured:
        return configured
    for family, url in DEFAULT_BASE_URLS.items():
        if provider.startswith(family):
            return url
    raise ValueError(
        f"Provider '{provider}' has no base_url in .configs.toml and no known default."
    )


class ChatCompletionsAdapter(ModelAdapter):
    """Single-call chat completions."""

    name = "chat_completions"

    def __init__(self, config, stats, carry_reasoning: bool = True):
        super().__init__(config, stats)
        self.client = httpx.AsyncClient()
        self.carry_reasoning = carry_reasoning
        self.base_url = resolve_base_url(config.provider, config.base_url)
        # Keep the config in sync so ENV registration reports the real endpoint.
        self.config.base_url = self.base_url

        console_system.print("=" * 39, style="yellow")
        console_system.print(self.config, style="yellow")
        console_system.print("=" * 39, style="yellow")

    def _thinking_payload(self) -> Dict[str, Any]:
        """Provider-specific spelling of the reasoning toggle."""
        enabled = bool(self.config.enable_thinking)
        provider = self.config.provider

        if provider.startswith("siliconflow"):
            return {"enable_thinking": enabled}
        if provider.startswith("vllm"):
            return {"chat_template_kwargs": {"enable_thinking": enabled}}
        if provider.startswith("deepseek"):
            # DeepSeek ignores both spellings above; this is the only one that
            # actually switches reasoning off.
            payload: Dict[str, Any] = {
                "thinking": {"type": "enabled" if enabled else "disabled"}
            }
            if enabled and self.config.reasoning_effort:
                payload["reasoning_effort"] = self.config.reasoning_effort
            return payload
        return {}

    @property
    def needs_reasoning_round_trip(self) -> bool:
        return self.config.provider.startswith(REASONING_ROUND_TRIP_FAMILIES)

    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.role == "assistant" and self.needs_reasoning_round_trip:
                entry["reasoning_content"] = (
                    msg.reasoning if self.carry_reasoning else ""
                )
            formatted.append(entry)
        return formatted

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _build_payload(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]],
        **overrides,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.config.model_id,
            "messages": self._format_messages(messages),
            "stream": False,
        }

        for key in ("temperature", "top_p", "top_k", "max_tokens"):
            value = getattr(self.config, key, None)
            if value is not None:
                payload[key] = value

        payload.update(self._thinking_payload())

        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = True

        payload.update(overrides)
        return payload

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """One HTTP round trip, with every failure mode counted."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        console.print("── LLM request payload ──", style="green")
        console.print(
            json.dumps(payload, indent=2, ensure_ascii=False),
            style="green",
            highlight=False,
        )

        self.stats.add_total_api_call_count()
        console.print(
            f"🔍 API call count: {self.stats.get_total_api_call_count()}", style="cyan"
        )

        try:
            response = await self.client.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code != 200:
                if 400 <= response.status_code < 500:
                    self.stats.add_http_4xx()
                elif 500 <= response.status_code < 600:
                    self.stats.add_http_5xx()
                else:
                    self.stats.add_http_other()

                try:
                    body = response.json()
                    message = body.get("error", {}).get("message", response.text)
                except Exception:
                    body = response.text
                    message = response.text

                console.print("🚨 LLM API error", style="red bold")
                console.print(f"Status code: {response.status_code}", style="red")
                console.print(f"URL: {response.url}", style="red")
                console.print(f"Provider: {self.config.provider}", style="red")
                console.print(f"Model: {self.config.model_id}", style="red")
                console.print(f"Body: {body}", style="red")

                raise ProviderError(
                    f"LLM API error: {response.status_code} - {message}"
                )

            body = response.json()
            self.stats.record_usage(
                body.get("usage") if isinstance(body, dict) else None
            )
            return body

        except httpx.ConnectError as e:
            self.stats.add_http_connect_error()
            msg = (
                f"Cannot connect to {self.config.provider} API server: {self.base_url}"
            )
            console.print(f"🔌 Connection error: {msg}", style="red")
            raise ProviderError(msg) from e

        except httpx.TimeoutException as e:
            self.stats.add_http_timeout()
            msg = (
                f"{self.config.provider} API request timeout "
                f"(>{REQUEST_TIMEOUT_SECONDS:.0f} seconds)"
            )
            console.print(f"⏱️ Timeout error: {msg}", style="red")
            raise ProviderError(msg) from e

        except httpx.HTTPStatusError as e:
            self.stats.add_http_other()
            msg = f"{self.config.provider} API HTTP error: {e.response.status_code}"
            console.print(f"🌐 HTTP error: {msg}", style="red")
            raise ProviderError(msg) from e

        except json.JSONDecodeError as e:
            self.stats.add_http_bad_json()
            msg = f"Failed to parse JSON response from {self.config.provider}: {e}"
            console.print(f"📋 JSON parse error: {msg}", style="red")
            raise ProviderError(msg) from e

        except ProviderError:
            raise

        except Exception as e:
            if "json" in str(e).lower():
                self.stats.add_http_bad_json()
            else:
                self.stats.add_http_other()
            msg = f"Unknown error while calling {self.config.provider}: {e}"
            console.print(f"❌ {msg}", style="red")
            console.print(f"Request URL: {self.base_url}", style="yellow")
            raise ProviderError(msg) from e

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> NormalizedReply:
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        tool_calls = [
            ToolCall(
                id=call.get("id", ""),
                name=(call.get("function") or {}).get("name", ""),
                arguments=(call.get("function") or {}).get("arguments", "") or "",
            )
            for call in (message.get("tool_calls") or [])
        ]

        return NormalizedReply(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason") or "stop",
            raw=raw,
            reasoning=message.get("reasoning_content") or "",
        )

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: str = "",
    ) -> NormalizedReply:
        """The system prompt travels as the leading system message."""
        raw = await self._post(self._build_payload(messages, tools))
        reply = self._normalize(raw)

        console.print("── LLM response ──", style="yellow")
        console.print(
            json.dumps(raw, indent=2, ensure_ascii=False), style="yellow", highlight=False
        )
        return reply

    async def close(self) -> None:
        await self.client.aclose()


__all__ = ["ChatCompletionsAdapter", "resolve_base_url", "DEFAULT_BASE_URLS"]
