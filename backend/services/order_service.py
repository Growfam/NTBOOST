"""
Сервіс для роботи із замовленнями
"""
from typing import Dict, Any, List
import structlog

from backend.database.connection import (
    get_available_packages, create_order, activate_order
)
from backend.utils.cache import cache_packages, get_cached_packages

logger = structlog.get_logger(__name__)


class OrderService:
    """Сервіс для роботи із замовленнями"""

    @staticmethod
    async def get_packages() -> List[Dict[str, Any]]:
        """Отримує список доступних пакетів"""
        try:
            # Спочатку перевіряємо кеш
            cached_packages = get_cached_packages()
            if cached_packages:
                return cached_packages

            # Отримуємо з БД
            packages = get_available_packages()

            # Кешуємо на 10 хвилин
            if packages:
                cache_packages(packages, 600)

            return packages

        except Exception as e:
            logger.error("Error getting packages", error=str(e))
            return []

    @staticmethod
    async def create_new_order(telegram_id: str, package_slug: str) -> Dict[str, Any]:
        """Створює нове замовлення"""
        try:
            result = create_order(telegram_id, package_slug)

            if result.get('success'):
                logger.info(f"Order created for user {telegram_id}",
                            order_id=result.get('order_id'),
                            package_slug=package_slug)

            return result

        except Exception as e:
            logger.error(f"Error creating order for {telegram_id}",
                         error=str(e), package_slug=package_slug)
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def activate_user_order(order_id: str) -> bool:
        """Активує замовлення після успішної оплати"""
        try:
            success = activate_order(order_id)

            if success:
                logger.info(f"Order {order_id} activated successfully")
            else:
                logger.error(f"Failed to activate order {order_id}")

            return success

        except Exception as e:
            logger.error(f"Error activating order {order_id}", error=str(e))
            return False

    @staticmethod
    async def get_package_by_slug(slug: str) -> Dict[str, Any]:
        """Знаходить пакет за slug"""
        packages = await OrderService.get_packages()
        for package in packages:
            if package.get('slug') == slug:
                return package
        return {}