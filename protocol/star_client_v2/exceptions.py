"""
Custom exception classes for the Star Client SDK
"""


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
