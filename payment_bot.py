#!/usr/bin/env python3
"""
SocialBoost Bot з платежами
"""
import os
import asyncio
import logging
import requests
from dotenv import load_dotenv

# Завантажуємо .env
load_dotenv()


class CryptoPayAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"

    def create_invoice(self, amount, description, payload=None):
        """Створює рахунок для оплати"""
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }

        data = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description,
            "payload": payload or "",
            "expires_in": 3600  # 1 година
        }

        try:
            response = requests.post(
                f"{self.base_url}/createInvoice",
                json=data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return result.get("result")

            print(f"CryptoBot API Error: {response.text}")
            return None

        except Exception as e:
            print(f"Error creating invoice: {e}")
            return None


async def main():
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.filters import CommandStart

        # Налаштовуємо логування
        logging.basicConfig(level=logging.INFO)

        # Токени
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        crypto_token = os.getenv('CRYPTOBOT_TOKEN')

        if not bot_token or not crypto_token:
            print("❌ Токени не знайдено в .env файлі!")
            return

        # Створюємо бота та CryptoBot API
        bot = Bot(token=bot_token)
        dp = Dispatcher()
        crypto_api = CryptoPayAPI(crypto_token)

        # Пакети (тимчасово в коді)
        PACKAGES = {
            'starter-mini': {
                'name': 'Starter Mini',
                'price': 99.99,
                'description': '2 пости в день | Для початківців',
                'features': '• 1,000-2,500 переглядів\n• 15-27 реакцій\n• 5-15 коментарів'
            },
            'pro-advanced': {
                'name': 'Pro Advanced',
                'price': 299.99,
                'description': '3 пости в день | Розширений пакет',
                'features': '• 8,000-15,000 переглядів\n• 60-120 реакцій\n• 35-65 коментарів'
            },
            'enterprise-elite': {
                'name': 'Enterprise Elite',
                'price': 999.99,
                'description': '3 пости в день | Найпотужніший пакет',
                'features': '• 70,000-120,000 переглядів\n• 400-700 реакцій\n• 84-120 коментарів'
            }
        }

        @dp.message(CommandStart())
        async def start_command(message: Message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Вибрати пакет", callback_data="packages")],
                [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                [InlineKeyboardButton(text="🔗 Додати пост", callback_data="add_post")]
            ])

            await message.answer(
                "🚀 <b>Вітаємо в SocialBoost Bot!</b>\n\n"
                "💰 Тепер з можливістю оплати через CryptoBot!\n\n"
                "Оберіть дію з меню нижче:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        @dp.callback_query()
        async def handle_callback(callback: CallbackQuery):
            if callback.data == "packages":
                # Меню пакетів
                packages_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"🥉 {PACKAGES['starter-mini']['name']} - ${PACKAGES['starter-mini']['price']:.0f}",
                        callback_data="pkg_starter-mini")],
                    [InlineKeyboardButton(
                        text=f"🥈 {PACKAGES['pro-advanced']['name']} - ${PACKAGES['pro-advanced']['price']:.0f}",
                        callback_data="pkg_pro-advanced")],
                    [InlineKeyboardButton(
                        text=f"🥇 {PACKAGES['enterprise-elite']['name']} - ${PACKAGES['enterprise-elite']['price']:.0f}",
                        callback_data="pkg_enterprise-elite")],
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "📦 <b>Доступні пакети:</b>\n\n"
                    "Оберіть пакет для деталей та оплати:",
                    reply_markup=packages_keyboard,
                    parse_mode="HTML"
                )

            elif callback.data.startswith("pkg_"):
                # Деталі пакету
                package_slug = callback.data.replace("pkg_", "")
                package = PACKAGES.get(package_slug)

                if package:
                    buy_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"💳 Купити за ${package['price']:.0f}",
                                              callback_data=f"buy_{package_slug}")],
                        [InlineKeyboardButton(text="« Назад до пакетів", callback_data="packages")]
                    ])

                    package_text = f"""
📦 <b>{package['name']}</b>

💰 <b>Ціна:</b> ${package['price']:.0f} USD/місяць

📝 <b>Опис:</b> {package['description']}

📊 <b>Що включено:</b>
{package['features']}

🎯 <b>Природність:</b> ±30% рандомізація
⚡ <b>Швидкість:</b> 80% за 24 години
"""

                    await callback.message.edit_text(
                        package_text,
                        reply_markup=buy_keyboard,
                        parse_mode="HTML"
                    )

            elif callback.data.startswith("buy_"):
                # Створення рахунку для оплати
                package_slug = callback.data.replace("buy_", "")
                package = PACKAGES.get(package_slug)

                if package:
                    # Створюємо унікальний payload для цього замовлення
                    payload = f"{callback.from_user.id}_{package_slug}_{callback.message.message_id}"

                    # Створюємо рахунок в CryptoBot
                    invoice = crypto_api.create_invoice(
                        amount=package['price'],
                        description=f"SocialBoost - {package['name']}",
                        payload=payload
                    )

                    if invoice:
                        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💳 Оплатити зараз", url=invoice['pay_url'])],
                            [InlineKeyboardButton(text="🔄 Перевірити оплату",
                                                  callback_data=f"check_{invoice['invoice_id']}")],
                            [InlineKeyboardButton(text="« Назад", callback_data="packages")]
                        ])

                        payment_text = f"""
💳 <b>Оплата замовлення</b>

📦 Пакет: <b>{package['name']}</b>
💰 Сума: <b>${package['price']:.0f} USDT</b>

🔗 Натисніть "Оплатити зараз" для переходу до оплати.

⏱️ Рахунок дійсний 1 годину.
"""

                        await callback.message.edit_text(
                            payment_text,
                            reply_markup=payment_keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        await callback.answer("❌ Помилка створення рахунку. Спробуйте пізніше.", show_alert=True)

            elif callback.data.startswith("check_"):
                # Перевірка статусу оплати (тимчасово заглушка)
                await callback.answer("🔄 Перевірка оплати... (в розробці)", show_alert=True)

            elif callback.data == "stats":
                stats_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "📊 <b>Ваша статистика:</b>\n\n"
                    f"👤 Користувач: @{callback.from_user.username or 'Невідомо'}\n"
                    "💰 Баланс: $0.00\n"
                    "📝 Постів: 0\n"
                    "📦 Активний пакет: Немає\n\n"
                    "💡 Оберіть пакет щоб почати!",
                    reply_markup=stats_keyboard,
                    parse_mode="HTML"
                )

            elif callback.data == "add_post":
                back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "🔗 <b>Додавання поста</b>\n\n"
                    "❗ Спочатку оберіть та оплатіть пакет у меню 'Вибрати пакет'.\n\n"
                    "Після оплати ви зможете додавати пости для накрутки.",
                    reply_markup=back_keyboard,
                    parse_mode="HTML"
                )

            elif callback.data == "back":
                # Головне меню
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Вибрати пакет", callback_data="packages")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                    [InlineKeyboardButton(text="🔗 Додати пост", callback_data="add_post")]
                ])

                await callback.message.edit_text(
                    "🚀 <b>Вітаємо в SocialBoost Bot!</b>\n\n"
                    "💰 Тепер з можливістю оплати через CryptoBot!\n\n"
                    "Оберіть дію з меню нижче:",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            await callback.answer()

        print("🚀 Бот з платежами запущений!")
        print(f"✅ Bot Token: {bot_token[:10]}...")
        print(f"✅ CryptoBot Token: {crypto_token[:10]}...")
        print("💳 Тестуйте платежі!")

        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())