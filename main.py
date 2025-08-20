#!/usr/bin/env python3
"""
SocialBoost Bot - Main Entry Point
Простий інтерфейсний бот для прийому замовлень та передачі основному боту

Запуск: python main.py
"""

import os
import sys
import asyncio
import threading
import signal
from pathlib import Path
import structlog

# Додаємо backend до Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from backend.app import create_app
from backend.bot.main import setup_bot, shutdown_bot, bot, dp
from backend.config import get_config
from backend.utils.logger import setup_logging
from backend.api.webhooks import webhooks_bp
from backend.api.health import health_bp

# Налаштування логування
setup_logging()
logger = structlog.get_logger(__name__)

# Глобальні змінні для управління
flask_app = None
bot_task = None
shutdown_event = asyncio.Event()


def validate_environment():
    """Перевіряє налаштування середовища"""
    config = get_config()
    errors = config.validate()

    if errors:
        logger.error("Environment validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info("Environment validation passed")
    return True


async def run_bot():
    """Запускає Telegram бота"""
    try:
        logger.info("🤖 Starting Telegram bot...")

        # Налаштовуємо бота
        if not await setup_bot():
            logger.error("Failed to setup bot")
            return False

        # Запускаємо поллінг або webhook залежно від конфігурації
        config = get_config()

        if config.TELEGRAM_WEBHOOK_URL:
            # Webhook режим - бот буде обробляти запити через Flask
            logger.info("Bot configured for webhook mode")

            # Просто чекаємо сигналу завершення
            await shutdown_event.wait()
        else:
            # Polling режим для локальної розробки
            logger.info("Bot configured for polling mode")
            await dp.start_polling(bot)

        return True

    except Exception as e:
        logger.error(f"Error running bot: {e}")
        return False
    finally:
        await shutdown_bot()


def run_flask_app():
    """Запускає Flask додаток в окремому потоці"""
    try:
        global flask_app
        config = get_config()

        logger.info("🌐 Starting Flask server...")

        # Створюємо Flask додаток
        flask_app = create_app()

        # Реєструємо додаткові blueprints
        flask_app.register_blueprint(webhooks_bp)
        flask_app.register_blueprint(health_bp)

        # Запускаємо сервер
        flask_app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False,  # Важливо: відключаємо reloader в продакшені
            threaded=True
        )

    except Exception as e:
        logger.error(f"Error running Flask app: {e}")
        shutdown_event.set()


async def graceful_shutdown(signum=None):
    """Graceful shutdown"""
    signal_name = signal.Signals(signum).name if signum else "MANUAL"
    logger.info(f"🛑 Received shutdown signal: {signal_name}")

    try:
        # Сигналізуємо про завершення
        shutdown_event.set()

        # Зупиняємо бота
        await shutdown_bot()

        logger.info("✅ Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        # Примусове завершення
        os._exit(0)


def setup_signal_handlers():
    """Налаштовує обробники сигналів"""

    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, initiating shutdown...")
        asyncio.create_task(graceful_shutdown(signum))

    # Unix сигнали
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Головна функція"""
    try:
        logger.info("🚀 Starting SocialBoost Interface Bot...")

        # Перевіряємо налаштування
        if not validate_environment():
            logger.error("❌ Environment validation failed")
            return False

        # Налаштовуємо обробники сигналів
        setup_signal_handlers()

        config = get_config()

        # Запускаємо Flask у окремому потоці
        flask_thread = threading.Thread(
            target=run_flask_app,
            daemon=True,
            name="FlaskThread"
        )
        flask_thread.start()

        # Даємо Flask час на запуск
        await asyncio.sleep(2)

        logger.info(f"🌐 Flask server started on {config.HOST}:{config.PORT}")

        # Запускаємо бота
        await run_bot()

        return True

    except KeyboardInterrupt:
        logger.info("👋 Keyboard interrupt received")
        await graceful_shutdown()
        return True
    except Exception as e:
        logger.error(f"💥 Fatal error in main: {e}")
        return False


def sync_main():
    """Синхронна обгортка для main()"""
    try:
        # Створюємо новий event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Запускаємо головну функцію
        success = loop.run_until_complete(main())

        return 0 if success else 1

    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        return 1
    finally:
        try:
            # Закриваємо loop
            loop.close()
        except:
            pass


if __name__ == "__main__":
    # Показуємо інформацію про запуск
    print("=" * 60)
    print("🤖 SocialBoost Interface Bot")
    print("📝 Simple order collection and payment processing")
    print("🔗 Integrates with main processing bot")
    print("=" * 60)

    try:
        exit_code = sync_main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"💥 Failed to start: {e}")
        sys.exit(1)