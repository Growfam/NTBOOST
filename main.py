#!/usr/bin/env python3
"""
SocialBoost Bot - Production Entry Point
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from threading import Thread

# Setup paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config import get_config
from backend.utils.logger import setup_logging
from backend.bot.main import setup_bot, get_bot, get_dispatcher
from backend.app import create_app

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Configuration
config = get_config()
PORT = int(os.environ.get("PORT", 8000))

# Global app instance for Gunicorn
app = create_app()


def run_bot_in_thread():
    """Run Telegram bot in separate thread"""

    async def bot_runner():
        try:
            # Setup bot
            if not await setup_bot():
                logger.error("Failed to setup bot")
                return

            # Get bot and dispatcher
            bot = await get_bot()
            dp = await get_dispatcher()

            # Start polling
            logger.info("🚀 Starting Telegram bot polling...")
            await dp.start_polling(bot)

        except Exception as e:
            logger.error(f"Bot error: {e}")

    # Create new event loop for thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(bot_runner())
    except KeyboardInterrupt:
        logger.info("Bot polling stopped")
    finally:
        loop.close()


# Start bot in background thread when module loads
if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PRODUCTION"):
    bot_thread = Thread(target=run_bot_in_thread, daemon=True)
    bot_thread.start()
    logger.info("Bot thread started")

if __name__ == "__main__":
    # Development mode - run Flask dev server
    if config.DEBUG:
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
        print(f"App ready for Gunicorn on port {PORT}")
        # Keep main thread alive
        try:
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")