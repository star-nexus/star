"""Error classifiers decide whether the loop trims, stops, or dies."""

from rotk_agent.core.errors import (
    is_context_overflow_error,
    is_terminal_chat_result,
)


class TestContextOverflow:
    def test_real_overflow_messages_match(self):
        assert is_context_overflow_error(
            RuntimeError(
                "This model's maximum context length is 8192 tokens. "
                "However, you requested 20000 tokens"
            )
        )
        assert is_context_overflow_error(RuntimeError("prompt is too long"))
        assert is_context_overflow_error(
            RuntimeError("context_length_exceeded: reduce the length of the messages")
        )

    def test_rate_limit_is_not_overflow(self):
        # The old classifier treated any mention of "tokens" or "requested"
        # as overflow, so a 429 was trimmed-and-retried until the budget died.
        assert not is_context_overflow_error(
            RuntimeError(
                "Rate limit reached for tokens per min. Limit: 10000, Requested: 8000"
            )
        )

    def test_traceback_mentioning_tokens_is_ignored(self):
        details = {
            "exception_message": "LLM API error: 400 - invalid request",
            "full_traceback": (
                'File "chat_completions.py", line 134, in _build_payload\n'
                "    payload['max_tokens'] = value\n"
            ),
        }
        assert not is_context_overflow_error(RuntimeError("invalid request"), details)

    def test_response_json_token_alone_is_not_enough(self):
        details = {
            "response_json": {"error": {"message": "You have exceeded your token quota"}}
        }
        assert not is_context_overflow_error(RuntimeError("quota"), details)


class TestTerminalChatResult:
    def test_game_ended_and_balance_and_unreachable_stop_the_runner(self):
        assert is_terminal_chat_result({"reason": "game_ended"})
        assert is_terminal_chat_result({"reason": "account_balance_insufficient"})
        assert is_terminal_chat_result({"reason": "llm_unreachable"})

    def test_content_filter_and_max_iterations_do_not(self):
        # Those relaunch; only an unreachable LLM must not.
        assert not is_terminal_chat_result({"reason": "content_filter"})
        assert not is_terminal_chat_result({"success": False, "error": "Max iterations"})
        assert not is_terminal_chat_result("not a dict")
