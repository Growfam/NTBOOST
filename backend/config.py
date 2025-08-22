import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Базова конфігурація"""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_ENV', 'production') == 'development'

    # Server
    PORT = int(os.getenv('PORT', 8000))
    HOST = os.getenv('HOST', '0.0.0.0')

    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL')

    # Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

    # CryptoBot Payment
    CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN')
    CRYPTOBOT_WEBHOOK_SECRET = os.getenv('CRYPTOBOT_WEBHOOK_SECRET')

    # External Bot Integration
    MAIN_BOT_API_URL = os.getenv('MAIN_BOT_API_URL')
    MAIN_BOT_API_KEY = os.getenv('MAIN_BOT_API_KEY')

    # Admin Settings - ВИПРАВЛЕНО: звичайна змінна класу замість property
    _admin_telegram_ids: Optional[List[int]] = None

    @classmethod
    def get_admin_telegram_ids(cls) -> List[int]:
        """Повертає список ID адмінів"""
        if cls._admin_telegram_ids is None:
            admin_ids_str = os.getenv('ADMIN_TELEGRAM_IDS', '')
            if not admin_ids_str.strip():
                cls._admin_telegram_ids = []
            else:
                try:
                    cls._admin_telegram_ids = [
                        int(admin_id.strip())
                        for admin_id in admin_ids_str.split(',')
                        if admin_id.strip().isdigit()
                    ]
                except (ValueError, AttributeError):
                    cls._admin_telegram_ids = []

        return cls._admin_telegram_ids

    ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')

    # Bot Settings
    WEBHOOK_PATH = '/webhook/telegram'
    CRYPTOBOT_WEBHOOK_PATH = '/webhook/cryptobot'

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/bot.log'
    ERROR_LOG_FILE = 'logs/errors.log'

    # Cache Settings
    CACHE_TTL = int(os.getenv('CACHE_TTL', 300))  # 5 хвилин

    # Validation
    @classmethod
    def validate(cls) -> List[str]:
        """Перевіряє обов'язкові змінні"""
        errors = []

        required_vars = [
            ('TELEGRAM_BOT_TOKEN', cls.TELEGRAM_BOT_TOKEN),
            ('SUPABASE_URL', cls.SUPABASE_URL),
            ('SUPABASE_KEY', cls.SUPABASE_KEY),
            ('CRYPTOBOT_TOKEN', cls.CRYPTOBOT_TOKEN),
        ]

        for var_name, var_value in required_vars:
            if not var_value:
                errors.append(f"Missing required environment variable: {var_name}")

        # ВИПРАВЛЕНО: використовуємо метод замість property
        admin_ids = cls.get_admin_telegram_ids()
        if not admin_ids:
            errors.append("No admin Telegram IDs configured")

        # Перевіряємо валідність MAIN_BOT_API_URL якщо вказаний
        if cls.MAIN_BOT_API_URL and not cls.MAIN_BOT_API_URL.startswith(('http://', 'https://')):
            errors.append("MAIN_BOT_API_URL must start with http:// or https://")

        # Перевіряємо Redis URL
        if not cls.REDIS_URL:
            errors.append("REDIS_URL is required")

        return errors

    @classmethod
    def get_webhook_url(cls) -> Optional[str]:
        """Повертає повний URL для webhook"""
        if not cls.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{cls.TELEGRAM_WEBHOOK_URL.rstrip('/')}{cls.WEBHOOK_PATH}"

    @classmethod
    def get_cryptobot_webhook_url(cls) -> Optional[str]:
        """Повертає URL для CryptoBot webhook"""
        if not cls.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{cls.TELEGRAM_WEBHOOK_URL.rstrip('/')}{cls.CRYPTOBOT_WEBHOOK_PATH}"

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production mode"""
        return (
            os.getenv('RAILWAY_ENVIRONMENT') == 'production' or
            os.getenv('PRODUCTION', '').lower() == 'true' or
            os.getenv('FLASK_ENV') == 'production'
        )


class DevelopmentConfig(Config):
    """Конфігурація для розробки"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Конфігурація для продакшену"""
    DEBUG = False
    LOG_LEVEL = 'INFO'


class TestingConfig(Config):
    """Конфігурація для тестування"""
    DEBUG = True
    TESTING = True
    # Використовуємо in-memory Redis для тестів
    REDIS_URL = 'redis://localhost:6379/1'


# Вибір конфігурації
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}


def get_config():
    """Отримує конфігурацію згідно з FLASK_ENV"""
    env = os.getenv('FLASK_ENV', 'production')
    return config_map.get(env, ProductionConfig)