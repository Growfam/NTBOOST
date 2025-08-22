# backend/utils/cache.py
import os

if os.getenv('FLASK_ENV') == 'development':
    class DummyCache:
        def set(self, *args, **kwargs): return True

        def get(self, *args, **kwargs): return None

        def delete(self, *args, **kwargs): return True

        def exists(self, *args, **kwargs): return False

        def connect(self): return self


    cache = DummyCache()
"""
Redis кешування для швидкодії
"""
import json
import redis
from typing import Any, Optional
import structlog

from backend.config import get_config

config = get_config()
logger = structlog.get_logger(__name__)


class RedisCache:
    """Простий Redis кеш"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    def connect(self) -> redis.Redis:
        """Підключення до Redis"""
        if not self._redis:
            try:
                self._redis = redis.from_url(config.REDIS_URL, decode_responses=True)
                # Тестуємо підключення
                self._redis.ping()
                logger.info("Connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                # Створюємо fake redis для fallback
                self._redis = FakeRedis()

        return self._redis

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Зберігає значення в кеші"""
        try:
            r = self.connect()
            json_value = json.dumps(value, ensure_ascii=False)
            ttl = ttl or config.CACHE_TTL
            r.setex(key, ttl, json_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}", error=str(e))
            return False

    def get(self, key: str) -> Any:
        """Отримує значення з кешу"""
        try:
            r = self.connect()
            value = r.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}", error=str(e))
            return None

    def delete(self, key: str) -> bool:
        """Видаляє ключ з кешу"""
        try:
            r = self.connect()
            r.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}", error=str(e))
            return False

    def exists(self, key: str) -> bool:
        """Перевіряє існування ключа"""
        try:
            r = self.connect()
            return bool(r.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}", error=str(e))
            return False


class FakeRedis:
    """Fallback кеш у пам'яті коли Redis недоступний"""

    def __init__(self):
        self._storage = {}

    def setex(self, key, ttl, value):
        self._storage[key] = value

    def get(self, key):
        return self._storage.get(key)

    def delete(self, key):
        self._storage.pop(key, None)

    def exists(self, key):
        return key in self._storage

    def ping(self):
        return True


# Глобальний інстанс кешу
cache = RedisCache()


# Зручні функції для кешування даних бота
def cache_user_stats(telegram_id: str, stats: dict, ttl: int = 300):
    """Кешує статистику користувача на 5 хвилин"""
    cache.set(f"user_stats:{telegram_id}", stats, ttl)


def get_cached_user_stats(telegram_id: str) -> Optional[dict]:
    """Отримує закешовану статистику"""
    return cache.get(f"user_stats:{telegram_id}")


def cache_packages(packages: list, ttl: int = 600):
    """Кешує список пакетів на 10 хвилин"""
    cache.set("packages", packages, ttl)


def get_cached_packages() -> Optional[list]:
    """Отримує закешовані пакети"""
    return cache.get("packages")


def invalidate_user_cache(telegram_id: str):
    """Очищає кеш користувача"""
    cache.delete(f"user_stats:{telegram_id}")


def check_redis_health() -> bool:
    """Перевірка підключення до Redis - виправлена функція"""
    try:
        # Перевіряємо підключення через наш cache об'єкт
        redis_client = cache.connect()
        redis_client.ping()

        # Тестуємо set/get операції
        test_key = 'health_check_test'
        redis_client.setex(test_key, 10, 'ok')
        result = redis_client.get(test_key)
        redis_client.delete(test_key)

        return result == 'ok'
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False