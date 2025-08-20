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
    'welcome': f"{EMOJI['rocket']} <b>Вітаємо в SocialBoost Bot!</b>\\n\\nОберіть пакет для розкрутки ваших постів:",
    'packages_header': f"{EMOJI['package']} <b>Доступні пакети:</b>",
    'order_created': f"{EMOJI['check']} Замовлення створено!\\n\\n{EMOJI['money']} Сума: <b>{{amount}} {{currency}}</b>\\n{EMOJI['package']} Пакет: <b>{{package_name}}</b>",
    'payment_success': f"{EMOJI['check']} <b>Оплата успішна!</b>\\n\\nВаш пакет активовано.",
    'add_post_prompt': f"{EMOJI['link']} Надішліть посилання на ваш пост:",
    'post_added': f"{EMOJI['check']} <b>Пост додано!</b>",
    'limit_reached': f"{EMOJI['warning']} <b>Ліміт вичерпано!</b>\\n\\nВи досягли денного ліміту постів.",
    'no_active_package': f"{EMOJI['info']} У вас немає активного пакету. Оберіть пакет для початку роботи:",
    'invalid_url': f"{EMOJI['cross']} Невірне посилання. Будь ласка, надішліть правильний URL.",
    'admin_notification': f"{EMOJI['bell']} <b>Нове замовлення!</b>\\n\\n{EMOJI['admin']} Користувач: {{username}}\\n{EMOJI['money']} Сума: {{amount}} {{currency}}\\n{EMOJI['package']} Пакет: {{package_name}}\\n{EMOJI['time']} Час: {{time}}"
}

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
    'telegram': r'https?://t\\.me/\\w+/\\d+',
    'instagram': r'https?://(?:www\\.)?instagram\\.com/p/[\\w-]+',
    'tiktok': r'https?://(?:www\\.)?tiktok\\.com/@[\\w.]+/video/\\d+',
    'youtube': r'https?://(?:www\\.)?youtube\\.com/watch\\?v=[\\w-]+'
}