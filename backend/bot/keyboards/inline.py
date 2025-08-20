"""
Inline клавіатури для Telegram бота
"""
from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from backend.utils.constants import EMOJI, CALLBACK_DATA


class KeyboardBuilder:
    """Клас для створення клавіатур"""

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Головне меню бота"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['package']} Вибрати пакет",
                callback_data="select_packages"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['link']} Додати пост",
                callback_data=CALLBACK_DATA['add_post']
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['chart']} Моя статистика",
                callback_data=CALLBACK_DATA['my_stats']
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['settings']} Підтримка",
                callback_data=CALLBACK_DATA['support']
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def packages_menu(packages: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """Меню вибору пакетів"""
        buttons = []

        # Групуємо пакети за категоріями
        categories = {
            'starter': [],
            'professional': [],
            'enterprise': []
        }

        for package in packages:
            category = package.get('category', 'starter')
            if category in categories:
                categories[category].append(package)

        # Додаємо кнопки для кожної категорії
        category_names = {
            'starter': f"{EMOJI['star']} STARTER",
            'professional': f"{EMOJI['fire']} PROFESSIONAL",
            'enterprise': f"{EMOJI['rocket']} ENTERPRISE"
        }

        for category, packages_list in categories.items():
            if packages_list:
                # Заголовок категорії
                buttons.append([InlineKeyboardButton(
                    text=f"━━━ {category_names[category]} ━━━",
                    callback_data="category_header"
                )])

                # Пакети в категорії
                for package in packages_list:
                    price_text = f"{package['price']:.0f}$"
                    text = f"{package['name']} - {price_text}"

                    buttons.append([InlineKeyboardButton(
                        text=text,
                        callback_data=CALLBACK_DATA['select_package'].format(package['slug'])
                    )])

        # Кнопка назад
        buttons.append([InlineKeyboardButton(
            text="« Назад до меню",
            callback_data="back_to_menu"
        )])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def package_details(package: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Детальна інформація про пакет"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['money']} Купити за {package['price']:.0f}$ {package['currency']}",
                callback_data=CALLBACK_DATA['confirm_order'].format(package['slug'])
            )],
            [InlineKeyboardButton(
                text="« Назад до пакетів",
                callback_data="select_packages"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def order_confirmation(order_data: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Підтвердження замовлення"""
        order_id = order_data.get('order_id')

        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['money']} Оплатити",
                callback_data=f"pay_{order_id}"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['cross']} Скасувати",
                callback_data=CALLBACK_DATA['cancel_order'].format(order_id)
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def payment_invoice(pay_url: str) -> InlineKeyboardMarkup:
        """Кнопка для оплати"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['money']} Оплатити зараз",
                url=pay_url
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['info']} Перевірити оплату",
                callback_data="check_payment"
            )],
            [InlineKeyboardButton(
                text="« Назад до меню",
                callback_data="back_to_menu"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def user_stats_menu() -> InlineKeyboardMarkup:
        """Меню статистики користувача"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['link']} Додати пост",
                callback_data=CALLBACK_DATA['add_post']
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['package']} Вибрати пакет",
                callback_data="select_packages"
            )],
            [InlineKeyboardButton(
                text="« Головне меню",
                callback_data="back_to_menu"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def post_platform_selection() -> InlineKeyboardMarkup:
        """Вибір платформи для поста"""
        buttons = [
            [InlineKeyboardButton(
                text="📱 Telegram",
                callback_data="platform_telegram"
            )],
            [InlineKeyboardButton(
                text="📷 Instagram",
                callback_data="platform_instagram"
            )],
            [InlineKeyboardButton(
                text="🎵 TikTok",
                callback_data="platform_tiktok"
            )],
            [InlineKeyboardButton(
                text="📺 YouTube",
                callback_data="platform_youtube"
            )],
            [InlineKeyboardButton(
                text="« Назад",
                callback_data="back_to_menu"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """Адмін панель"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['chart']} Статистика системи",
                callback_data="admin_stats"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['package']} Керування пакетами",
                callback_data="admin_packages"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['bell']} Розсилка",
                callback_data="admin_broadcast"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['settings']} Налаштування",
                callback_data="admin_settings"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def support_menu() -> InlineKeyboardMarkup:
        """Меню підтримки"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['admin']} Зв'язатися з підтримкою",
                url="https://t.me/support_username"  # Замінити на реальний
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['info']} FAQ",
                callback_data="show_faq"
            )],
            [InlineKeyboardButton(
                text="« Головне меню",
                callback_data="back_to_menu"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def cancel_action() -> InlineKeyboardMarkup:
        """Кнопка скасування дії"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['cross']} Скасувати",
                callback_data="cancel_action"
            )]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_package_info(package: Dict[str, Any]) -> str:
    """Форматує інформацію про пакет"""
    features = package.get('features', {})

    text = f"""
{EMOJI['package']} <b>{package['name']}</b>

💰 <b>Ціна:</b> {package['price']:.0f} {package['currency']}/місяць

📊 <b>Показники на 1 пост:</b>
• 👀 Перегляди: {package['views_range']}
• ❤️ Реакції: {package['reactions_range']}
• 💬 Коментарі: {package['comments_range']}
• 🔄 Репости: {package['reposts_range']}

⚙️ <b>Налаштування:</b>
• 📝 Постів на день: {package['posts_per_day']}
• 🎲 Рандомізація: {features.get('randomization', '30%')}
• ⚡ {features.get('immediate_delivery', '80% за 24 години')}
• 📈 {features.get('delayed_delivery', '20% протягом тижня')}

📝 {package['description']}
"""

    return text.strip()


def format_user_stats(stats: Dict[str, Any]) -> str:
    """Форматує статистику користувача"""
    current_package = stats.get('current_package')

    text = f"""
{EMOJI['chart']} <b>Ваша статистика</b>

👤 <b>Користувач:</b> {stats.get('username', 'Не вказано')}
💰 <b>Баланс:</b> {stats.get('balance', 0):.2f}$
💳 <b>Всього витрачено:</b> {stats.get('total_spent', 0):.2f}$

📦 <b>Замовлення:</b> {stats.get('orders_count', 0)}
📝 <b>Всього постів:</b> {stats.get('posts_count', 0)}
⚡ <b>Активних постів:</b> {stats.get('active_posts', 0)}
"""

    if current_package:
        text += f"""
🎯 <b>Поточний пакет:</b> {current_package['name']}
📅 <b>Діє до:</b> {current_package.get('expires_at', 'Не вказано')[:10]}
📊 <b>Постів сьогодні:</b> {current_package.get('posts_used_today', 0)}/{current_package.get('posts_per_day', 0)}
"""
    else:
        text += f"\n{EMOJI['info']} У вас немає активного пакету"

    return text.strip()