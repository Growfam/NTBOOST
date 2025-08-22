"""
Основний файл Telegram бота - ВИПРАВЛЕНИЙ З ДІАГНОСТИКОЮ
"""
import asyncio
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
import threading
import traceback
import logging

from backend.config import get_config

# Використовуємо звичайний logging для діагностики
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = get_config()

# Глобальні змінні
_bot_instance: Optional[Bot] = None
_storage_instance: Optional[RedisStorage] = None
_dp_instance: Optional[Dispatcher] = None
_initialization_lock = threading.Lock()


async def create_redis_storage():
    """Створює Redis storage для FSM"""
    try:
        logger.info("Creating storage...")

        # В production на Railway використовуємо MemoryStorage якщо Redis недоступний
        if "localhost" in config.REDIS_URL and config.is_production():
            logger.info("Using MemoryStorage for production (Redis localhost detected)")
            return MemoryStorage()

        # Спробуємо підключитись до Redis
        try:
            from redis.asyncio.client import Redis

            logger.info(f"Trying Redis connection to: {config.REDIS_URL}")
            redis = Redis.from_url(
                config.REDIS_URL,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=2,
                socket_timeout=2,
                max_connections=10
            )

            # Швидкий тест
            await asyncio.wait_for(redis.ping(), timeout=1.0)
            logger.info("Redis connected successfully")

            storage = RedisStorage(redis=redis)
            return storage

        except (ImportError, ConnectionError, asyncio.TimeoutError) as e:
            logger.warning(f"Redis not available: {e}, using MemoryStorage")
            return MemoryStorage()

    except Exception as e:
        logger.error(f"Storage creation error: {e}, using MemoryStorage")
        return MemoryStorage()


async def get_bot() -> Bot:
    """Thread-safe отримання інстансу бота"""
    global _bot_instance

    if _bot_instance is None:
        with _initialization_lock:
            if _bot_instance is None:
                if not config.TELEGRAM_BOT_TOKEN:
                    raise ValueError("TELEGRAM_BOT_TOKEN is required")

                logger.info("Creating bot instance...")
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
            if _storage_instance is None:
                _storage_instance = await create_redis_storage()
                logger.info(f"Storage created: {type(_storage_instance).__name__}")

    return _storage_instance


async def get_dispatcher() -> Dispatcher:
    """Thread-safe отримання dispatcher"""
    global _dp_instance

    if _dp_instance is None:
        with _initialization_lock:
            if _dp_instance is None:
                storage = await get_storage()
                _dp_instance = Dispatcher(storage=storage)
                logger.info("Dispatcher created")

    return _dp_instance


async def register_handlers():
    """Реєструє всі handlers"""
    try:
        logger.info("Registering handlers...")

        # Отримуємо dispatcher
        dp = await get_dispatcher()

        # Імпортуємо handlers
        try:
            logger.info("Importing handler modules...")
            from backend.bot.handlers import start, packages, orders, admin
            logger.info("Handler modules imported")
        except ImportError as e:
            logger.error(f"Handler import error: {e}")
            logger.error(traceback.format_exc())
            return False

        # Реєструємо роутери
        try:
            dp.include_router(start.router)
            logger.info("✓ Start router registered")

            dp.include_router(packages.router)
            logger.info("✓ Packages router registered")

            dp.include_router(orders.router)
            logger.info("✓ Orders router registered")

            dp.include_router(admin.router)
            logger.info("✓ Admin router registered")

        except Exception as e:
            logger.error(f"Router registration error: {e}")
            return False

        logger.info("All handlers registered successfully")
        return True

    except Exception as e:
        logger.error(f"Handler registration failed: {e}")
        logger.error(traceback.format_exc())
        return False


async def init_database():
    """Ініціалізація з'єднання з БД"""
    try:
        logger.info("Initializing database...")

        from backend.database.connection import db

        # Перевіряємо підключення
        health = db.health_check()
        if health:
            logger.info("✓ Database connection successful")
            return True
        else:
            logger.error("✗ Database health check failed")
            return False

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        logger.error(traceback.format_exc())
        return False


