"""
Валідація даних - покращена версія
"""
import re
from typing import Optional, Tuple
from urllib.parse import urlparse


# Покращені паттерни URL
URL_PATTERNS = {
    'telegram': [
        r'https?://t\.me/\w+/\d+',
        r'https?://t\.me/c/\d+/\d+',  # Приватні канали
        r'https?://telegram\.me/\w+/\d+',
    ],
    'instagram': [
        r'https?://(?:www\.)?instagram\.com/p/[\w-]+',
        r'https?://(?:www\.)?instagram\.com/reel/[\w-]+',
        r'https?://(?:www\.)?instagram\.com/tv/[\w-]+',
    ],
    'tiktok': [
        r'https?://(?:www\.)?tiktok\.com/@[\w.]+/video/\d+',
        r'https?://vm\.tiktok\.com/[\w-]+',
        r'https?://(?:www\.)?tiktok\.com/t/[\w-]+',
    ],
    'youtube': [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]
}

PLATFORMS = {
    'telegram': 'Telegram',
    'instagram': 'Instagram',
    'tiktok': 'TikTok',
    'youtube': 'YouTube'
}


def validate_post_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Валідує URL поста та визначає платформу
    Повертає (is_valid, platform)
    """
    if not url or not isinstance(url, str):
        return False, None

    url = url.strip()

    # Базова перевірка URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, None
    except Exception:
        return False, None

    # Перевіряємо кожну платформу
    for platform, patterns in URL_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, platform

    return False, None


def validate_telegram_id(telegram_id: str) -> bool:
    """Валідує Telegram ID"""
    if not telegram_id:
        return False

    try:
        # Telegram ID має бути числом
        telegram_id_int = int(telegram_id)
        # Telegram ID має бути позитивним і довжиною принаймні 5 цифр
        return telegram_id_int > 0 and len(telegram_id) >= 5
    except (ValueError, TypeError):
        return False


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Очищає текст від небезпечних символів"""
    if not text:
        return ""

    # Видаляємо потенційно небезпечні символи
    # Дозволяємо тільки основні HTML теги
    import html
    text = html.escape(text)

    # Обмежуємо довжину
    text = text[:max_length]

    return text.strip()


def validate_amount(amount: str) -> Tuple[bool, float]:
    """Валідує суму грошей"""
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            return False, 0.0
        if amount_float > 10000:  # Максимальна сума
            return False, 0.0
        return True, round(amount_float, 2)
    except (ValueError, TypeError):
        return False, 0.0


def validate_email(email: str) -> bool:
    """Валідує email адресу"""
    if not email or not isinstance(email, str):
        return False

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email.strip()))


def validate_package_slug(slug: str) -> bool:
    """Валідує slug пакету"""
    if not slug or not isinstance(slug, str):
        return False

    # Slug має містити тільки літери, цифри, дефіси та підкреслення
    slug_pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(slug_pattern, slug)) and len(slug) <= 50


def sanitize_username(username: str) -> str:
    """Очищає username від небезпечних символів"""
    if not username:
        return ""

    # Видаляємо @ на початку якщо є
    if username.startswith('@'):
        username = username[1:]

    # Залишаємо тільки дозволені символи для username
    username = re.sub(r'[^a-zA-Z0-9_]', '', username)

    return username[:32]  # Обмежуємо довжину


def validate_order_status(status: str) -> bool:
    """Валідує статус замовлення"""
    valid_statuses = [
        'pending', 'paid', 'processing', 'completed',
        'failed', 'cancelled', 'refunded'
    ]
    return status in valid_statuses


def validate_task_status(status: str) -> bool:
    """Валідує статус завдання"""
    valid_statuses = [
        'created', 'sent', 'processing', 'completed',
        'failed', 'cancelled'
    ]
    return status in valid_statuses