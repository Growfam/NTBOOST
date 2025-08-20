#!/usr/bin/env python3
"""
SocialBoost Bot - Main Entry Point - УЛЬТИМАТИВНЕ ВИПРАВЛЕННЯ
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
import time

# Додаємо backend до Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from backend.config import get_config
from backend.utils.logger import setup_logging

# Налаштування логування
setup_logging()
logger = structlog.get_logger(__name__)

# Глобальні змінні для управління
flask_app = None
flask_thread = None
bot_task = None
shutdown_event = None
main_loop = None


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

        # ВИПРАВЛЕНО: Lazy import з proper error handling
        try:
            from backend.bot.main import setup_bot, shutdown_bot, get_bot, get_dispatcher
        except ImportError as e:
            logger.error(f"Failed to import bot modules: {e}")
            return False

        # Налаштовуємо бота
        if not await setup_bot():
            logger.error("Failed to setup bot")
            return False

        config = get_config()

        if config.TELEGRAM_WEBHOOK_URL:
            # Webhook режим - бот буде обробляти запити через Flask
            logger.info("Bot configured for webhook mode")

            # Просто чекаємо сигналу завершення
            while not shutdown_event.is_set():
                await asyncio.sleep(1)
        else:
            # Polling режим для локальної розробки
            logger.info("Bot configured for polling mode")

            try:
                bot = await get_bot()
                dp = await get_dispatcher()

                # Запускаємо поллінг з graceful shutdown
                await dp.start_polling(bot, handle_signals=False)
            except asyncio.CancelledError:
                logger.info("Bot polling cancelled")

        return True

    except Exception as e:
        logger.error(f"Error running bot: {e}")
        return False
    finally:
        # ВИПРАВЛЕНО: Безпечний cleanup
        try:
            from backend.bot.main import shutdown_bot
            await shutdown_bot()
        except (ImportError, Exception) as e:
            logger.warning(f"Could not perform bot shutdown: {e}")


def run_flask_app():
    """Запускає Flask додаток в окремому потоці"""
    try:
        global flask_app
        config = get_config()

        logger.info("🌐 Starting Flask server...")

        # ВИПРАВЛЕНО: Lazy import з error handling
        try:
            from backend.app import create_app
            from backend.api.webhooks import webhooks_bp
            from backend.api.health import health_bp
        except ImportError as e:
            logger.error(f"Failed to import Flask modules: {e}")
            if shutdown_event:
                shutdown_event.set()
            return

        # Створюємо Flask додаток
        flask_app = create_app()

        # Реєструємо додаткові blueprints
        flask_app.register_blueprint(webhooks_bp)
        flask_app.register_blueprint(health_bp)

        # ВИПРАВЛЕНО: Додаємо cleanup handler для Flask
        import atexit

        def cleanup_flask():
            try:
                from backend.app import cleanup_thread_pool
                cleanup_thread_pool()
                logger.info("Flask cleanup completed")
            except Exception as e:
                logger.error(f"Flask cleanup error: {e}")

        atexit.register(cleanup_flask)

        # Запускаємо сервер
        flask_app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False,  # Важливо: відключаємо reloader
            threaded=True
        )

    except Exception as e:
        logger.error(f"Error running Flask app: {e}")
        if shutdown_event:
            shutdown_event.set()


async def graceful_shutdown():
    """Graceful shutdown з improved error handling"""
    logger.info("🛑 Initiating graceful shutdown...")

    try:
        shutdown_tasks = []

        # Сигналізуємо про завершення
        if shutdown_event:
            shutdown_event.set()

        # ВИПРАВЛЕНО: Безпечний імпорт для shutdown
        try:
            from backend.bot.main import shutdown_bot
            shutdown_tasks.append(shutdown_bot())
        except ImportError:
            logger.warning("Could not import shutdown_bot for cleanup")
        except Exception as e:
            logger.error(f"Error importing bot shutdown: {e}")

        # Очищаємо Flask app
        if flask_app:
            try:
                from backend.app import cleanup_thread_pool
                cleanup_thread_pool()
            except Exception as e:
                logger.error(f"Flask cleanup error: {e}")

        # Виконуємо всі завдання з timeout
        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Shutdown tasks timeout")

        logger.info("✅ Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        # Примусове завершення через кілька секунд
        await asyncio.sleep(1)
        os._exit(0)


def setup_signal_handlers(loop):
    """Налаштовує обробники сигналів з improved error handling"""

    def signal_handler(signum, frame):
        try:
            signal_name = signal.Signals(signum).name if signum else "MANUAL"
            logger.info(f"Signal {signal_name} received, initiating shutdown...")

            # ВИПРАВЛЕНО: Перевіряємо чи loop активний і доступний
            if loop and not loop.is_closed():
                try:
                    # Використовуємо call_soon_threadsafe для безпечного виклику
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(graceful_shutdown())
                    )
                except Exception as e:
                    logger.error(f"Failed to schedule shutdown: {e}")
                    os._exit(1)
            else:
                # Якщо loop недоступний, робимо швидке завершення
                logger.warning("Event loop not available, forcing exit")
                os._exit(1)
        except Exception as e:
            logger.error(f"Signal handler error: {e}")
            os._exit(1)

    # Unix сигнали
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Головна функція з improved error handling"""
    global shutdown_event, main_loop, flask_thread

    try:
        logger.info("🚀 Starting SocialBoost Interface Bot...")

        # Перевіряємо налаштування
        if not validate_environment():
            logger.error("❌ Environment validation failed")
            return False

        # Зберігаємо посилання на main loop
        main_loop = asyncio.get_running_loop()

        # Створюємо event для shutdown
        shutdown_event = asyncio.Event()

        # Налаштовуємо обробники сигналів
        setup_signal_handlers(main_loop)

        config = get_config()

        # ВИПРАВЛЕНО: Запускаємо Flask у окремому потоці з error handling
        try:
            flask_thread = threading.Thread(
                target=run_flask_app,
                daemon=True,
                name="FlaskThread"
            )
            flask_thread.start()

            # Даємо Flask час на запуск
            await asyncio.sleep(3)

            if flask_thread.is_alive():
                logger.info(f"🌐 Flask server started on {config.HOST}:{config.PORT}")
            else:
                logger.error("Flask thread failed to start")
                return False

        except Exception as e:
            logger.error(f"Failed to start Flask thread: {e}")
            return False

        # Запускаємо бота
        bot_result = await run_bot()

        return bot_result

    except KeyboardInterrupt:
        logger.info("👋 Keyboard interrupt received")
        await graceful_shutdown()
        return True
    except Exception as e:
        logger.error(f"💥 Fatal error in main: {e}")
        return False


