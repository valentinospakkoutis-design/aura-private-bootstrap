"""
Redis connection management
"""

import os
import json
from typing import Optional, Any
import redis
from redis.asyncio import Redis as AsyncRedis
import asyncio

# Redis URL from environment or default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Sync Redis client
redis_client: Optional[redis.Redis] = None

# Async Redis client
async_redis_client: Optional[AsyncRedis] = None


def get_redis() -> redis.Redis:
    """
    Get sync Redis client (singleton)
    """
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            redis_client.ping()
            print("[+] Redis connected (sync)")
        except Exception as e:
            print(f"[-] Redis connection error: {e}")
            print("[!] Continuing without Redis caching")
            redis_client = None
    return redis_client


async def get_async_redis() -> Optional[AsyncRedis]:
    """
    Get async Redis client (singleton)
    """
    global async_redis_client
    if async_redis_client is None:
        try:
            async_redis_client = await AsyncRedis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await async_redis_client.ping()
            print("[+] Redis connected (async)")
        except Exception as e:
            print(f"[-] Redis connection error: {e}")
            print("[!] Continuing without Redis caching")
            async_redis_client = None
    return async_redis_client


def cache_get(key: str, default: Any = None) -> Any:
    """
    Get value from cache
    """
    client = get_redis()
    if client is None:
        return default
    
    try:
        value = client.get(key)
        if value is None:
            return default
        # Try to parse as JSON, fallback to string
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    except Exception as e:
        print(f"[-] Cache get error: {e}")
        return default


def cache_set(key: str, value: Any, expire: int = 3600) -> bool:
    """
    Set value in cache with expiration (default 1 hour)
    """
    client = get_redis()
    if client is None:
        return False
    
    try:
        # Serialize to JSON if not string
        if not isinstance(value, str):
            value = json.dumps(value)
        client.setex(key, expire, value)
        return True
    except Exception as e:
        print(f"[-] Cache set error: {e}")
        return False


def cache_delete(key: str) -> bool:
    """
    Delete key from cache
    """
    client = get_redis()
    if client is None:
        return False
    
    try:
        client.delete(key)
        return True
    except Exception as e:
        print(f"[-] Cache delete error: {e}")
        return False


def cache_clear(pattern: str = "*") -> int:
    """
    Clear cache by pattern (default: all)
    """
    client = get_redis()
    if client is None:
        return 0
    
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        print(f"[-] Cache clear error: {e}")
        return 0


def check_redis_connection() -> bool:
    """
    Check if Redis connection is working
    """
    try:
        client = get_redis()
        if client is None:
            return False
        client.ping()
        return True
    except Exception:
        return False

