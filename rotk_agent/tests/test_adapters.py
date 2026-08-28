"""Adapters must present both wire formats as the same NormalizedReply."""

import json
from types import SimpleNamespace

import pytest

from rotk_agent.adapters import build_adapter
from rotk_agent.adapters.chat_completions import (
    ChatCompletionsAdapter,
    resolve_base_url,
)
from rotk_agent.adapters.fake import FakeAdapter, ProbeScript
from rotk_agent.adapters.nemotron import NemotronAdapter, ensure_closed_think_block
from rotk_agent.adapters.responses import (
    ResponsesAdapter,
    clean_tool_name,
    sanitize_model_text,
)
from rotk_agent.core.types import Message, NormalizedReply
from rotk_agent.profiles import PROFILES, Profile


class TestBaseUrlResolution:
    def test_explicit_base_url_wins(self):
        assert (
            resolve_base_url("siliconflow", "http://localhost:8001/v1/chat/completions")
            == "http://localhost:8001/v1/chat/completions"
        )

    def test_falls_back_to_known_default(self):
        assert resolve_base_url("deepseek", None) == (
            "https://api.deepseek.com/chat/completions"
        )

    def test_matches_on_family_prefix(self):
        assert resolve_base_url("siliconflow_qwen3", "") == (
            "https://api.siliconflow.cn/v1/chat/completions"
        )

    def test_unknown_provider_without_base_url_is_an_error(self):
        # Better to fail at startup than to POST to an empty URL.
        with pytest.raises(ValueError, match="no known default"):
            resolve_base_url("vllm_something", None)


class TestChatCompletionsNormalization:
    def test_reads_text_and_finish_reason(self):
        reply = ChatCompletionsAdapter._normalize(
            {
                "choices": [
                    {"message": {"content": "hello"}, "finish_reason": "stop"}
                ]
            }
        )
        assert reply.text == "hello"
        assert reply.finish_reason == "stop"
        assert reply.tool_calls == []

    def test_reads_tool_calls(self):
        reply = ChatCompletionsAdapter._normalize(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "perform_action",
                                        "arguments": '{"action":"move"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        )
        assert len(reply.tool_calls) == 1
        call = reply.tool_calls[0]
        assert (call.id, call.name) == ("call_1", "perform_action")
        assert json.loads(call.arguments) == {"action": "move"}

    def test_null_content_becomes_empty_string(self):
        reply = ChatCompletionsAdapter._normalize(
            {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]}
        )
        assert reply.text == ""

    def test_empty_response_does_not_raise(self):
        reply = ChatCompletionsAdapter._normalize({})
        assert reply.text == ""
        assert reply.finish_reason == "stop"


class TestThinkingToggle:
    """Each family spells the reasoning switch differently.

    Verified against the live DeepSeek API: it ignores both `enable_thinking`
    and `chat_template_kwargs`, so only the `thinking` object actually works.
    """

    @staticmethod
    def payload(provider, enabled, effort=None):
        adapter = ChatCompletionsAdapter.__new__(ChatCompletionsAdapter)
        adapter.config = SimpleNamespace(
            provider=provider, enable_thinking=enabled, reasoning_effort=effort
        )
        return ChatCompletionsAdapter._thinking_payload(adapter)

    def test_deepseek_uses_the_thinking_object(self):
        assert self.payload("deepseek-v4-flash", False) == (
            {"thinking": {"type": "disabled"}}
        )
        assert self.payload("deepseek-v4-flash", True) == (
            {"thinking": {"type": "enabled"}}
        )

    def test_deepseek_carries_the_effort_when_thinking(self):
        assert self.payload("deepseek-v4-flash", True, "max") == {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
        }

    def test_effort_is_omitted_when_thinking_is_off(self):
        # An intensity for reasoning that will not happen is just noise.
        assert self.payload("deepseek-v4-flash", False, "max") == (
            {"thinking": {"type": "disabled"}}
        )

    def test_siliconflow_uses_a_top_level_flag(self):
        assert self.payload("siliconflow_qwen3", True) == {"enable_thinking": True}

    def test_vllm_uses_chat_template_kwargs(self):
        assert self.payload("vllm_qwen3_14b", False) == (
            {"chat_template_kwargs": {"enable_thinking": False}}
        )

    def test_an_unknown_family_sends_nothing(self):
        assert self.payload("openai", True) == {}


