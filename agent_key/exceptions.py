"""SDK exception types."""

from __future__ import annotations


class AgentKeyError(Exception):
    """Base SDK error."""


class AgentKeyAPIError(AgentKeyError):
    """API request failed.

    Parameters
    ----------
    message : str
        Error message.
    status_code : int | None, default=None
        HTTP status code if available.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class AgentKeyAuthError(AgentKeyAPIError):
    """Authentication failed."""


class AgentKeyValidationError(AgentKeyAPIError):
    """Request payload or policy validation failed."""


class AgentKeyNotFoundError(AgentKeyAPIError):
    """Requested resource was not found."""


class AgentKeyConflictError(AgentKeyAPIError):
    """Request conflicted with current server state."""


class AgentKeyRateLimitError(AgentKeyAPIError):
    """Caller hit a rate limit."""
