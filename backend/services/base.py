"""
Base exceptions and utilities for AMAP business services.
"""


class ServiceError(Exception):
    """Base exception for service-layer business errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""
    pass


class ConflictError(ServiceError):
    """Raised when a requested operation conflicts with existing resource state."""
    pass


class ValidationError(ServiceError):
    """Raised when domain business validation fails."""
    pass


class SafetyViolationError(ServiceError):
    """Raised when an action violates safety gates or action prerequisites."""
    pass


class UnauthorizedError(ServiceError):
    """Raised when tenant context or resource ownership verification fails."""
    pass