class TestReasoningRoundTrip:
    """DeepSeek rejects an assistant message unless reasoning_content comes back.

    Confirmed against the live API: once a request carries `tools`, the field is
    required on every assistant message. An empty string satisfies the check
    (`--no-carry-reasoning`); the default is to send the chain back verbatim.
    """

    @staticmethod
    def format(provider, messages, carry_reasoning=True):
        adapter = ChatCompletionsAdapter.__new__(ChatCompletionsAdapter)
        adapter.config = SimpleNamespace(
            provider=provider, enable_thinking=True, reasoning_effort=None
        )
        adapter.carry_reasoning = carry_reasoning
        return ChatCompletionsAdapter._format_messages(adapter, messages)

    @staticmethod
    def assistant_with_call(reasoning=""):
        return Message(
            role="assistant",
            content="checking the board",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "perform_action", "arguments": "{}"},
                }
            ],
            reasoning=reasoning,
        )

    def test_the_key_is_always_present_for_deepseek(self):
        # Once a request carries tools, DeepSeek demands the field on *every*
        # assistant message, including turns with no tool call. Omitting it is
        # a 400; an empty string is accepted.
        with_call = self.format("deepseek-v4-flash", [self.assistant_with_call()])[0]
        without_call = self.format(
            "deepseek-v4-flash", [Message(role="assistant", content="thinking")]
        )[0]
        assert with_call["reasoning_content"] == ""
        assert without_call["reasoning_content"] == ""

    def test_carrying_reasoning_sends_it_back_verbatim(self):
        entry = self.format(
            "deepseek-v4-flash",
            [self.assistant_with_call("flank then focus fire")],
        )[0]
        assert entry["reasoning_content"] == "flank then focus fire"

    def test_not_carrying_reasoning_sends_an_empty_field(self):
        # --no-carry-reasoning: honour the protocol without paying for a long
        # chain on every later request. The reasoning still reaches the rubric.
        entry = self.format(
            "deepseek-v4-flash",
            [self.assistant_with_call("a very long chain of thought")],
            carry_reasoning=False,
        )[0]
        assert entry["reasoning_content"] == ""

    def test_non_assistant_messages_never_get_the_field(self):
        entries = self.format(
            "deepseek-v4-flash",
            [
                Message(role="system", content="s"),
                Message(role="user", content="u"),
                Message(role="tool", content="{}", tool_call_id="c1"),
            ],
        )
        assert all("reasoning_content" not in e for e in entries)

    def test_other_providers_do_not_get_the_field(self):
        # Sending an unexpected message field is a needless 400 risk elsewhere.
        entry = self.format(
            "vllm_qwen3_14b", [self.assistant_with_call("hmm")], carry_reasoning=True
        )[0]
        assert "reasoning_content" not in entry

    def test_tool_results_keep_their_call_id(self):
        entry = self.format(
            "deepseek-v4-flash",
            [Message(role="tool", content="{}", tool_call_id="call_1")],
        )[0]
        assert entry["tool_call_id"] == "call_1"


class TestResponsesSanitization:
    """GPT-OSS leaks Harmony control tokens that make the next request 400."""

    def test_truncates_at_end_token(self):
        assert sanitize_model_text("plan the attack<|end|>garbage") == "plan the attack"

    def test_strips_channel_tokens(self):
        assert sanitize_model_text("<|channel|>commentary attack now") == "attack now"

    def test_caps_length(self):
        assert len(sanitize_model_text("x" * 9000, max_len=100)) == 100

    def test_leaves_clean_text_alone(self):
        assert sanitize_model_text("移动到高地然后攻击") == "移动到高地然后攻击"

    def test_cleans_tool_names(self):
        assert clean_tool_name("perform_action<|channel|>commentary") == "perform_action"
        assert clean_tool_name("perform_action") == "perform_action"


class TestResponsesInputProjection:
    """Input items are derived from the message history, not tracked separately.

    The old implementation kept a parallel `input_items` list beside the normal
    history and let the two drift apart.
    """

    @staticmethod
    def project(messages):
        return ResponsesAdapter._build_input_items(messages)

    def test_system_message_is_excluded(self):
        # It travels as `instructions` instead.
        items = self.project([Message(role="system", content="you are a commander")])
        assert items == []

    def test_tool_result_becomes_function_call_output(self):
        items = self.project(
            [Message(role="tool", content='{"ok":true}', tool_call_id="call_9")]
        )
        assert items == [
            {
                "type": "function_call_output",
                "call_id": "call_9",
                "output": '{"ok":true}',
            }
        ]

    def test_assistant_tool_calls_become_function_call_items(self):
        items = self.project(
            [
                Message(
                    role="assistant",
                    content="attacking",
                    tool_calls=[
                        {
                            "id": "call_3",
                            "function": {
                                "name": "perform_action<|channel|>",
                                "arguments": '{"action":"attack"}',
                            },
                        }
                    ],
                )
            ]
        )
        assert items[0] == {"role": "assistant", "content": "attacking"}
        assert items[1] == {
            "type": "function_call",
            "name": "perform_action",
            "call_id": "call_3",
            "arguments": '{"action":"attack"}',
        }

    def test_empty_assistant_text_is_omitted(self):
        items = self.project([Message(role="assistant", content="")])
        assert items == []

    def test_assistant_content_is_sanitized_on_the_way_in(self):
        items = self.project(
            [Message(role="assistant", content="plan<|end|>junk")]
        )
        assert items == [{"role": "assistant", "content": "plan"}]

    def test_carrying_reasoning_emits_a_reasoning_item(self):
        items = ResponsesAdapter._build_input_items(
            [Message(role="assistant", content="move", reasoning="flank first")],
            carry_reasoning=True,
        )
        assert items[0] == {
            "type": "reasoning",
            "content": [{"type": "reasoning_text", "text": "flank first"}],
        }
        assert items[1] == {"role": "assistant", "content": "move"}

    def test_not_carrying_reasoning_omits_the_item(self):
        items = ResponsesAdapter._build_input_items(
            [Message(role="assistant", content="move", reasoning="flank first")],
            carry_reasoning=False,
        )
        assert items == [{"role": "assistant", "content": "move"}]


