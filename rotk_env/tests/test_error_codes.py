"""Error-code semantics, and the observation-cache invariant that depends on them.

The bug this file pins: 2010 used to mean both "unknown verb" and "the ENV
raised". `ActionExecutor` skipped `World.bump_revision()` for 2010 on the
grounds that an unknown verb cannot have touched the board -- which silently
also skipped it when a *handler raised halfway through a mutation*, leaving the
next `get_faction_state` to answer from a stale cache.
"""

import pytest

from framework import World
from protocol.error_codes import ErrorCode, describe, is_rejected_before_dispatch
from rotk_env.systems.llm_system import ActionExecutor, ActionRequest


# ---------------------------------------------------------------- enum contract


def test_every_code_has_a_description():
    for code in ErrorCode:
        assert describe(code), f"{code!r} has no description"


def test_unknown_action_and_internal_error_are_distinct():
    """They need different agent behaviour, so they cannot share a code."""
    assert ErrorCode.UNKNOWN_ACTION != ErrorCode.INTERNAL_ERROR
    assert not ErrorCode.UNKNOWN_ACTION.retryable
    assert ErrorCode.INTERNAL_ERROR.retryable


def test_only_firewall_rejections_are_pre_dispatch():
    pre = {c for c in ErrorCode if c.rejected_before_dispatch}
    assert pre == {ErrorCode.UNKNOWN_ACTION, ErrorCode.ACTION_NOT_IN_MATCH}


def test_internal_error_is_not_treated_as_pre_dispatch():
    """The whole point of splitting 2012 out of 2010."""
    assert not ErrorCode.INTERNAL_ERROR.rejected_before_dispatch
    assert not is_rejected_before_dispatch(int(ErrorCode.INTERNAL_ERROR))


def test_is_rejected_before_dispatch_tolerates_junk():
    for junk in (None, "UNKNOWN_ERROR", 9999, object()):
        assert is_rejected_before_dispatch(junk) is False


# -------------------------------------------------- revision bump on failure


class _StubLLMSystem:
    """Minimal stand-in for LLMSystem: only what ActionExecutor touches."""

    def __init__(self, world, handler_effect):
        self.world = world
        self.system_actions = {}
        self.action_handler = _StubHandler(handler_effect)

    def _create_system_error_response(self, action, error_message, error_code):
        return {
            "success": False,
            "error": describe(error_code),
            "error_code": int(error_code),
            "message": f"Action {action} failed: {error_message}",
        }


class _StubHandler:
    def __init__(self, effect):
        self._effect = effect
        self.action_handlers = {"move": self._move}

    def execute_action(self, action, params):
        return self.action_handlers[action](params)

    def _move(self, params):
        return self._effect()


def _executor(world, effect):
    executor = ActionExecutor(_StubLLMSystem(world, effect))
    executor.world = world
    return executor


def _request(action="move"):
    return ActionRequest(
        agent_id="agent_1",
        action_id="1",
        action_name=action,
        parameters={},
        timestamp=0.0,
    )


def _run(world, effect, action="move"):
    executor = _executor(world, effect)
    before = world.revision
    result = executor.execute(_request(action))
    return result, world.revision - before


def test_raising_mutating_handler_still_bumps_revision():
    """Regression: a half-applied mutation must invalidate the observation cache.

    The exception propagates (LLMSystem turns it into an INTERNAL_ERROR reply),
    but the revision bump must already have happened on the way out.
    """
    world = World()

    def raises():
        raise RuntimeError("wrote MP, then blew up before moving the unit")

    executor = _executor(world, raises)
    before = world.revision
    with pytest.raises(RuntimeError):
        executor.execute(_request("move"))
    assert world.revision - before == 1, (
        "a handler that raised mid-mutation must still drop the observation cache"
    )


def test_raising_query_handler_does_not_bump_revision():
    """A read-only verb cannot have changed the board, even when it raises."""
    world = World()

    def raises():
        raise RuntimeError("boom")

    executor = _executor(world, raises)
    executor.llm_system.action_handler.action_handlers["get_faction_state"] = (
        lambda params: raises()
    )
    before = world.revision
    with pytest.raises(RuntimeError):
        executor.execute(_request("get_faction_state"))
    assert world.revision - before == 0


def test_internal_error_response_bumps_revision():
    world = World()

    def internal_error():
        return {
            "success": False,
            "error_code": int(ErrorCode.INTERNAL_ERROR),
            "message": "partially applied",
        }

    result, delta = _run(world, internal_error)
    assert result["error_code"] == int(ErrorCode.INTERNAL_ERROR)
    assert delta == 1, "an internal error may have mutated the board; cache must drop"


def test_unknown_action_does_not_bump_revision():
    """Refused by the firewall before dispatch, so the cache stays valid."""
    world = World()
    result, delta = _run(world, lambda: {"success": True}, action="definitely_not_a_verb")
    assert result["error_code"] == int(ErrorCode.UNKNOWN_ACTION)
    assert delta == 0


def test_successful_mutation_bumps_revision():
    world = World()
    _, delta = _run(world, lambda: {"success": True})
    assert delta == 1