async def setup_bot():
    """Налаштування бота"""
    try:
        logger.info("=" * 50)
        logger.info("SETUP BOT STARTED")
        logger.info("=" * 50)

        # 1. Check token
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("✗ TELEGRAM_BOT_TOKEN is missing!")
            return False
        logger.info(f"✓ Token present: {config.TELEGRAM_BOT_TOKEN[:20]}...")

        # 2. Create bot
        try:
            logger.info("Creating bot instance...")
            bot = await get_bot()
            logger.info("✓ Bot instance created")
        except Exception as e:
            logger.error(f"✗ Bot creation failed: {e}")
            return False

        # 3. Create dispatcher
        try:
            logger.info("Creating dispatcher...")
            dp = await get_dispatcher()
            logger.info("✓ Dispatcher created")
        except Exception as e:
            logger.error(f"✗ Dispatcher creation failed: {e}")
            return False

        # 4. Register handlers
        try:
            logger.info("Registering handlers...")
            handlers_ok = await register_handlers()
            if not handlers_ok:
                logger.error("✗ Handler registration failed")
                return False
            logger.info("✓ Handlers registered")
        except Exception as e:
            logger.error(f"✗ Handler registration error: {e}")
            return False

        # 5. Initialize database
        try:
            logger.info("Checking database...")
            db_ok = await init_database()
            if not db_ok:
                logger.error("✗ Database check failed")
                return False
            logger.info("✓ Database ready")
        except Exception as e:
            logger.error(f"✗ Database error: {e}")
            return False

        # 6. Configure webhook/polling
        try:
            webhook_url = config.get_webhook_url()
            if webhook_url:
                logger.info(f"Setting webhook: {webhook_url}")
                await bot.delete_webhook(drop_pending_updates=True)
                await bot.set_webhook(
                    webhook_url,
                    allowed_updates=["message", "callback_query", "inline_query"],
                    max_connections=100
                )
                logger.info("✓ Webhook configured")
            else:
                logger.info("Configuring polling mode...")
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✓ Polling mode configured")
        except Exception as e:
            logger.warning(f"Webhook/polling setup warning: {e}")
            # Продовжуємо навіть якщо webhook не вдалося налаштувати

        logger.info("=" * 50)
        logger.info("✓ BOT SETUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 50)
        return True

    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"✗ SETUP BOT FAILED: {e}")
        logger.error(traceback.format_exc())
        logger.error("=" * 50)
        return False


async def shutdown_bot():
    """Закриття бота"""
    global _bot_instance, _storage_instance, _dp_instance

    try:
        logger.info("Shutting down bot...")

        shutdown_tasks = []

        if _bot_instance:
            shutdown_tasks.append(_bot_instance.session.close())
            logger.info("Bot session closing...")

        if _storage_instance:
            shutdown_tasks.append(_storage_instance.close())
            logger.info("Storage closing...")

        if shutdown_tasks:
            await asyncio.wait_for(
                asyncio.gather(*shutdown_tasks, return_exceptions=True),
                timeout=5.0
            )

        with _initialization_lock:
            _bot_instance = None
            _storage_instance = None
            _dp_instance = None

        logger.info("Bot shutdown completed")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")
        with _initialization_lock:
            _bot_instance = None
            _storage_instance = None
            _dp_instance = None


async def create_webhook_app():
    """Створює aiohttp додаток для webhook"""
    try:
        bot = await get_bot()
        dp = await get_dispatcher()

        app = web.Application()

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)

        async def webhook_health(request):
            return web.json_response({
                'status': 'healthy',
                'service': 'telegram-webhook'
            })

        app.router.add_get('/webhook/health', webhook_health)

        logger.info("Webhook app created")
        return app

    except Exception as e:
        logger.error(f"Webhook app creation error: {e}")
        return None


# Helper functions
def is_bot_initialized() -> bool:
    """Перевіряє чи ініціалізований бот"""
    return _bot_instance is not None


def is_dispatcher_initialized() -> bool:
    """Перевіряє чи ініціалізований dispatcher"""
    return _dp_instance is not None


def get_bot_sync() -> Optional[Bot]:
    """Синхронний getter для bot instance"""
    return _bot_instance


def get_dp_sync() -> Optional[Dispatcher]:
    """Синхронний getter для dispatcher instance"""
    return _dp_instance


def get_storage_sync():
    """Синхронний getter для storage instance"""
    return _storage_instance


# Експортуємо
__all__ = [
    'get_bot', 'get_dispatcher', 'get_storage',
    'setup_bot', 'shutdown_bot', 'create_webhook_app',
    'is_bot_initialized', 'is_dispatcher_initialized',
    'get_bot_sync', 'get_dp_sync', 'get_storage_sync'
]