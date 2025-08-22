"""
Simple in-memory cache for Railway
"""
import json
from typing import Any, Optional
from datetime import datetime, timedelta


class SimpleCache:
    """In-memory cache"""

    def __init__(self):
        self._storage = {}
        self._expiry = {}

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Store value with TTL"""
        try:
            self._storage[key] = json.dumps(value)
            self._expiry[key] = datetime.now() + timedelta(seconds=ttl)
            return True
        except:
            return False

    def get(self, key: str) -> Any:
        """Get value if not expired"""
        try:
            if key in self._expiry:
                if datetime.now() < self._expiry[key]:
                    return json.loads(self._storage[key])
                else:
                    # Expired, clean up
                    del self._storage[key]
                    del self._expiry[key]
            return None
        except:
            return None

    def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            if key in self._storage:
                del self._storage[key]
            if key in self._expiry:
                del self._expiry[key]
            return True
        except:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists and not expired"""
        return self.get(key) is not None

    def connect(self):
        return self


# Global cache instance
cache = SimpleCache()


# Helper functions
def cache_user_stats(telegram_id: str, stats: dict, ttl: int = 300):
    cache.set(f"user_stats:{telegram_id}", stats, ttl)


def get_cached_user_stats(telegram_id: str) -> Optional[dict]:
    return cache.get(f"user_stats:{telegram_id}")


def invalidate_user_cache(telegram_id: str):
    cache.delete(f"user_stats:{telegram_id}")


def check_redis_health() -> bool:
    return True  # Always healthy for in-memory