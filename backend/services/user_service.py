"""
Сервіс для роботи з користувачами
"""
from typing import Dict, Any, Optional
import structlog

from backend.database.connection import (
    get_user_stats, create_user_if_not_exists
)
from backend.utils.cache import cache_user_stats, get_cached_user_stats, invalidate_user_cache

logger = structlog.get_logger(__name__)


class UserService:
    """Сервіс для роботи з користувачами"""

    @staticmethod
    async def get_or_create_user(telegram_id: str, username: str = None,
                                 first_name: str = None, last_name: str = None) -> Dict[str, Any]:
        """Отримує або створює користувача"""
        try:
            # Спочатку перевіряємо кеш
            cached_stats = get_cached_user_stats(telegram_id)
            if cached_stats:
                return cached_stats

            # Отримуємо з БД
            stats = get_user_stats(telegram_id)

            # Якщо користувача немає - створюємо
            if not stats.get('user_id'):
                success = create_user_if_not_exists(telegram_id, username, first_name, last_name)
                if success:
                    stats = get_user_stats(telegram_id)
                else:
                    return {'error': 'Failed to create user'}

            # Кешуємо результат
            if stats.get('user_id'):
                cache_user_stats(telegram_id, stats)

            return stats

        except Exception as e:
            logger.error(f"Error in get_or_create_user for {telegram_id}", error=str(e))
            return {'error': str(e)}

    @staticmethod
    async def get_user_stats_fresh(telegram_id: str) -> Dict[str, Any]:
        """Отримує актуальну статистику користувача (без кешу)"""
        try:
            stats = get_user_stats(telegram_id)
            if stats.get('user_id'):
                # Оновлюємо кеш
                cache_user_stats(telegram_id, stats)
            return stats
        except Exception as e:
            logger.error(f"Error getting fresh stats for {telegram_id}", error=str(e))
            return {'error': str(e)}

    @staticmethod
    async def invalidate_cache(telegram_id: str):
        """Очищає кеш користувача"""
        invalidate_user_cache(telegram_id)