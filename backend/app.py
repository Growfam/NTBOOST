"""
Flask додаток для API та webhook - ФІНАЛЬНА виправлена версія
"""
from flask import Flask, request, jsonify
import asyncio
import structlog
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading
import atexit

from backend.config import get_config
from backend.services.payment_service import PaymentService
from backend.services.external_service import ExternalService
from backend.utils.logger import setup_logging

config = get_config()
logger = structlog.get_logger(__name__)

# ВИПРАВЛЕНО: Thread pool з proper cleanup
thread_pool = None
thread_pool_lock = threading.Lock()


def get_thread_pool():
    """Thread-safe отримання thread pool"""
    global thread_pool

    if thread_pool is None:
        with thread_pool_lock:
            if thread_pool is None:
                thread_pool = ThreadPoolExecutor(
                    max_workers=4,
                    thread_name_prefix='async_handler'
                )
                # Реєструємо cleanup при виході
                atexit.register(cleanup_thread_pool)
                logger.info("Thread pool created")

    return thread_pool


def cleanup_thread_pool():
    """Очищення thread pool"""
    global thread_pool

    if thread_pool:
        logger.info("Shutting down thread pool...")
        thread_pool.shutdown(wait=True, timeout=5.0)
        thread_pool = None
        logger.info("Thread pool shutdown completed")


def run_async_in_thread(coro, timeout=25):
    """ВИПРАВЛЕНО: Виконує async функцію з proper error handling"""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Async operation failed: {e}")
            raise
        finally:
            try:
                # Закриваємо pending tasks
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                loop.close()

    pool = get_thread_pool()

    try:
        future = pool.submit(run)
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        logger.error(f"Async operation timeout after {timeout}s")
        raise TimeoutError(f"Operation timeout after {timeout}s")
    except Exception as e:
        logger.error(f"Async operation error: {e}")
        raise


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
            from backend.utils.cache import check_redis_health

            checks = {
                'database': db.health_check(),
                'redis': check_redis_health(),
                'thread_pool': thread_pool is not None and not thread_pool._shutdown,
                'service': 'interface-bot'
            }

            all_healthy = checks['database'] and checks['redis'] and checks['thread_pool']

            return jsonify({
                'status': 'healthy' if all_healthy else 'degraded',
                'checks': checks
            }), 200 if all_healthy else 503

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 503

    # ВИПРАВЛЕНО: безпечна перевірка webhook path
    webhook_path = getattr(config, 'CRYPTOBOT_WEBHOOK_PATH', None)
    if webhook_path:
        @app.route(webhook_path, methods=['POST'])
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
                    # ВИПРАВЛЕНО: додаємо try-catch для async операції
                    try:
                        is_valid = run_async_in_thread(
                            PaymentService.verify_webhook(body, signature),
                            timeout=10
                        )
                        if not is_valid:
                            logger.warning("Invalid webhook signature")
                            return jsonify({'error': 'Invalid signature'}), 401
                    except TimeoutError:
                        logger.error("Webhook signature verification timeout")
                        return jsonify({'error': 'Verification timeout'}), 408

                # ВИПРАВЛЕНО: додаємо try-catch для async операції
                try:
                    success = run_async_in_thread(
                        PaymentService.process_payment_webhook(webhook_data),
                        timeout=20
                    )

                    if success:
                        logger.info("Payment webhook processed successfully")
                        return jsonify({'status': 'ok'}), 200
                    else:
                        logger.error("Failed to process payment webhook")
                        return jsonify({'error': 'Processing failed'}), 400

                except TimeoutError:
                    logger.error("Payment webhook processing timeout")
                    return jsonify({'error': 'Processing timeout'}), 408

            except Exception as e:
                logger.error("Error processing CryptoBot webhook", error=str(e))
                return jsonify({'error': 'Internal error'}), 500

    @app.route('/api/tasks/pending', methods=['GET'])
    def get_pending_tasks():
        """API для отримання завдань основним ботом"""
        try:
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not config.MAIN_BOT_API_KEY or api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            limit = request.args.get('limit', 10, type=int)
            limit = min(max(limit, 1), 50)  # Обмежуємо від 1 до 50

            # ВИПРАВЛЕНО: додаємо try-catch для async операції
            try:
                tasks = run_async_in_thread(
                    ExternalService.send_pending_tasks(limit),
                    timeout=15
                )

                return jsonify({
                    'success': True,
                    'tasks_sent': tasks
                }), 200

            except TimeoutError:
                logger.error("Get pending tasks timeout")
                return jsonify({'error': 'Operation timeout'}), 408

        except Exception as e:
            logger.error("Error getting pending tasks", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tasks/<task_id>/status', methods=['PUT'])
    def update_task_status(task_id: str):
        """API для оновлення статусу завдання основним ботом"""
        try:
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not config.MAIN_BOT_API_KEY or api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400

            status = data.get('status')
            external_task_id = data.get('external_task_id')
            response_data = data.get('response_data')

            if not status:
                return jsonify({'error': 'Status is required'}), 400

            # Валідуємо статус
            from backend.utils.validators import validate_task_status
            if not validate_task_status(status):
                return jsonify({'error': 'Invalid status'}), 400

            # Валідуємо task_id
            if not task_id or len(task_id) > 100:
                return jsonify({'error': 'Invalid task_id'}), 400

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
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not config.MAIN_BOT_API_KEY or api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            from backend.database.connection import get_admin_stats
            stats = get_admin_stats()

            return jsonify(stats), 200

        except Exception as e:
            logger.error("Error getting admin stats via API", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.route('/api/bot/status', methods=['GET'])
    def get_bot_status():
        """API для перевірки статусу бота"""
        try:
            # Перевіряємо API ключ
            api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not config.MAIN_BOT_API_KEY or api_key != config.MAIN_BOT_API_KEY:
                return jsonify({'error': 'Unauthorized'}), 401

            from backend.bot.main import is_bot_initialized, is_dispatcher_initialized

            status = {
                'bot_initialized': is_bot_initialized(),
                'dispatcher_initialized': is_dispatcher_initialized(),
                'webhook_mode': bool(config.TELEGRAM_WEBHOOK_URL),
                'thread_pool_active': thread_pool is not None and not thread_pool._shutdown,
                'service': 'socialboost-interface-bot'
            }

            return jsonify(status), 200

        except Exception as e:
            logger.error("Error getting bot status", error=str(e))
            return jsonify({'error': str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error", error=str(error))
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(408)
    def timeout_error(error):
        return jsonify({'error': 'Request timeout'}), 408

    # Додаємо middleware для логування запитів
    @app.before_request
    def log_request():
        logger.info(
            "Request received",
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr,
            user_agent=request.user_agent.string[:100] if request.user_agent else None
        )

    @app.after_request
    def log_response(response):
        logger.info(
            "Response sent",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            content_length=response.content_length
        )
        return response

    # ВИПРАВЛЕНО: додаємо cleanup при завершенні Flask app
    @app.teardown_appcontext
    def cleanup_app_context(error):
        if error:
            logger.error(f"App context error: {error}")

    return app