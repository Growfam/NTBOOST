"""
Сервіс для відправки завдань основному боту
"""
import requests
from typing import Dict, Any, List
import structlog

from backend.config import get_config
from backend.database.connection import (
    add_user_post, get_pending_tasks, update_task_status
)

config = get_config()
logger = structlog.get_logger(__name__)

class ExternalService:
    """Сервіс для інтеграції з основним ботом"""

    @staticmethod
    async def add_post_for_processing(telegram_id: str, post_url: str,
                                    platform: str = "telegram") -> Dict[str, Any]:
        """Додає пост користувача та створює завдання"""
        try:
            result = add_user_post(telegram_id, post_url, platform)

            if result.get('success'):
                logger.info(f"Post added for user {telegram_id}",
                          post_id=result.get('post_id'),
                          task_id=result.get('task_id'))

                # Спробуємо відправити завдання одразу
                await ExternalService.send_pending_tasks()

            return result

        except Exception as e:
            logger.error(f"Error adding post for {telegram_id}",
                        error=str(e), post_url=post_url)
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def send_pending_tasks(limit: int = 5) -> int:
        """Відправляє завдання в черзі основному боту"""
        try:
            tasks = get_pending_tasks(limit)

            if not tasks:
                return 0

            sent_count = 0

            for task in tasks:
                success = await ExternalService._send_single_task(task)
                if success:
                    sent_count += 1

            logger.info(f"Sent {sent_count}/{len(tasks)} tasks to main bot")
            return sent_count

        except Exception as e:
            logger.error("Error sending pending tasks", error=str(e))
            return 0

    @staticmethod
    async def _send_single_task(task: Dict[str, Any]) -> bool:
        """Відправляє одне завдання основному боту"""
        try:
            task_id = task.get('task_id')

            if not config.MAIN_BOT_API_URL or not config.MAIN_BOT_API_KEY:
                # Якщо основний бот не налаштований, просто помічаємо як відправлено
                update_task_status(task_id, "sent", f"mock_task_{task_id}", {"mock": True})
                logger.info(f"Task {task_id} marked as sent (mock mode)")
                return True

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.MAIN_BOT_API_KEY}"
            }

            payload = {
                "interface_task_id": task_id,
                "user_data": task.get('user_data'),
                "post_data": task.get('post_data'),
                "package_data": task.get('package_data')
            }

            response = requests.post(
                f"{config.MAIN_BOT_API_URL}/api/process-task",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # Оновлюємо статус завдання
                    update_task_status(
                        task_id,
                        "sent",
                        data.get("main_task_id"),
                        {"sent_at": "now", "main_bot_response": data}
                    )

                    logger.info(f"Task {task_id} sent successfully to main bot")
                    return True

            logger.error(f"Failed to send task {task_id}",
                        status=response.status_code,
                        response=response.text)
            return False

        except Exception as e:
            logger.error(f"Error sending task {task.get('task_id')}", error=str(e))
            return False

    @staticmethod
    async def check_main_bot_health() -> bool:
        """Перевіряє доступність основного бота"""
        try:
            if not config.MAIN_BOT_API_URL:
                return False

            response = requests.get(
                f"{config.MAIN_BOT_API_URL}/health",
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            logger.error("Main bot health check failed", error=str(e))
            return False