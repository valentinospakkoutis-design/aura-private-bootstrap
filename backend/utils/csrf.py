"""
CSRF Protection utilities
"""

from fastapi import HTTPException, Request, status
from typing import Optional
from cache.connection import cache_get, cache_set
import secrets


def generate_csrf_token(user_id: Optional[str] = None) -> str:
    """
    Generate CSRF token
    
    Args:
        user_id: Optional user ID for user-specific tokens
    
    Returns:
        CSRF token
    """
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, user_id: Optional[str] = None) -> bool:
    """
    Validate CSRF token
    
    Args:
        token: CSRF token to validate
        user_id: Optional user ID
    
    Returns:
        True if token is valid
    """
    if not token:
        return False
    
    cache_key = f"csrf:{user_id or 'anonymous'}:{token}"
    cached = cache_get(cache_key)
    return cached == "valid"


def require_csrf_token(request: Request):
    """
    Dependency to require CSRF token for protected endpoints
    
    Usage:
        @router.post("/endpoint")
        async def endpoint(request: Request, csrf_valid = Depends(require_csrf_token)):
            ...
    """
    # Get CSRF token from header
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "CSRF_TOKEN_MISSING", "message": "CSRF token required"}
        )
    
    # Get user ID from JWT token if available
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from auth.jwt_handler import get_user_from_token
            token = auth_header.split(" ")[1]
            user_info = get_user_from_token(token)
            user_id = user_info.get("user_id")
        except:
            pass
    
    # Validate CSRF token
    if not validate_csrf_token(csrf_token, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "CSRF_TOKEN_INVALID", "message": "Invalid CSRF token"}
        )
    
    return True

