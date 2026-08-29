"""The ENV must echo back the request id it was given, unchanged.

The id is the only correlation key. If the ENV replies with a different one, the
agent waits forever and reports a timeout for an action that actually ran.

The bug pinned here: `payload.get("id") or <generated>` treats `0` and `""` as
absent, so an agent numbering its requests from zero silently lost every reply.
`0` is a legal id per `protocol/schemas/payloads.schema.json`.
"""

import pytest

from rotk_env.systems.llm_system import _inbound_id


class TestInboundId:
    @pytest.mark.parametrize("raw", [0, "0", 1, "abc", "42-7", -1, "", "  "])
    def test_present_ids_are_returned_unchanged(self, raw):
        assert _inbound_id(raw) == raw

    def test_zero_is_not_treated_as_absent(self):
        """The specific regression."""
        assert _inbound_id(0) == 0

    def test_empty_string_is_not_treated_as_absent(self):
        assert _inbound_id("") == ""

    def test_absent_id_gets_a_generated_one(self):
        generated = _inbound_id(None)
        assert generated is not None
        assert generated != _inbound_id(None), "generated ids must differ"

    def test_absent_id_uses_the_supplied_fallback(self):
        assert _inbound_id(None, fallback="batch-1_0") == "batch-1_0"

    def test_present_id_beats_the_fallback(self):
        assert _inbound_id(0, fallback="batch-1_0") == 0


class TestEchoThroughTheEnv:
    """End-to-end: the id the ENV replies with must be the id it received."""

    @pytest.mark.parametrize("request_id", [0, "0", 7, "toolcall_abc", ""])
    def test_exec_action_echoes_the_request_id(self, request_id):
        from rotk_env.systems.llm_system import LLMSystem
        from framework import World

        system = LLMSystem()
        world = World()
        system.initialize(world)

        replies = []
        system.client.response_to_agent = lambda aid, action_id, result, kind: replies.append(
            action_id
        )

        system.exec_action(
            {
                "sender": {"type": "agent", "id": "agent_1"},
                "payload": {
                    "type": "action",
                    "id": request_id,
                    "action": "definitely_not_a_verb",
                    "parameters": {},
                },
            }
        )

        assert replies == [request_id], (
            f"ENV replied with {replies!r} for a request sent as {request_id!r}; "
            "the agent could never correlate that"
        )
