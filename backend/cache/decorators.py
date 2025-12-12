"""
Redis caching decorators
"""

import functools
import hashlib
import json
from typing import Callable, Any, Optional
from .connection import cache_get, cache_set, get_async_redis


def cached(expire: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching function results (sync)
    
    Args:
        expire: Cache expiration in seconds (default: 1 hour)
        key_prefix: Prefix for cache key
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(func.__name__, key_prefix, args, kwargs)
            
            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache_set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator


def cached_async(expire: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching async function results
    
    Args:
        expire: Cache expiration in seconds (default: 1 hour)
        key_prefix: Prefix for cache key
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(func.__name__, key_prefix, args, kwargs)
            
            # Try to get from cache (async)
            redis_client = await get_async_redis()
            if redis_client:
                try:
                    cached_value = await redis_client.get(cache_key)
                    if cached_value:
                        try:
                            return json.loads(cached_value)
                        except (json.JSONDecodeError, TypeError):
                            return cached_value
                except Exception:
                    pass
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache (async)
            if redis_client:
                try:
                    value = json.dumps(result) if not isinstance(result, str) else result
                    await redis_client.setex(cache_key, expire, value)
                except Exception:
                    pass
            
            return result
        return wrapper
    return decorator


def _generate_cache_key(func_name: str, prefix: str, args: tuple, kwargs: dict) -> str:
    """
    Generate cache key from function name and arguments
    """
    key_parts = [prefix, func_name] if prefix else [func_name]
    
    # Add args and kwargs to key
    key_data = {
        "args": str(args),
        "kwargs": {k: str(v) for k, v in kwargs.items()}
    }
    key_str = json.dumps(key_data, sort_keys=True)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()[:8]
    
    return f"{':'.join(key_parts)}:{key_hash}"

