"""
Rate limiting utilities for AURA
Protect API endpoints from abuse
"""

from fastapi import HTTPException, Request, status
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time
from cache.connection import cache_get, cache_set

# In-memory rate limit storage (fallback if Redis not available)
_rate_limit_store: Dict[str, Dict] = defaultdict(dict)


class RateLimiter:
    """
    Simple rate limiter using sliding window
    """
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
    
    def _get_key(self, identifier: str, window: str) -> str:
        """Generate cache key for rate limit"""
        return f"rate_limit:{identifier}:{window}"
    
    def _get_window_start(self, window_seconds: int) -> int:
        """Get current window start timestamp"""
        now = int(time.time())
        return (now // window_seconds) * window_seconds
    
    def check_rate_limit(
        self,
        identifier: str,
        requests_per_window: int,
        window_seconds: int = 60
    ):
        """
        Check if request is within rate limit
        
        Args:
            identifier: Unique identifier (IP, user_id, etc.)
            requests_per_window: Max requests per window
            window_seconds: Window size in seconds
        
        Returns:
            (is_allowed, remaining_requests)
        """
        window_start = self._get_window_start(window_seconds)
        key = f"{self._get_key(identifier, str(window_seconds))}:{window_start}"
        
        # Try Redis first
        cached = cache_get(key)
        if cached is not None:
            count = int(cached)
            if count >= requests_per_window:
                return False, 0
            # Increment
            cache_set(key, count + 1, expire=window_seconds)
            return True, requests_per_window - count - 1
        
        # Fallback to in-memory
        if key not in _rate_limit_store:
            _rate_limit_store[key] = {"count": 0, "expires_at": time.time() + window_seconds}
        
        store = _rate_limit_store[key]
        
        # Clean expired entries
        if time.time() > store["expires_at"]:
            store["count"] = 0
            store["expires_at"] = time.time() + window_seconds
        
        if store["count"] >= requests_per_window:
            return False, 0
        
        store["count"] += 1
        return True, requests_per_window - store["count"]
    
    def check(self, identifier: str):
        """
        Check both minute and hour rate limits
        
        Returns:
            (is_allowed, remaining_per_minute, remaining_per_hour)
        """
        allowed_min, remaining_min = self.check_rate_limit(
            identifier, self.requests_per_minute, 60
        )
        allowed_hour, remaining_hour = self.check_rate_limit(
            identifier, self.requests_per_hour, 3600
        )
        
        if not allowed_min or not allowed_hour:
            return False, remaining_min, remaining_hour
        
        return True, remaining_min, remaining_hour


# Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_minute=60,  # 60 requests per minute
    requests_per_hour=1000    # 1000 requests per hour
)


def get_client_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting (IP address)
    
    Args:
        request: FastAPI request object
    
    Returns:
        Client identifier (IP address)
    """
    # Try to get real IP (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware
    
    Usage:
        app.middleware("http")(rate_limit_middleware)
    """
    identifier = get_client_identifier(request)
    allowed, remaining_min, remaining_hour = rate_limiter.check(identifier)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT",
                "message": "Rate limit exceeded. Please try again later.",
                "remaining_per_minute": remaining_min,
                "remaining_per_hour": remaining_hour,
                "retry_after": 60
            },
            headers={
                "X-RateLimit-Limit-Minute": str(rate_limiter.requests_per_minute),
                "X-RateLimit-Remaining-Minute": str(remaining_min or 0),
                "X-RateLimit-Limit-Hour": str(rate_limiter.requests_per_hour),
                "X-RateLimit-Remaining-Hour": str(remaining_hour or 0),
                "Retry-After": "60"
            }
        )
    
    response = call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit-Minute"] = str(rate_limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_min or 0)
    response.headers["X-RateLimit-Limit-Hour"] = str(rate_limiter.requests_per_hour)
    response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour or 0)
    
    return response

