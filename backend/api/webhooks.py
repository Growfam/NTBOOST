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

    # Admin Settings - виправлена обробка
    @property
    def ADMIN_TELEGRAM_IDS(self) -> List[int]:
        """Повертає список ID адмінів"""
        admin_ids_str = os.getenv('ADMIN_TELEGRAM_IDS', '')
        if not admin_ids_str.strip():
            return []
        
        try:
            return [
                int(admin_id.strip()) 
                for admin_id in admin_ids_str.split(',')
                if admin_id.strip().isdigit()
            ]
        except (ValueError, AttributeError):
            return []

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
        config_instance = cls()

        required_vars = [
            ('TELEGRAM_BOT_TOKEN', config_instance.TELEGRAM_BOT_TOKEN),
            ('SUPABASE_URL', config_instance.SUPABASE_URL),
            ('SUPABASE_KEY', config_instance.SUPABASE_KEY),
            ('CRYPTOBOT_TOKEN', config_instance.CRYPTOBOT_TOKEN),
        ]

        for var_name, var_value in required_vars:
            if not var_value:
                errors.append(f"Missing required environment variable: {var_name}")

        if not config_instance.ADMIN_TELEGRAM_IDS:
            errors.append("No admin Telegram IDs configured")

        # Перевіряємо валідність MAIN_BOT_API_URL якщо вказаний
        if config_instance.MAIN_BOT_API_URL and not config_instance.MAIN_BOT_API_URL.startswith(('http://', 'https://')):
            errors.append("MAIN_BOT_API_URL must start with http:// or https://")

        return errors

    @classmethod
    def get_webhook_url(cls) -> Optional[str]:
        """Повертає повний URL для webhook"""
        config_instance = cls()
        if not config_instance.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{config_instance.TELEGRAM_WEBHOOK_URL.rstrip('/')}{config_instance.WEBHOOK_PATH}"

    @classmethod
    def get_cryptobot_webhook_url(cls) -> Optional[str]:
        """Повертає URL для CryptoBot webhook"""
        config_instance = cls()
        if not config_instance.TELEGRAM_WEBHOOK_URL:
            return None
        return f"{config_instance.TELEGRAM_WEBHOOK_URL.rstrip('/')}{config_instance.CRYPTOBOT_WEBHOOK_PATH}"


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