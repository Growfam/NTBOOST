# backend/services/user_service.py
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


# ===================================

# backend/services/order_service.py
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
    async def get_package_by_slug(slug: str) -> Optional[Dict[str, Any]]:
        """Знаходить пакет за slug"""
        packages = await OrderService.get_packages()
        for package in packages:
            if package.get('slug') == slug:
                return package
        return None


# ===================================

# backend/services/payment_service.py
"""
Сервіс для роботи з CryptoBot платежами
"""
import requests
from typing import Dict, Any, Optional
import structlog

from backend.config import get_config
from backend.services.order_service import OrderService

config = get_config()
logger = structlog.get_logger(__name__)


class PaymentService:
    """Сервіс для роботи з CryptoBot API"""

    BASE_URL = "https://pay.crypt.bot/api"

    @staticmethod
    async def create_invoice(order_id: str, amount: float, currency: str = "USD",
                             description: str = "") -> Dict[str, Any]:
        """Створює рахунок для оплати в CryptoBot"""
        try:
            headers = {
                "Crypto-Pay-API-Token": config.CRYPTOBOT_TOKEN,
                "Content-Type": "application/json"
            }

            payload = {
                "asset": "USDT",  # Використовуємо USDT для стабільності
                "amount": str(amount),
                "description": description or f"Оплата замовлення {order_id}",
                "payload": order_id,  # Передаємо order_id як payload
                "return_url": config.TELEGRAM_WEBHOOK_URL,
                "expires_in": 3600  # 1 година на оплату
            }

            response = requests.post(
                f"{PaymentService.BASE_URL}/createInvoice",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    invoice = data.get("result", {})
                    logger.info(f"Invoice created for order {order_id}",
                                invoice_id=invoice.get("invoice_id"))
                    return {
                        "success": True,
                        "invoice_id": invoice.get("invoice_id"),
                        "pay_url": invoice.get("pay_url"),
                        "amount": invoice.get("amount"),
                        "asset": invoice.get("asset")
                    }

            logger.error(f"CryptoBot API error for order {order_id}",
                         status=response.status_code,
                         response=response.text)
            return {"success": False, "error": "Payment service error"}

        except Exception as e:
            logger.error(f"Error creating invoice for order {order_id}", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    async def verify_webhook(body: bytes, signature: str) -> bool:
        """Перевіряє підпис webhook від CryptoBot"""
        try:
            import hmac
            import hashlib

            secret = config.CRYPTOBOT_WEBHOOK_SECRET.encode()
            expected_signature = hmac.new(
                secret,
                body,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error("Error verifying webhook signature", error=str(e))
            return False

    @staticmethod
    async def process_payment_webhook(webhook_data: Dict[str, Any]) -> bool:
        """Обробляє webhook про успішну оплату"""
        try:
            update_type = webhook_data.get("update_type")

            if update_type == "invoice_paid":
                invoice = webhook_data.get("payload", {})
                order_id = invoice.get("payload")  # Наш order_id
                status = invoice.get("status")

                if status == "paid" and order_id:
                    # Активуємо замовлення
                    success = await OrderService.activate_user_order(order_id)

                    if success:
                        logger.info(f"Payment processed successfully for order {order_id}")
                        return True
                    else:
                        logger.error(f"Failed to activate order {order_id} after payment")
                        return False

            logger.warning("Unhandled webhook update type", update_type=update_type)
            return False

        except Exception as e:
            logger.error("Error processing payment webhook", error=str(e))
            return False


# ===================================

# backend/services/external_service.py
"""
Сервіс для відправки завдань основному боту
"""
import requests
from typing import Dict, Any, List
import structlog

from backend.config import get_config
from backend.database.connection import (
    add_user_post, get_pending_tasks, update_task_status
)

config = get_config()
logger = structlog.get_logger(__name__)


class ExternalService:
    """Сервіс для інтеграції з основним ботом"""

    @staticmethod
    async def add_post_for_processing(telegram_id: str, post_url: str,
                                      platform: str = "telegram") -> Dict[str, Any]:
        """Додає пост користувача та створює завдання"""
        try:
            result = add_user_post(telegram_id, post_url, platform)

            if result.get('success'):
                logger.info(f"Post added for user {telegram_id}",
                            post_id=result.get('post_id'),
                            task_id=result.get('task_id'))

                # Спробуємо відправити завдання одразу
                await ExternalService.send_pending_tasks()

            return result

        except Exception as e:
            logger.error(f"Error adding post for {telegram_id}",
                         error=str(e), post_url=post_url)
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def send_pending_tasks(limit: int = 5) -> int:
        """Відправляє завдання в черзі основному боту"""
        try:
            tasks = get_pending_tasks(limit)

            if not tasks:
                return 0

            sent_count = 0

            for task in tasks:
                success = await ExternalService._send_single_task(task)
                if success:
                    sent_count += 1

            logger.info(f"Sent {sent_count}/{len(tasks)} tasks to main bot")
            return sent_count

        except Exception as e:
            logger.error("Error sending pending tasks", error=str(e))
            return 0

    @staticmethod
    async def _send_single_task(task: Dict[str, Any]) -> bool:
        """Відправляє одне завдання основному боту"""
        try:
            task_id = task.get('task_id')

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.MAIN_BOT_API_KEY}"
            }

            payload = {
                "interface_task_id": task_id,
                "user_data": task.get('user_data'),
                "post_data": task.get('post_data'),
                "package_data": task.get('package_data')
            }

            response = requests.post(
                f"{config.MAIN_BOT_API_URL}/api/process-task",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # Оновлюємо статус завдання
                    update_task_status(
                        task_id,
                        "sent",
                        data.get("main_task_id"),
                        {"sent_at": "now", "main_bot_response": data}
                    )

                    logger.info(f"Task {task_id} sent successfully to main bot")
                    return True

            logger.error(f"Failed to send task {task_id}",
                         status=response.status_code,
                         response=response.text)
            return False

        except Exception as e:
            logger.error(f"Error sending task {task.get('task_id')}", error=str(e))
            return False

    @staticmethod
    async def check_main_bot_health() -> bool:
        """Перевіряє доступність основного бота"""
        try:
            response = requests.get(
                f"{config.MAIN_BOT_API_URL}/health",
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            logger.error("Main bot health check failed", error=str(e))
            return False