def sync_main():
    """Синхронна обгортка для main() з improved error handling"""
    try:
        # Налаштування для різних платформ
        if sys.platform == 'win32':
            # Windows потребує спеціального налаштування
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # Створюємо новий event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Встановлюємо debug режим якщо потрібно
        config = get_config()
        if config.DEBUG:
            loop.set_debug(True)

        try:
            # Запускаємо головну функцію
            success = loop.run_until_complete(main())
            return 0 if success else 1
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt in sync_main")
            return 0

    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        return 1
    finally:
        try:
            # ВИПРАВЛЕНО: Proper cleanup loop
            if 'loop' in locals() and loop:
                # Скасовуємо всі pending tasks
                try:
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        for task in pending:
                            task.cancel()

                        # Чекаємо на завершення з timeout
                        try:
                            loop.run_until_complete(
                                asyncio.wait_for(
                                    asyncio.gather(*pending, return_exceptions=True),
                                    timeout=5.0
                                )
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Some tasks did not complete in time")
                except Exception as e:
                    logger.error(f"Error cleaning up tasks: {e}")

                # Закриваємо loop
                try:
                    if not loop.is_closed():
                        loop.close()
                except Exception as e:
                    logger.error(f"Error closing loop: {e}")
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")


if __name__ == "__main__":
    # Показуємо інформацію про запуск
    print("=" * 60)
    print("🤖 SocialBoost Interface Bot")
    print("📝 Simple order collection and payment processing")
    print("🔗 Integrates with main processing bot")
    print("=" * 60)

    start_time = time.time()

    try:
        exit_code = sync_main()
        duration = time.time() - start_time

        if exit_code == 0:
            print(f"✅ Bot stopped successfully after {duration:.1f}s")
        else:
            print(f"❌ Bot stopped with errors after {duration:.1f}s")

        sys.exit(exit_code)

    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 Failed to start after {duration:.1f}s: {e}")
        sys.exit(1)