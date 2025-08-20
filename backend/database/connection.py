import asyncio
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
import structlog

from backend.config import get_config

config = get_config()
logger = structlog.get_logger(__name__)


class SupabaseConnection:
    """Клас для роботи з Supabase"""

    def __init__(self):
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None

    def connect(self) -> Client:
        """Створює підключення до Supabase"""
        if not self._client:
            self._client = create_client(
                config.SUPABASE_URL,
                config.SUPABASE_KEY
            )
            logger.info("Connected to Supabase with anon key")
        return self._client

    def connect_service(self) -> Client:
        """Створює підключення з service role (для адмін операцій)"""
        if not self._service_client:
            self._service_client = create_client(
                config.SUPABASE_URL,
                config.SUPABASE_SERVICE_KEY
            )
            logger.info("Connected to Supabase with service role")
        return self._service_client

    def execute_function(self, function_name: str, params: Dict[str, Any] = None) -> Any:
        """
        Викликає PostgreSQL функцію
        Використовуємо service role для максимальних прав
        """
        try:
            client = self.connect_service()

            if params:
                result = client.rpc(function_name, params).execute()
            else:
                result = client.rpc(function_name).execute()

            logger.debug(f"Function {function_name} executed", params=params)
            return result.data

        except Exception as e:
            logger.error(f"Error executing function {function_name}", error=str(e), params=params)
            raise

    def get_table(self, table_name: str):
        """Отримує таблицю для прямих запитів (рідко використовується)"""
        client = self.connect_service()
        return client.table(table_name)

    def health_check(self) -> bool:
        """Перевіряє підключення до БД"""
        try:
            # Простий запит для перевірки
            result = self.execute_function('get_available_packages')
            return isinstance(result, list) or isinstance(result, dict)
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Глобальний інстанс підключення
db = SupabaseConnection()


# Зручні функції для використання в коді
def get_user_stats(telegram_id: str) -> Dict[str, Any]:
    """Отримує статистику користувача"""
    result = db.execute_function('get_user_stats', {'p_telegram_id': telegram_id})
    return result if isinstance(result, dict) else {}


def get_available_packages() -> List[Dict[str, Any]]:
    """Отримує доступні пакети"""
    result = db.execute_function('get_available_packages')
    return result if isinstance(result, list) else []


def create_order(telegram_id: str, package_slug: str) -> Dict[str, Any]:
    """Створює замовлення"""
    result = db.execute_function('create_order', {
        'p_telegram_id': telegram_id,
        'p_package_slug': package_slug
    })
    return result if isinstance(result, dict) else {}


def activate_order(order_id: str) -> bool:
    """Активує замовлення після оплати"""
    result = db.execute_function('activate_order', {'p_order_id': order_id})
    return bool(result)


def add_user_post(telegram_id: str, post_url: str, platform: str = 'telegram') -> Dict[str, Any]:
    """Додає пост користувача"""
    # Спочатку отримуємо user_id
    user_stats = get_user_stats(telegram_id)
    if not user_stats.get('user_id'):
        return {'success': False, 'error': 'User not found'}

    result = db.execute_function('add_user_post_v2', {
        'p_user_id': user_stats['user_id'],
        'p_post_url': post_url,
        'p_platform': platform
    })
    return result if isinstance(result, dict) else {}


def get_pending_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    """Отримує завдання в черзі для основного бота"""
    result = db.execute_function('get_pending_tasks', {'p_limit': limit})
    return result if isinstance(result, list) else []


def update_task_status(task_id: str, status: str, external_task_id: str = None, response_data: Dict = None) -> bool:
    """Оновлює статус завдання"""
    params = {
        'p_task_id': task_id,
        'p_status': status
    }
    if external_task_id:
        params['p_external_task_id'] = external_task_id
    if response_data:
        params['p_response_data'] = response_data

    result = db.execute_function('update_task_status', params)
    return bool(result)


def get_admin_stats() -> Dict[str, Any]:
    """Отримує статистику для адмінів"""
    result = db.execute_function('get_admin_stats')
    return result if isinstance(result, dict) else {}


def create_user_if_not_exists(telegram_id: str, username: str = None, first_name: str = None,
                              last_name: str = None) -> bool:
    """Створює користувача якщо не існує"""
    try:
        # Перевіряємо чи існує
        stats = get_user_stats(telegram_id)
        if stats.get('user_id'):
            return True

        # Створюємо нового користувача через пряму вставку
        table = db.get_table('users')
        table.insert({
            'telegram_id': telegram_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        }).execute()

        logger.info(f"Created new user {telegram_id}")
        return True

    except Exception as e:
        logger.error(f"Error creating user {telegram_id}", error=str(e))
        return False


async def init_database():
    """Ініціалізація з'єднання з БД"""
    try:
        # Перевіряємо підключення
        if db.health_check():
            logger.info("Database connection successful")
            return True
        else:
            logger.error("Database health check failed")
            return False
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        return False