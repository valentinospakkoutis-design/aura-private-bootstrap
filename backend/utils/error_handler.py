"""
Error handling utilities for AURA
User-friendly error messages and error handling
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any
import traceback
import logging

logger = logging.getLogger(__name__)


class AuraError(Exception):
    """Base exception for AURA"""
    def __init__(self, message: str, code: str = "AURA_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(AuraError):
    """Validation error"""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", status.HTTP_400_BAD_REQUEST)


class NotFoundError(AuraError):
    """Resource not found error"""
    def __init__(self, message: str):
        super().__init__(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)


class AuthenticationError(AuraError):
    """Authentication error"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR", status.HTTP_401_UNAUTHORIZED)


class RateLimitError(AuraError):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT", status.HTTP_429_TOO_MANY_REQUESTS)


def handle_error(error: Exception, include_traceback: bool = False) -> HTTPException:
    """
    Convert exception to HTTPException with user-friendly message
    
    Args:
        error: Exception to handle
        include_traceback: Whether to include traceback in response (dev only)
    
    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(error, AuraError):
        detail = {
            "error": error.code,
            "message": error.message,
            "status_code": error.status_code
        }
        if include_traceback:
            detail["traceback"] = traceback.format_exc()
        return HTTPException(status_code=error.status_code, detail=detail)
    
    # Handle HTTPException
    if isinstance(error, HTTPException):
        return error
    
    # Handle unknown errors
    logger.error(f"Unhandled error: {error}", exc_info=True)
    detail = {
        "error": "INTERNAL_ERROR",
        "message": "An internal error occurred. Please try again later.",
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
    }
    if include_traceback:
        detail["traceback"] = traceback.format_exc()
    
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail
    )


def error_response(error_code: str, message: str, status_code: int = 500) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        error_code: Error code
        message: Error message
        status_code: HTTP status code
    
    Returns:
        Dict with error details
    """
    return {
        "error": error_code,
        "message": message,
        "status_code": status_code,
        "timestamp": None  # Will be set by middleware
    }


# Greek error messages
ERROR_MESSAGES = {
    "VALIDATION_ERROR": "Τα δεδομένα που εισήγαγες δεν είναι έγκυρα",
    "NOT_FOUND": "Το αντικείμενο που αναζητάς δεν βρέθηκε",
    "AUTH_ERROR": "Σφάλμα αυθεντικοποίησης. Ελέγξτε τα διαπιστευτήριά σας",
    "RATE_LIMIT": "Έχετε υπερβεί το όριο αιτημάτων. Παρακαλώ δοκιμάστε αργότερα",
    "INTERNAL_ERROR": "Παρουσιάστηκε σφάλμα. Παρακαλώ δοκιμάστε αργότερα",
    "DATABASE_ERROR": "Σφάλμα βάσης δεδομένων. Παρακαλώ δοκιμάστε αργότερα",
    "NETWORK_ERROR": "Σφάλμα δικτύου. Ελέγξτε τη σύνδεσή σας",
    "INSUFFICIENT_FUNDS": "Ανεπαρκές υπόλοιπο",
    "INVALID_SYMBOL": "Μη έγκυρο σύμβολο",
    "MARKET_CLOSED": "Η αγορά είναι κλειστή",
}


def get_error_message(error_code: str, default: Optional[str] = None) -> str:
    """
    Get user-friendly error message in Greek
    
    Args:
        error_code: Error code
        default: Default message if code not found
    
    Returns:
        Error message in Greek
    """
    return ERROR_MESSAGES.get(error_code, default or "Άγνωστο σφάλμα")

