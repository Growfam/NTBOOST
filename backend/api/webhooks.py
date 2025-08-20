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

        return jsonify({
            'status': 'received',
            'update_type': data.get('update_type', 'unknown'),
            'message': 'Test webhook processed'
        }), 200

    except Exception as e:
        logger.error("Error in CryptoBot test webhook", error=str(e))
        return jsonify({'error': str(e)}), 500