"""
Сервіс для роботи з CryptoBot платежами
"""
import requests
from typing import Dict, Any, Optional
import structlog

from backend.config import get_config
from backend.services.order_service import OrderService

config = get_config()
logger = structlog.get_logger(__name__)


class PaymentService:
    """Сервіс для роботи з CryptoBot API"""

    BASE_URL = "https://pay.crypt.bot/api"

    @staticmethod
    async def create_invoice(order_id: str, amount: float, currency: str = "USD",
                             description: str = "") -> Dict[str, Any]:
        """Створює рахунок для оплати в CryptoBot"""
        try:
            headers = {
                "Crypto-Pay-API-Token": config.CRYPTOBOT_TOKEN,
                "Content-Type": "application/json"
            }

            payload = {
                "asset": "USDT",  # Використовуємо USDT для стабільності
                "amount": str(amount),
                "description": description or f"Оплата замовлення {order_id}",
                "payload": order_id,  # Передаємо order_id як payload
                "expires_in": 3600  # 1 година на оплату
            }

            response = requests.post(
                f"{PaymentService.BASE_URL}/createInvoice",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    invoice = data.get("result", {})
                    logger.info(f"Invoice created for order {order_id}",
                                invoice_id=invoice.get("invoice_id"))
                    return {
                        "success": True,
                        "invoice_id": invoice.get("invoice_id"),
                        "pay_url": invoice.get("pay_url"),
                        "amount": invoice.get("amount"),
                        "asset": invoice.get("asset")
                    }

            logger.error(f"CryptoBot API error for order {order_id}",
                         status=response.status_code,
                         response=response.text)
            return {"success": False, "error": "Payment service error"}

        except Exception as e:
            logger.error(f"Error creating invoice for order {order_id}", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    async def verify_webhook(body: bytes, signature: str) -> bool:
        """Перевіряє підпис webhook від CryptoBot"""
        try:
            import hmac
            import hashlib

            if not config.CRYPTOBOT_WEBHOOK_SECRET:
                return True  # Якщо секрет не налаштований, пропускаємо

            secret = config.CRYPTOBOT_WEBHOOK_SECRET.encode()
            expected_signature = hmac.new(
                secret,
                body,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error("Error verifying webhook signature", error=str(e))
            return False

    @staticmethod
    async def process_payment_webhook(webhook_data: Dict[str, Any]) -> bool:
        """Обробляє webhook про успішну оплату"""
        try:
            update_type = webhook_data.get("update_type")

            if update_type == "invoice_paid":
                invoice = webhook_data.get("payload", {})
                order_id = invoice.get("payload")  # Наш order_id
                status = invoice.get("status")

                if status == "paid" and order_id:
                    # Активуємо замовлення
                    success = await OrderService.activate_user_order(order_id)

                    if success:
                        logger.info(f"Payment processed successfully for order {order_id}")
                        return True
                    else:
                        logger.error(f"Failed to activate order {order_id} after payment")
                        return False

            logger.warning("Unhandled webhook update type", update_type=update_type)
            return False

        except Exception as e:
            logger.error("Error processing payment webhook", error=str(e))
            return False