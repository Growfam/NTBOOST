# backend/utils/cache.py
"""
Redis кешування для швидкодії
"""
import json
import redis
from typing import Any, Optional
import structlog

from backend.config import get_config

config = get_config()
logger = structlog.get_logger(__name__)


class RedisCache:
    """Простий Redis кеш"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    def connect(self) -> redis.Redis:
        """Підключення до Redis"""
        if not self._redis:
            self._redis = redis.from_url(config.REDIS_URL, decode_responses=True)
            logger.info("Connected to Redis")
        return self._redis

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Зберігає значення в кеші"""
        try:
            r = self.connect()
            json_value = json.dumps(value, ensure_ascii=False)
            ttl = ttl or config.CACHE_TTL
            r.setex(key, ttl, json_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}", error=str(e))
            return False

    def get(self, key: str) -> Any:
        """Отримує значення з кешу"""
        try:
            r = self.connect()
            value = r.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}", error=str(e))
            return None

    def delete(self, key: str) -> bool:
        """Видаляє ключ з кешу"""
        try:
            r = self.connect()
            r.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}", error=str(e))
            return False

    def exists(self, key: str) -> bool:
        """Перевіряє існування ключа"""
        try:
            r = self.connect()
            return bool(r.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}", error=str(e))
            return False


# Глобальний інстанс кешу
cache = RedisCache()


# Зручні функції для кешування даних бота
def cache_user_stats(telegram_id: str, stats: dict, ttl: int = 300):
    """Кешує статистику користувача на 5 хвилин"""
    cache.set(f"user_stats:{telegram_id}", stats, ttl)


def get_cached_user_stats(telegram_id: str) -> Optional[dict]:
    """Отримує закешовану статистику"""
    return cache.get(f"user_stats:{telegram_id}")


def cache_packages(packages: list, ttl: int = 600):
    """Кешує список пакетів на 10 хвилин"""
    cache.set("packages", packages, ttl)


def get_cached_packages() -> Optional[list]:
    """Отримує закешовані пакети"""
    return cache.get("packages")


def invalidate_user_cache(telegram_id: str):
    """Очищає кеш користувача"""
    cache.delete(f"user_stats:{telegram_id}")


# ===================================

# backend/utils/logger.py
"""
Налаштування логування
"""
import os
import sys
import structlog
from pathlib import Path

from backend.config import get_config

config = get_config()


def setup_logging():
    """Налаштовує систему логування"""

    # Створюємо папку для логів
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Налаштування structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Налаштування стандартного логування Python
    import logging
    import logging.handlers

    # Основний logger
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, config.LOG_LEVEL.upper())
    )

    # File handler для загальних логів
    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    # File handler для помилок
    error_handler = logging.handlers.RotatingFileHandler(
        config.ERROR_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)

    # Додаємо handlers до root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    # Налаштування для aiogram (менше спаму)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


# ===================================

# backend/utils/constants.py
"""
Константи для бота
"""

# Емодзі для інтерфейсу
EMOJI = {
    'rocket': '🚀',
    'package': '📦',
    'money': '💰',
    'check': '✅',
    'cross': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'star': '⭐',
    'fire': '🔥',
    'heart': '❤️',
    'thumbs_up': '👍',
    'chart': '📊',
    'calendar': '📅',
    'time': '⏱️',
    'link': '🔗',
    'admin': '👨‍💼',
    'bell': '🔔',
    'settings': '⚙️'
}

# Тексти повідомлень
MESSAGES = {
    'welcome': f"{EMOJI['rocket']} <b>Вітаємо в SocialBoost Bot!</b>\n\nОберіть пакет для розкрутки ваших постів:",

    'packages_header': f"{EMOJI['package']} <b>Доступні пакети:</b>",

    'order_created': f"{EMOJI['check']} Замовлення створено!\n\n{EMOJI['money']} Сума: <b>{{amount}} {{currency}}</b>\n{EMOJI['package']} Пакет: <b>{{package_name}}</b>",

    'payment_success': f"{EMOJI['check']} <b>Оплата успішна!</b>\n\nВаш пакет активовано. Тепер ви можете додавати пости для розкрутки.",

    'add_post_prompt': f"{EMOJI['link']} Надішліть посилання на ваш пост:",

    'post_added': f"{EMOJI['check']} <b>Пост додано!</b>\n\n{EMOJI['chart']} Цільові показники:\n• Перегляди: {{views}}\n• Реакції: {{reactions}}\n• Коментарі: {{comments}}\n• Репости: {{reposts}}",

    'limit_reached': f"{EMOJI['warning']} <b>Ліміт вичерпано!</b>\n\nВи досягли денного ліміту постів для вашого пакету.",

    'no_active_package': f"{EMOJI['info']} У вас немає активного пакету. Оберіть пакет для початку роботи:",

    'invalid_url': f"{EMOJI['cross']} Невірне посилання. Будь ласка, надішліть правильний URL.",

    'admin_notification': f"{EMOJI['bell']} <b>Нове замовлення!</b>\n\n{EMOJI['admin']} Користувач: {{username}}\n{EMOJI['money']} Сума: {{amount}} {{currency}}\n{EMOJI['package']} Пакет: {{package_name}}\n{EMOJI['time']} Час: {{time}}"
}


# Стани FSM
class UserStates:
    """Стани користувача"""
    WAITING_POST_URL = "waiting_post_url"
    SELECTING_PACKAGE = "selecting_package"
    CONFIRMING_ORDER = "confirming_order"


# Callback data для кнопок
CALLBACK_DATA = {
    'select_package': 'pkg_{}',
    'confirm_order': 'confirm_{}',
    'cancel_order': 'cancel_{}',
    'add_post': 'add_post',
    'my_stats': 'my_stats',
    'support': 'support'
}

# Платформи для постів
PLATFORMS = {
    'telegram': 'Telegram',
    'instagram': 'Instagram',
    'tiktok': 'TikTok',
    'youtube': 'YouTube'
}

# Валідація URL
URL_PATTERNS = {
    'telegram': r'https?://t\.me/\w+/\d+',
    'instagram': r'https?://(?:www\.)?instagram\.com/p/[\w-]+',
    'tiktok': r'https?://(?:www\.)?tiktok\.com/@[\w.]+/video/\d+',
    'youtube': r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+'
}

# ===================================

# backend/utils/validators.py
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