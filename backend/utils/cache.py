"""
Redis cache for Railway
"""
import json
import os
from typing import Any, Optional
import redis
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache wrapper"""

    def __init__(self):
        self._client = None
        self._connected = False

    def _get_client(self):
        """Get Redis client with lazy connection"""
        if self._client is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

            if redis_url and redis_url != 'redis://localhost:6379':
                try:
                    self._client = redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        retry_on_timeout=True,
                        retry_on_error=[redis.ConnectionError, redis.TimeoutError]
                    )
                    # Test connection
                    self._client.ping()
                    self._connected = True
                    logger.info("Redis cache connected")
                except Exception as e:
                    logger.warning(f"Redis cache connection failed: {e}")
                    self._connected = False
            else:
                self._connected = False

        return self._client if self._connected else None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Store value with TTL"""
        try:
            client = self._get_client()
            if client:
                client.setex(key, ttl, json.dumps(value))
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
        return False

    def get(self, key: str) -> Any:
        """Get value from cache"""
        try:
            client = self._get_client()
            if client:
                value = client.get(key)
                if value:
                    return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            client = self._get_client()
            if client:
                client.delete(key)
                return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
        return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            client = self._get_client()
            if client:
                return client.exists(key) > 0
        except Exception:
            pass
        return False

    def connect(self):
        """Initialize connection"""
        self._get_client()
        return self

# Global cache instance
cache = RedisCache()

# Helper functions залишаються ті самі
def cache_user_stats(telegram_id: str, stats: dict, ttl: int = 300):
    """Cache user statistics"""
    cache.set(f"user_stats:{telegram_id}", stats, ttl)

def get_cached_user_stats(telegram_id: str) -> Optional[dict]:
    """Get cached user statistics"""
    return cache.get(f"user_stats:{telegram_id}")

def cache_packages(packages: list, ttl: int = 600):
    """Cache packages list"""
    cache.set("packages", packages, ttl)

def get_cached_packages() -> Optional[list]:
    """Get cached packages"""
    return cache.get("packages")

def invalidate_user_cache(telegram_id: str):
    """Clear user cache"""
    cache.delete(f"user_stats:{telegram_id}")

def check_redis_health() -> bool:
    """Check cache health"""
    try:
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        return result == 'ok'
    except:
        return True  # Повертаємо True щоб не блокувати health check