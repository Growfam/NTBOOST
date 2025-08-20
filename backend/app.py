"""
Flask додаток для API та webhook
"""
from flask import Flask, request, jsonify
import structlog

from backend.config import get_config
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
        return jsonify({
            'status': 'healthy',
            'service': 'interface-bot'
        }), 200

    return app