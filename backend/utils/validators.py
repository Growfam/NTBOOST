"""
Валідація даних
"""
import re
from typing import Optional, Tuple
from backend.utils.constants import URL_PATTERNS, PLATFORMS


def validate_post_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Валідує URL поста та визначає платформу
    Повертає (is_valid, platform)
    """
    if not url or not isinstance(url, str):
        return False, None

    url = url.strip()

    for platform, pattern in URL_PATTERNS.items():
        if re.match(pattern, url, re.IGNORECASE):
            return True, platform

    return False, None


def validate_telegram_id(telegram_id: str) -> bool:
    """Валідує Telegram ID"""
    if not telegram_id:
        return False

    try:
        # Telegram ID має бути числом
        int(telegram_id)
        return len(telegram_id) >= 5  # Мінімальна довжина
    except ValueError:
        return False


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Очищає текст від небезпечних символів"""
    if not text:
        return ""

    # Видаляємо HTML теги (окрім дозволених)
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'code', 'pre']

    # Обмежуємо довжину
    text = text[:max_length]

    return text.strip()