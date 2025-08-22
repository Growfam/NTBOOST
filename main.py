#!/usr/bin/env python3
"""
SocialBoost Bot - Railway Edition
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

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


async def main():
    """Main entry point"""
    try:
        # Setup bot
        if not await setup_bot():
            logger.error("Failed to setup bot")
            return False

        # Get bot and dispatcher
        bot = await get_bot()
        dp = await get_dispatcher()

        # Start bot polling
        logger.info(f"🚀 Starting bot on port {PORT}")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return False


def run_flask():
    """Run Flask in production mode"""
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )


if __name__ == "__main__":
    # Railway використовує PORT змінну
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        # Production mode on Railway
        run_flask()
    else:
        # Development mode
        asyncio.run(main())