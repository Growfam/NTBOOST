import os
from typing import List
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
    MAIN_BOT_API_URL = os.getenv('MAIN_BOT_API_URL', 'http://main-bot-api:8080')
    MAIN_BOT_API_KEY = os.getenv('MAIN_BOT_API_KEY')

    # Admin Settings
    ADMIN_TELEGRAM_IDS = [
        int(admin_id) for admin_id in
        os.getenv('ADMIN_TELEGRAM_IDS', '').split(',')
        if admin_id.strip()
    ]
    ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')  # Канал для сповіщень

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

        if not cls.ADMIN_TELEGRAM_IDS:
            errors.append("No admin Telegram IDs configured")

        return errors

    @classmethod
    def get_webhook_url(cls) -> str:
        """Повертає повний URL для webhook"""
        if not cls.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{cls.TELEGRAM_WEBHOOK_URL.rstrip('/')}{cls.WEBHOOK_PATH}"

    @classmethod
    def get_cryptobot_webhook_url(cls) -> str:
        """Повертає URL для CryptoBot webhook"""
        if not cls.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{cls.TELEGRAM_WEBHOOK_URL.rstrip('/')}{cls.CRYPTOBOT_WEBHOOK_PATH}"


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