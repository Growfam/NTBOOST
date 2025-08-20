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
            'main_bot': False
        }

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


def _check_redis() -> bool:
    """Перевірка підключення до Redis"""
    try:
        from backend.utils.cache import cache
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        return result == 'ok'
    except:
        return False