class TestResponsesNormalization:
    @staticmethod
    def response(output, status="completed", incomplete_reason=None):
        return SimpleNamespace(
            output=output,
            status=status,
            incomplete_details=(
                SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None
            ),
        )

    def test_reads_message_text(self):
        reply = ResponsesAdapter._normalize(
            self.response(
                [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "advance"}],
                    }
                ]
            )
        )
        assert reply.text == "advance"
        assert reply.finish_reason == "stop"

    def test_reads_reasoning_separately_from_the_answer(self):
        reply = ResponsesAdapter._normalize(
            self.response(
                [
                    {
                        "type": "reasoning",
                        "content": [{"type": "reasoning_text", "text": "首先包抄"}],
                    },
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "move"}],
                    },
                ]
            )
        )
        assert reply.reasoning == "首先包抄"
        assert reply.text == "move"
        # Both feed the rubric, so reasoning is not scored away.
        assert reply.scoreable_text == "首先包抄\nmove"

    def test_function_calls_set_the_tool_calls_finish_reason(self):
        reply = ResponsesAdapter._normalize(
            self.response(
                [
                    {
                        "type": "function_call",
                        "name": "perform_action",
                        "call_id": "call_1",
                        "arguments": '{"action":"move"}',
                    }
                ]
            )
        )
        assert reply.finish_reason == "tool_calls"
        assert reply.tool_calls[0].name == "perform_action"

    def test_missing_arguments_default_to_empty_object(self):
        reply = ResponsesAdapter._normalize(
            self.response(
                [{"type": "function_call", "name": "end_turn", "call_id": "c"}]
            )
        )
        assert reply.tool_calls[0].arguments == "{}"

    def test_token_limit_maps_to_length(self):
        reply = ResponsesAdapter._normalize(
            self.response([], status="incomplete", incomplete_reason="max_output_tokens")
        )
        assert reply.finish_reason == "length"

    def test_content_filter_maps_across(self):
        reply = ResponsesAdapter._normalize(
            self.response([], status="incomplete", incomplete_reason="content_filter")
        )
        assert reply.finish_reason == "content_filter"


class TestNemotronThinkBlock:
    def test_closes_an_unterminated_block(self):
        assert ensure_closed_think_block("weighing options").endswith("</think>\n\n")

    def test_leaves_a_closed_block_alone(self):
        text = "reasoning</think>\n\n"
        assert ensure_closed_think_block(text) == text

    def test_empty_reasoning_still_produces_a_valid_block(self):
        assert ensure_closed_think_block("") == "</think>\n\n"


class TestNemotronThinkingSwitch:
    @pytest.mark.asyncio
    async def test_thinking_off_uses_a_single_parent_call(self, config, stats, monkeypatch):
        config.enable_thinking = False
        adapter = NemotronAdapter(config, stats)

        async def no_post(*_args, **_kwargs):
            raise AssertionError("stage-1 thinking must not run when thinking is off")

        async def parent_complete(self, messages, tools=None, instructions=""):
            return NormalizedReply(text="answer", finish_reason="stop")

        adapter._post = no_post
        monkeypatch.setattr(ChatCompletionsAdapter, "complete", parent_complete)

        reply = await adapter.complete([])
        assert reply.text == "answer"


class TestAdapterFactory:
    def test_unknown_adapter_is_rejected(self, config, stats):
        with pytest.raises(ValueError, match="Unknown adapter"):
            build_adapter(Profile(name="x", adapter="nope"), config, stats)

    def test_profile_rows_construct_the_named_transport(self, config, stats):
        mapping = {
            "qwen3": ChatCompletionsAdapter,
            "gpt_oss": ResponsesAdapter,
            "nemotron": NemotronAdapter,
            "fake": FakeAdapter,
        }
        for name, expected in mapping.items():
            adapter = build_adapter(PROFILES[name], config, stats)
            assert isinstance(adapter, expected)

    def test_carry_reasoning_reaches_the_responses_adapter(self, config, stats):
        adapter = build_adapter(
            PROFILES["gpt_oss"], config, stats, carry_reasoning=False
        )
        assert adapter.carry_reasoning is False


class TestProbeScript:
    def test_reads_compact_unit_rows(self):
        script = ProbeScript(faction="wei")
        messages = [
            Message(
                role="tool",
                content=(
                    '{"units":[[227,"infantry",1,3,100,100,2,4,1,10,2,10,'
                    '[[-3,2]],[]]]}'
                ),
            )
        ]
        assert script._first_unit_id(messages) == 227

    def test_still_reads_dict_unit_rows(self):
        script = ProbeScript(faction="wei")
        messages = [
            Message(role="tool", content='{"units":[{"unit_id": 9}]}')
        ]
        assert script._first_unit_id(messages) == 9
