# backend/bot/main.py
"""
Основний файл Telegram бота
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import structlog

from backend.config import get_config
from backend.bot.handlers import start, packages, orders, admin
from backend.utils.logger import setup_logging
from backend.database.connection import init_database

config = get_config()
logger = structlog.get_logger(__name__)

# Ініціалізація бота
bot = Bot(token=config.TELEGRAM_BOT_TOKEN, parse_mode="HTML")

# Redis storage для FSM
storage = RedisStorage.from_url(config.REDIS_URL)

# Диспетчер
dp = Dispatcher(storage=storage)


async def setup_bot():
    """Налаштування бота"""
    try:
        # Реєструємо роутери
        dp.include_router(start.router)
        dp.include_router(packages.router)
        dp.include_router(orders.router)
        dp.include_router(admin.router)

        # Ініціалізуємо базу даних
        if not await init_database():
            logger.error("Failed to initialize database")
            return False

        # Налаштовуємо webhook
        webhook_url = config.get_webhook_url()
        if webhook_url:
            await bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
        else:
            logger.warning("No webhook URL configured")

        logger.info("Bot setup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error setting up bot: {e}")
        return False


async def shutdown_bot():
    """Закриття бота"""
    try:
        await bot.session.close()
        await storage.close()
        logger.info("Bot shutdown completed")
    except Exception as e:
        logger.error(f"Error during bot shutdown: {e}")


def create_webhook_app():
    """Створює aiohttp додаток для webhook"""
    app = web.Application()

    # Налаштовуємо webhook handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)

    return app


# ===================================

# backend/app.py
"""
Flask додаток для API та webhook
"""
from flask import Flask, request, jsonify
import asyncio
import structlog
from typing import Dict, Any

from backend.config import get_config
from backend.services.payment_service import PaymentService
from backend.services.external_service import ExternalService
from backend.bot.handlers.admin import notify_admins_payment_success
from backend.utils.logger import setup_logging

config = get_config()
logger = structlog.get_logger(__name__)


def create_app():
    """Створює Flask додаток"""
    app = Flask(__name__)
    app.config.from_object(config)

    # Налаштовуємо логування
    setup_logging()

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            from backend.database.connection import db
            db_healthy = db.health_check()

            return jsonify({
                'status': 'healthy' if db_healthy else 'unhealthy',
                'database': 'connected' if db_healthy else 'disconnected',
                'service': 'interface-bot'
            }), 200 if db_healthy else 503

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 503

    @app.route(config.CRYPTOBOT_WEBHOOK_PATH, methods=['POST'])
    def cryptobot_webhook():
        """Webhook для CryptoBot платежів"""
        try:
            # Отримуємо дані
            webhook_data = request.get_json()

            if not webhook_data:
                logger.warning("Empty webhook data received")
                return jsonify({'error': 'No data'}), 400

            # Перевіряємо підпис (якщо налаштований)
            signature = request.headers.get('Crypto-Pay-API-Signature')
            if config.CRYPTOBOT_WEBHOOK_SECRET and signature:
                body = request.get_data()
                is_valid = asyncio.run(
                    PaymentService.verify_webhook(body, signature)
                )
                if not is_valid:
                    logger.warning("Invalid webhook signature")
                    return jsonify({'error': 'Invalid signature'}), 401

            # Обробляємо платіж
            success = asyncio.run(
                PaymentService.process_payment_webhook(webhook_data)
            )

            if success:
                logger.info("Payment webhook processed successfully")
                return jsonify({'status': 'ok'}), 200
            else:
                logger.error("Failed to process payment webhook")
                return jsonify({'error': 'Processing failed'}), 400

        except Exception as e:
            logger.error("Error processing CryptoBot webhook", error=str(e))
            return jsonify({'error': 'Internal error'}), 500

    @app.route('/api/tasks/pending', methods=['GET'])
    def get_pending_tasks():
        """API для отримання завдань основним ботом"""
        try:
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            limit = request.args.get('limit', 10, type=int)

            # Отримуємо завдання
            tasks = asyncio.run(ExternalService.send_pending_tasks(limit))

            return jsonify({
                'success': True,
                'tasks_sent': tasks
            }), 200

        except Exception as e:
            logger.error("Error getting pending tasks", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tasks/<task_id>/status', methods=['PUT'])
    def update_task_status(task_id: str):
        """API для оновлення статусу завдання основним ботом"""
        try:
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400

            status = data.get('status')
            external_task_id = data.get('external_task_id')
            response_data = data.get('response_data')

            if not status:
                return jsonify({'error': 'Status is required'}), 400

            # Оновлюємо статус
            from backend.database.connection import update_task_status
            success = update_task_status(task_id, status, external_task_id, response_data)

            if success:
                return jsonify({'success': True}), 200
            else:
                return jsonify({'error': 'Failed to update status'}), 400

        except Exception as e:
            logger.error(f"Error updating task status for {task_id}", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.route('/api/stats/admin', methods=['GET'])
    def get_admin_stats_api():
        """API для отримання адмін статистики"""
        try:
            # Перевіряємо API ключ або адмін права
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            from backend.database.connection import get_admin_stats
            stats = get_admin_stats()

            return jsonify(stats), 200

        except Exception as e:
            logger.error("Error getting admin stats via API", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error", error=str(error))
        return jsonify({'error': 'Internal server error'}), 500

    return app


# ===================================

# backend/api/webhooks.py
"""
Додаткові webhook обробники
"""
from flask import Blueprint, request, jsonify
import structlog

from backend.services.payment_service import PaymentService
from backend.config import get_config

config = get_config()
logger = structlog.get_logger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhook')


@webhooks_bp.route('/test', methods=['GET', 'POST'])
def webhook_test():
    """Тестовий endpoint для перевірки webhook"""
    try:
        method = request.method
        data = request.get_json() if method == 'POST' else request.args.to_dict()

        logger.info(f"Webhook test called via {method}", data=data)

        return jsonify({
            'status': 'ok',
            'method': method,
            'data_received': data,
            'message': 'Webhook is working'
        }), 200

    except Exception as e:
        logger.error("Error in webhook test", error=str(e))
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/cryptobot/test', methods=['POST'])
def cryptobot_test():
    """Тестовий endpoint для CryptoBot webhook"""
    try:
        data = request.get_json()

        logger.info("CryptoBot test webhook received", data=data)

        # Імітуємо обробку
        return jsonify({
            'status': 'received',
            'update_type': data.get('update_type', 'unknown'),
            'message': 'Test webhook processed'
        }), 200

    except Exception as e:
        logger.error("Error in CryptoBot test webhook", error=str(e))
        return jsonify({'error': str(e)}), 500


# ===================================

# backend/api/health.py
"""
Health check endpoints
"""
from flask import Blueprint, jsonify
import structlog

from backend.database.connection import db
from backend.services.external_service import ExternalService

logger = structlog.get_logger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/health')


@health_bp.route('/', methods=['GET'])
def health_check():
    """Основний health check"""
    try:
        checks = {
            'database': db.health_check(),
            'redis': _check_redis(),
            'main_bot': False  # Буде перевірено асинхронно
        }

        # Асинхронна перевірка основного бота
        import asyncio
        try:
            checks['main_bot'] = asyncio.run(ExternalService.check_main_bot_health())
        except:
            checks['main_bot'] = False

        all_healthy = all(checks.values())

        return jsonify({
            'status': 'healthy' if all_healthy else 'degraded',
            'checks': checks,
            'service': 'socialboost-interface-bot'
        }), 200 if all_healthy else 503

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@health_bp.route('/database', methods=['GET'])
def database_health():
    """Перевірка бази даних"""
    try:
        healthy = db.health_check()
        return jsonify({
            'database': 'healthy' if healthy else 'unhealthy'
        }), 200 if healthy else 503
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@health_bp.route('/redis', methods=['GET'])
def redis_health():
    """Перевірка Redis"""
    try:
        healthy = _check_redis()
        return jsonify({
            'redis': 'healthy' if healthy else 'unhealthy'
        }), 200 if healthy else 503
    except Exception as e:
        return jsonify({'error': str(e)}), 503


def _check_redis() -> bool:
    """Перевірка підключення до Redis"""
    try:
        from backend.utils.cache import cache
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        return result == 'ok'
    except:
        return False