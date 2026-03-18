"""Utility modules for AURA."""

try:
    from .error_handler import handle_error, AuraError, ValidationError, NotFoundError, AuthenticationError
except Exception:
    handle_error = None
    AuraError = ValidationError = NotFoundError = AuthenticationError = None

try:
    from .rate_limiter import rate_limiter, get_client_identifier
except Exception:
    rate_limiter = None
    get_client_identifier = None

try:
    from .security import security_manager
except Exception:
    security_manager = None

__all__ = [
    "handle_error",
    "AuraError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "rate_limiter",
    "get_client_identifier",
    "security_manager",
]

