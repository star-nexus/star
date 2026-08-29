"""Agent-facing error codes — the single source of truth.

These codes are part of the wire contract, so they live in `protocol/` rather
than in the ENV: agents branch on them (`retryable`) and `docs/agent-protocol.md`
documents them. ENV builds its human-readable table from `DESCRIPTIONS` instead
of maintaining a parallel dict that can drift.

`INTERNAL_ERROR` (2012) exists because 2010 used to mean both "you called a verb
that does not exist" and "the ENV raised". Those need different agent behaviour
(rename the verb vs. retry) and, more importantly, different ENV behaviour: an
unknown verb is rejected before dispatch and cannot have touched the board,
while a raising handler may have written half its mutation. See
`rejected_before_dispatch`.
"""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """System-level error codes returned in an `outcome` payload."""

    GAME_NOT_INITIALIZED = 2001
    GAME_ALREADY_FINISHED = 2002
    ACTION_NOT_IN_MATCH = 2003
    INSUFFICIENT_RESOURCES = 2004
    INSUFFICIENT_PERMISSIONS = 2005
    OPERATION_TIMED_OUT = 2006
    PARAMETER_VALIDATION_FAILED = 2007
    INVALID_SYSTEM_STATE = 2008
    NETWORK_ERROR = 2009
    UNKNOWN_ACTION = 2010
    RATE_LIMITED = 2011
    INTERNAL_ERROR = 2012

    @property
    def description(self) -> str:
        return DESCRIPTIONS[self]

    @property
    def retryable(self) -> bool:
        """Whether an agent should retry the same request unchanged.

        Everything else is a permanent rejection: retrying without changing the
        request gets the same answer and only burns turns.
        """
        return self in _RETRYABLE

    @property
    def rejected_before_dispatch(self) -> bool:
        """True when the action never reached a handler, so the board is intact.

        Only these codes may skip `World.bump_revision()` for a mutating verb.
        `INTERNAL_ERROR` deliberately is not here: a handler that raised
        mid-execution may already have written components, and skipping the
        revision bump would serve a stale observation afterwards.
        """
        return self in _REJECTED_BEFORE_DISPATCH


DESCRIPTIONS: dict[ErrorCode, str] = {
    ErrorCode.GAME_NOT_INITIALIZED: "Game not initialized",
    ErrorCode.GAME_ALREADY_FINISHED: "Game already finished",
    ErrorCode.ACTION_NOT_IN_MATCH: "Operation not supported in current game mode",
    ErrorCode.INSUFFICIENT_RESOURCES: "Insufficient system resources",
    ErrorCode.INSUFFICIENT_PERMISSIONS: "Insufficient permissions",
    ErrorCode.OPERATION_TIMED_OUT: "Operation timed out",
    ErrorCode.PARAMETER_VALIDATION_FAILED: "Parameter validation failed",
    ErrorCode.INVALID_SYSTEM_STATE: "Invalid system state",
    ErrorCode.NETWORK_ERROR: "Network connection error",
    ErrorCode.UNKNOWN_ACTION: "Unknown action",
    ErrorCode.RATE_LIMITED: "Operation rate limit exceeded",
    ErrorCode.INTERNAL_ERROR: "Internal service error",
}

_RETRYABLE = frozenset(
    {
        ErrorCode.RATE_LIMITED,
        ErrorCode.INTERNAL_ERROR,
        ErrorCode.OPERATION_TIMED_OUT,
        ErrorCode.NETWORK_ERROR,
    }
)

# Rejected by the action firewall, before any handler runs.
_REJECTED_BEFORE_DISPATCH = frozenset(
    {
        ErrorCode.UNKNOWN_ACTION,
        ErrorCode.ACTION_NOT_IN_MATCH,
    }
)


def describe(code: int) -> str:
    """Description for a raw int code, tolerant of unknown values."""
    try:
        return ErrorCode(code).description
    except ValueError:
        return "Unknown system error"


def is_rejected_before_dispatch(code: object) -> bool:
    """Whether a raw `error_code` value means the board was never touched."""
    try:
        return ErrorCode(code).rejected_before_dispatch  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return False


__all__ = [
    "ErrorCode",
    "DESCRIPTIONS",
    "describe",
    "is_rejected_before_dispatch",
]
