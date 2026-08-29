"""
Custom exception classes for the Star Client SDK
"""

import builtins


class AgentClientError(Exception):
    """Base exception for the SDK."""
    pass


class ConnectionError(AgentClientError):
    """Connection-related error."""
    pass


class MessageError(AgentClientError):
    """Message-processing error."""
    pass


class AuthenticationError(AgentClientError):
    """Authentication error."""
    pass


class TimeoutError(AgentClientError):
    """Timeout error."""
    pass


class ProtocolError(AgentClientError):
    """The peer answered, but with a protocol-level error rather than an outcome."""

    def __init__(self, message: str, request_id: object = None):
        super().__init__(message)
        self.request_id = request_id


class ActionTimeout(TimeoutError, builtins.TimeoutError):
    """No outcome arrived for an action within its timeout.

    Carries the request context so callers can log which action stalled without
    re-deriving it from the message text.

    Also a builtin `TimeoutError` so that callers written against the old
    hand-rolled polling loop -- which raised the builtin -- keep working.
    """

    def __init__(self, action: str, request_id: object, timeout: float):
        super().__init__(
            f"No outcome for action '{action}' (id={request_id}) within {timeout}s"
        )
        self.action = action
        self.request_id = request_id
        self.timeout_seconds = timeout
