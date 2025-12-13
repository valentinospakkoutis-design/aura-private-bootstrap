"""
Error handling wrapper for API endpoints
Provides consistent error handling across all endpoints
"""

from functools import wraps
from fastapi import HTTPException, status
from typing import Callable, Any
import logging
from utils.error_handler import handle_error, get_error_message

logger = logging.getLogger(__name__)


def error_handler(func: Callable) -> Callable:
    """
    Decorator for consistent error handling in API endpoints
    
    Usage:
        @router.get("/endpoint")
        @error_handler
        async def my_endpoint():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions (already handled)
            raise
        except Exception as e:
            # Log error
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            
            # Convert to HTTPException
            http_exception = handle_error(e, include_traceback=False)
            
            # Add Greek message if available
            if isinstance(http_exception.detail, dict):
                error_code = http_exception.detail.get("error", "INTERNAL_ERROR")
                greek_message = get_error_message(error_code)
                if greek_message:
                    http_exception.detail["message_el"] = greek_message
            
            raise http_exception
    
    return wrapper


def sync_error_handler(func: Callable) -> Callable:
    """
    Decorator for synchronous functions
    
    Usage:
        @sync_error_handler
        def my_function():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            http_exception = handle_error(e, include_traceback=False)
            if isinstance(http_exception.detail, dict):
                error_code = http_exception.detail.get("error", "INTERNAL_ERROR")
                greek_message = get_error_message(error_code)
                if greek_message:
                    http_exception.detail["message_el"] = greek_message
            raise http_exception
    
    return wrapper

