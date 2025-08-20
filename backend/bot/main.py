# backend/bot/main.py
"""
Основний файл Telegram бота - УЛЬТИМАТИВНЕ ВИПРАВЛЕННЯ
"""
import asyncio
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
import structlog
import threading

from backend.config import get_config
from backend.utils.logger import setup_logging
from backend.database.connection import init_database

config = get_config()
logger = structlog.get_logger(__name__)

# ВИПРАВЛЕНО: Глобальні змінні з proper cleanup
_bot_instance: Optional[Bot] = None
_storage_instance: Optional[RedisStorage] = None
_dp_instance: Optional[Dispatcher] = None
_initialization_lock = threading.Lock()  # Використовуємо threading.Lock для sync compatibility


async def create_redis_storage():
    """Створює Redis storage для FSM"""
    try:
        # Імпортуємо Redis для aiogram 3.x
        from redis.asyncio.client import Redis

        # Додаємо timeout та connection parameters
        redis = Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
            max_connections=10
        )

        # Тестуємо підключення з timeout
        try:
            await asyncio.wait_for(redis.ping(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("Redis ping timeout")
            raise ConnectionError("Redis connection timeout")

        # Створюємо storage
        storage = RedisStorage(redis=redis)
        logger.info("Redis storage created successfully")
        return storage

    except Exception as e:
        logger.warning(f"Failed to create Redis storage: {e}")
        logger.info("Falling back to Memory storage")
        return MemoryStorage()


async def get_bot() -> Bot:
    """Thread-safe отримання інстансу бота"""
    global _bot_instance

    if _bot_instance is None:
        # ВИПРАВЛЕНО: Не можемо використовувати asyncio.Lock в sync контексті
        with _initialization_lock:
            if _bot_instance is None:  # Double-check
                if not config.TELEGRAM_BOT_TOKEN:
                    raise ValueError("TELEGRAM_BOT_TOKEN is required")

                _bot_instance = Bot(
                    token=config.TELEGRAM_BOT_TOKEN,
                    parse_mode="HTML"
                )
                logger.info("Bot instance created")

    return _bot_instance


async def get_storage():
    """Thread-safe отримання storage"""
    global _storage_instance

    if _storage_instance is None:
        with _initialization_lock:
            if _storage_instance is None:  # Double-check
                _storage_instance = await create_redis_storage()

    return _storage_instance


async def get_dispatcher() -> Dispatcher:
    """Thread-safe отримання dispatcher"""
    global _dp_instance

    if _dp_instance is None:
        with _initialization_lock:
            if _dp_instance is None:  # Double-check
                storage = await get_storage()
                _dp_instance = Dispatcher(storage=storage)
                logger.info("Dispatcher created")

    return _dp_instance


async def register_handlers():
    """Реєструє всі handlers"""
    try:
        # Отримуємо dispatcher
        dp = await get_dispatcher()

        # Імпортуємо handlers тут, щоб уникнути циркулярних імпортів
        from backend.bot.handlers import start, packages, orders, admin

        # Реєструємо роутери
        dp.include_router(start.router)
        dp.include_router(packages.router)
        dp.include_router(orders.router)
        dp.include_router(admin.router)

        logger.info("All handlers registered successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to register handlers: {e}")
        return False


async def setup_bot():
    """Налаштування бота"""
    try:
        # Ініціалізуємо компоненти
        bot = await get_bot()
        dp = await get_dispatcher()

        # Реєструємо handlers
        if not await register_handlers():
            return False

        # Ініціалізуємо базу даних
        if not await init_database():
            logger.error("Failed to initialize database")
            return False

        # Налаштовуємо webhook якщо потрібно
        webhook_url = config.get_webhook_url()
        if webhook_url:
            try:
                # Видаляємо старий webhook
                await bot.delete_webhook(drop_pending_updates=True)

                # Встановлюємо новий
                await bot.set_webhook(
                    webhook_url,
                    allowed_updates=["message", "callback_query", "inline_query"],
                    max_connections=100
                )
                logger.info(f"Webhook set to {webhook_url}")
            except Exception as e:
                logger.error(f"Failed to set webhook: {e}")
                return False
        else:
            # Видаляємо webhook для polling режиму
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook removed, using polling mode")

        logger.info("Bot setup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error setting up bot: {e}")
        return False


async def shutdown_bot():
    """Закриття бота з proper cleanup"""
    global _bot_instance, _storage_instance, _dp_instance

    try:
        shutdown_tasks = []

        if _bot_instance:
            # Закриваємо сесію бота
            shutdown_tasks.append(_bot_instance.session.close())
            logger.info("Bot session scheduled for closure")

        if _storage_instance:
            # Закриваємо storage
            shutdown_tasks.append(_storage_instance.close())
            logger.info("Storage scheduled for closure")

        # Виконуємо всі завдання закриття з timeout
        if shutdown_tasks:
            await asyncio.wait_for(
                asyncio.gather(*shutdown_tasks, return_exceptions=True),
                timeout=10.0
            )

        # ВИПРАВЛЕНО: Очищаємо глобальні змінні
        with _initialization_lock:
            _bot_instance = None
            _storage_instance = None
            _dp_instance = None

        logger.info("Bot shutdown completed")

    except asyncio.TimeoutError:
        logger.warning("Bot shutdown timeout, forcing cleanup")
        # Форсуємо очищення
        with _initialization_lock:
            _bot_instance = None
            _storage_instance = None
            _dp_instance = None
    except Exception as e:
        logger.error(f"Error during bot shutdown: {e}")


async def create_webhook_app():
    """Створює aiohttp додаток для webhook"""
    try:
        bot = await get_bot()
        dp = await get_dispatcher()

        app = web.Application()

        # Налаштовуємо webhook handler
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)

        # Додаємо middleware для логування
        async def logging_middleware(request, handler):
            start_time = asyncio.get_event_loop().time()

            try:
                response = await handler(request)
                process_time = asyncio.get_event_loop().time() - start_time
                logger.info(
                    "Webhook request processed",
                    method=request.method,
                    path=request.path,
                    status=response.status,
                    process_time=round(process_time, 3)
                )
                return response
            except Exception as e:
                process_time = asyncio.get_event_loop().time() - start_time
                logger.error(
                    "Webhook request failed",
                    method=request.method,
                    path=request.path,
                    error=str(e),
                    process_time=round(process_time, 3)
                )
                raise

        app.middlewares.append(logging_middleware)

        # Додаємо health check для webhook app
        async def webhook_health(request):
            return web.json_response({
                'status': 'healthy',
                'service': 'telegram-webhook'
            })

        app.router.add_get('/webhook/health', webhook_health)

        logger.info("Webhook app created successfully")
        return app

    except Exception as e:
        logger.error(f"Error creating webhook app: {e}")
        return None


# ВИПРАВЛЕНО: Функції для перевірки статусу
def is_bot_initialized() -> bool:
    """Перевіряє чи ініціалізований бот"""
    return _bot_instance is not None


def is_dispatcher_initialized() -> bool:
    """Перевіряє чи ініціалізований dispatcher"""
    return _dp_instance is not None


# ВИПРАВЛЕНО: Видаляємо properties, замінюємо на звичайні функції
def get_bot_sync() -> Optional[Bot]:
    """Синхронний getter для bot instance"""
    return _bot_instance


def get_dp_sync() -> Optional[Dispatcher]:
    """Синхронний getter для dispatcher instance"""
    return _dp_instance


def get_storage_sync() -> Optional[RedisStorage]:
    """Синхронний getter для storage instance"""
    return _storage_instance


# Експортуємо для використання в main.py
__all__ = [
    'get_bot', 'get_dispatcher', 'get_storage',
    'setup_bot', 'shutdown_bot', 'create_webhook_app',
    'is_bot_initialized', 'is_dispatcher_initialized',
    'get_bot_sync', 'get_dp_sync', 'get_storage_sync'  # ВИПРАВЛЕНО: замість properties
]