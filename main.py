#!/usr/bin/env python3
"""
SocialBoost Bot - Production Entry Point with detailed logging
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from threading import Thread
import traceback

# Setup paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config import get_config
from backend.utils.logger import setup_logging
from backend.app import create_app

# Setup logging FIRST
setup_logging()
logger = logging.getLogger(__name__)

# Configuration
config = get_config()
PORT = int(os.environ.get("PORT", 8000))

# Global app instance for Gunicorn
app = create_app()

# Log configuration status
logger.info("=" * 50)
logger.info("CONFIGURATION CHECK:")
logger.info(f"PORT: {PORT}")
logger.info(f"TELEGRAM_BOT_TOKEN: {'SET' if config.TELEGRAM_BOT_TOKEN else 'MISSING!!!'}")
logger.info(f"SUPABASE_URL: {'SET' if config.SUPABASE_URL else 'MISSING!!!'}")
logger.info(f"REDIS_URL: {config.REDIS_URL}")
logger.info(f"PRODUCTION MODE: {config.is_production()}")
logger.info("=" * 50)


def run_bot_in_thread():
    """Run Telegram bot in separate thread with detailed error logging"""

    async def bot_runner():
        try:
            logger.info("Starting bot setup...")

            # Check critical environment variables
            if not config.TELEGRAM_BOT_TOKEN:
                logger.error("TELEGRAM_BOT_TOKEN is not set! Bot cannot start.")
                return False

            # Import bot modules here to catch import errors
            try:
                from backend.bot.main import setup_bot, get_bot, get_dispatcher
                logger.info("Bot modules imported successfully")
            except Exception as e:
                logger.error(f"Failed to import bot modules: {e}")
                logger.error(traceback.format_exc())
                return False

            # Setup bot
            logger.info("Calling setup_bot()...")
            setup_result = await setup_bot()

            if not setup_result:
                logger.error("setup_bot() returned False")
                return False

            logger.info("Bot setup completed successfully")

            # Get bot and dispatcher
            bot = await get_bot()
            dp = await get_dispatcher()

            # Start polling
            logger.info("🚀 Starting Telegram bot polling...")
            await dp.start_polling(bot)

        except Exception as e:
            logger.error(f"Critical bot error: {e}")
            logger.error(traceback.format_exc())
            return False

    # Create new event loop for thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(bot_runner())
        if result is False:
            logger.error("Bot runner failed to start")
    except KeyboardInterrupt:
        logger.info("Bot polling stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in bot thread: {e}")
        logger.error(traceback.format_exc())
    finally:
        try:
            loop.close()
        except:
            pass


# Start bot in background thread when module loads
if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PRODUCTION"):
    logger.info("Production environment detected, starting bot thread...")

    # Validate configuration before starting
    validation_errors = config.validate()
    if validation_errors:
        logger.error("Configuration validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
    else:
        logger.info("Configuration validation passed")

    bot_thread = Thread(target=run_bot_in_thread, daemon=True)
    bot_thread.start()
    logger.info("Bot thread started")

if __name__ == "__main__":
    # Development mode - run Flask dev server
    if config.DEBUG:
        logger.info("Running in DEBUG mode")
        # Start bot thread
        bot_thread = Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()

        # Run Flask dev server
        app.run(
            host="0.0.0.0",
            port=PORT,
            debug=False  # Never use debug=True with threading
        )
    else:
        # Production - just start bot thread, Gunicorn will handle Flask
        logger.info(f"App ready for Gunicorn on port {PORT}")
        # Keep main thread alive
        try:
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")