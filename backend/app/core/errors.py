"""Service-layer errors.

Services raise these instead of ``HTTPException`` so they stay usable from the
WebSocket layer and from scripts, where HTTP status codes mean nothing. The API
layer owns the mapping to status codes -- see ``app/api/errors.py``.
"""


class ServiceError(Exception):
    """Base class for every expected service-layer failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    """The requested entity does not exist."""


class PermissionDeniedError(ServiceError):
    """The caller exists but may not do this."""


class ConflictError(ServiceError):
    """The request collides with existing state (duplicate username, etc.)."""


class ValidationError(ServiceError):
    """The request is well-formed but semantically invalid."""


class AuthenticationError(ServiceError):
    """Credentials are missing, wrong, or no longer valid."""
