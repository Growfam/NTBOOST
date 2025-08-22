"""
Основний файл Telegram бота - ДЕТАЛЬНЕ ЛОГУВАННЯ
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
import traceback

from backend.config import get_config
from backend.utils.logger import setup_logging

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
        logger.info("Attempting to create Redis storage...")
        logger.info(f"Redis URL: {config.REDIS_URL}")

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
            logger.info("Redis ping successful")
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
        with _initialization_lock:
            if _bot_instance is None:  # Double-check
                if not config.TELEGRAM_BOT_TOKEN:
                    raise ValueError("TELEGRAM_BOT_TOKEN is required")

                logger.info(f"Creating bot instance with token: {config.TELEGRAM_BOT_TOKEN[:20]}...")
                _bot_instance = Bot(
                    token=config.TELEGRAM_BOT_TOKEN,
                    parse_mode="HTML"
                )
                logger.info("Bot instance created successfully")

    return _bot_instance


async def get_storage():
    """Thread-safe отримання storage"""
    global _storage_instance

    if _storage_instance is None:
        with _initialization_lock:
            if _storage_instance is None:  # Double-check
                logger.info("Creating storage...")
                _storage_instance = await create_redis_storage()
                logger.info("Storage created")

    return _storage_instance


async def get_dispatcher() -> Dispatcher:
    """Thread-safe отримання dispatcher"""
    global _dp_instance

    if _dp_instance is None:
        with _initialization_lock:
            if _dp_instance is None:  # Double-check
                logger.info("Creating dispatcher...")
                storage = await get_storage()
                _dp_instance = Dispatcher(storage=storage)
                logger.info("Dispatcher created successfully")

    return _dp_instance


async def register_handlers():
    """Реєструє всі handlers"""
    try:
        logger.info("Starting handler registration...")

        # Отримуємо dispatcher
        dp = await get_dispatcher()

        # Імпортуємо handlers тут, щоб уникнути циркулярних імпортів
        logger.info("Importing handler modules...")
        try:
            from backend.bot.handlers import start, packages, orders, admin
            logger.info("Handler modules imported")
        except Exception as e:
            logger.error(f"Failed to import handlers: {e}")
            logger.error(traceback.format_exc())
            return False

        # Реєструємо роутери
        logger.info("Including routers...")
        dp.include_router(start.router)
        logger.info("Start router included")
        dp.include_router(packages.router)
        logger.info("Packages router included")
        dp.include_router(orders.router)
        logger.info("Orders router included")
        dp.include_router(admin.router)
        logger.info("Admin router included")

        logger.info("All handlers registered successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to register handlers: {e}")
        logger.error(traceback.format_exc())
        return False


async def init_database():
    """Ініціалізація з'єднання з БД"""
    try:
        logger.info("Initializing database connection...")

        from backend.database.connection import db

        # Перевіряємо підключення
        if db.health_check():
            logger.info("Database connection successful")
            return True
        else:
            logger.error("Database health check failed")
            return False
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        return False


async def setup_bot():
    """Налаштування бота"""
    try:
        logger.info("=" * 50)
        logger.info("setup_bot() started")

        # Check token first
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN is missing!")
            return False

        logger.info(f"Token present: {config.TELEGRAM_BOT_TOKEN[:20]}...")

        # Ініціалізуємо компоненти
        logger.info("Getting bot instance...")
        bot = await get_bot()
        logger.info("Bot instance created")

        logger.info("Getting dispatcher...")
        dp = await get_dispatcher()
        logger.info("Dispatcher created")

        # Реєструємо handlers
        logger.info("Registering handlers...")
        if not await register_handlers():
            logger.error("Failed to register handlers")
            return False
        logger.info("Handlers registered")

        # Ініціалізуємо базу даних
        logger.info("Initializing database...")
        if not await init_database():
            logger.error("Failed to initialize database")
            return False
        logger.info("Database initialized")

        # Налаштовуємо webhook якщо потрібно
        webhook_url = config.get_webhook_url()
        if webhook_url:
            logger.info(f"Setting webhook to: {webhook_url}")
            try:
                # Видаляємо старий webhook
                await bot.delete_webhook(drop_pending_updates=True)

                # Встановлюємо новий
                await bot.set_webhook(
                    webhook_url,
                    allowed_updates=["message", "callback_query", "inline_query"],
                    max_connections=100
                )
                logger.info(f"Webhook set successfully")
            except Exception as e:
                logger.error(f"Failed to set webhook: {e}")
                logger.error(traceback.format_exc())
                return False
        else:
            # Видаляємо webhook для polling режиму
            logger.info("Removing webhook for polling mode...")
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("Webhook removed, using polling mode")
            except Exception as e:
                logger.error(f"Error removing webhook: {e}")
                logger.error(traceback.format_exc())
                # Продовжуємо навіть якщо не вдалося видалити webhook

        logger.info("Bot setup completed successfully")
        logger.info("=" * 50)
        return True

    except Exception as e:
        logger.error(f"Error in setup_bot: {e}")
        logger.error(traceback.format_exc())
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
    'get_bot_sync', 'get_dp_sync', 'get_storage_sync'
]