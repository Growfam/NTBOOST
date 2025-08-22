#!/usr/bin/env python3
"""
SocialBoost Bot з webhook для оплат
"""
import os
import asyncio
import logging
import requests
import threading
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Завантажуємо .env
load_dotenv()

# Глобальні змінні
bot = None
user_orders = {}  # Тимчасове зберігання замовлень


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


# Flask app для webhook
app = Flask(__name__)


@app.route('/webhook/cryptobot', methods=['POST'])
def cryptobot_webhook():
    """Webhook для обробки платежів CryptoBot"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data'}), 400

        print(f"💰 Webhook received: {data}")

        # Перевіряємо тип оновлення
        if data.get('update_type') == 'invoice_paid':
            invoice = data.get('payload', {})
            payload = invoice.get('payload', '')
            status = invoice.get('status')
            amount = invoice.get('amount')

            if status == 'paid' and payload:
                # Розбираємо payload: user_id_package_slug_message_id
                parts = payload.split('_')
                if len(parts) >= 2:
                    user_id = parts[0]
                    package_slug = parts[1]

                    print(f"✅ Payment confirmed for user {user_id}, package {package_slug}")

                    # Зберігаємо успішну оплату
                    user_orders[user_id] = {
                        'package_slug': package_slug,
                        'amount': amount,
                        'status': 'paid'
                    }

                    # Відправляємо повідомлення користувачу
                    asyncio.create_task(notify_payment_success(user_id, package_slug, amount))

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500


async def notify_payment_success(user_id, package_slug, amount):
    """Сповіщає користувача про успішну оплату"""
    try:
        if bot:
            # Отримуємо назву пакету
            package_names = {
                'starter-mini': 'Starter Mini',
                'pro-advanced': 'Pro Advanced',
                'enterprise-elite': 'Enterprise Elite'
            }

            package_name = package_names.get(package_slug, 'Unknown Package')

            success_text = f"""
🎉 <b>Оплата успішна!</b>

📦 <b>Пакет:</b> {package_name}
💰 <b>Сума:</b> ${amount} USDT

✅ Ваш пакет активовано! Тепер ви можете додавати пости для накрутки.

Натисніть /start щоб продовжити.
"""

            await bot.send_message(
                chat_id=int(user_id),
                text=success_text,
                parse_mode="HTML"
            )

            print(f"✅ Payment notification sent to user {user_id}")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")


def run_flask():
    """Запускає Flask в окремому потоці"""
    print("🌐 Flask webhook server starting on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)


async def main():
    try:
        global bot

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

        # Запускаємо Flask в окремому потоці
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Пакети
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
            user_id = str(message.from_user.id)

            # Перевіряємо чи є активний пакет
            active_package = user_orders.get(user_id)

            if active_package and active_package.get('status') == 'paid':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Додати пост", callback_data="add_post")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                    [InlineKeyboardButton(text="📦 Вибрати новий пакет", callback_data="packages")]
                ])

                welcome_text = f"""
🚀 <b>Вітаємо в SocialBoost Bot!</b>

✅ У вас активний пакет! Можете додавати пости для накрутки.

Оберіть дію з меню нижче:
"""
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Вибрати пакет", callback_data="packages")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
                ])

                welcome_text = """
🚀 <b>Вітаємо в SocialBoost Bot!</b>

💰 Оберіть пакет та оплатіть щоб почати!

Оберіть дію з меню нижче:
"""

            await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

        @dp.callback_query()
        async def handle_callback(callback: CallbackQuery):
            user_id = str(callback.from_user.id)

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
                # Деталі пакету (код такий же як раніше)
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
💳 <b>Оплата:</b> Автоматично через CryptoBot
"""

                    await callback.message.edit_text(
                        package_text,
                        reply_markup=buy_keyboard,
                        parse_mode="HTML"
                    )

            elif callback.data.startswith("buy_"):
                # Створення рахунку для оплати (код такий же)
                package_slug = callback.data.replace("buy_", "")
                package = PACKAGES.get(package_slug)

                if package:
                    payload = f"{callback.from_user.id}_{package_slug}_{callback.message.message_id}"

                    invoice = crypto_api.create_invoice(
                        amount=package['price'],
                        description=f"SocialBoost - {package['name']}",
                        payload=payload
                    )

                    if invoice:
                        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💳 Оплатити зараз", url=invoice['pay_url'])],
                            [InlineKeyboardButton(text="« Назад", callback_data="packages")]
                        ])

                        payment_text = f"""
💳 <b>Оплата замовлення</b>

📦 Пакет: <b>{package['name']}</b>
💰 Сума: <b>${package['price']:.0f} USDT</b>

🔗 Натисніть "Оплатити зараз" для переходу до оплати.

✅ <b>Після оплати пакет активується автоматично!</b>

⏱️ Рахунок дійсний 1 годину.
"""

                        await callback.message.edit_text(
                            payment_text,
                            reply_markup=payment_keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        await callback.answer("❌ Помилка створення рахунку. Спробуйте пізніше.", show_alert=True)

            elif callback.data == "add_post":
                # Додавання поста
                active_package = user_orders.get(user_id)

                if active_package and active_package.get('status') == 'paid':
                    await callback.message.edit_text(
                        "🔗 <b>Додавання поста</b>\n\n"
                        "Надішліть посилання на ваш пост і ми розпочнемо накрутку!\n\n"
                        "Підтримувані платформи:\n"
                        "• Telegram\n• Instagram\n• TikTok\n• YouTube",
                        parse_mode="HTML"
                    )
                else:
                    await callback.answer("❗ Спочатку оберіть та оплатіть пакет!", show_alert=True)

            elif callback.data == "stats":
                # Статистика
                active_package = user_orders.get(user_id)

                if active_package and active_package.get('status') == 'paid':
                    package_names = {
                        'starter-mini': 'Starter Mini',
                        'pro-advanced': 'Pro Advanced',
                        'enterprise-elite': 'Enterprise Elite'
                    }

                    package_name = package_names.get(active_package['package_slug'], 'Unknown')

                    stats_text = f"""
📊 <b>Ваша статистика:</b>

👤 Користувач: @{callback.from_user.username or 'Невідомо'}
💰 Витрачено: ${active_package['amount']} USDT
📦 Активний пакет: {package_name}
📝 Постів оброблено: 0

✅ Пакет активний! Додавайте пости для накрутки.
"""
                else:
                    stats_text = f"""
📊 <b>Ваша статистика:</b>

👤 Користувач: @{callback.from_user.username or 'Невідомо'}
💰 Витрачено: $0.00
📦 Активний пакет: Немає
📝 Постів оброблено: 0

💡 Оберіть пакет щоб почати!
"""

                back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(stats_text, reply_markup=back_keyboard, parse_mode="HTML")

            elif callback.data == "back":
                # Повернення до головного меню
                await start_command(callback.message)

            await callback.answer()

        print("🚀 Бот з webhook запущений!")
        print(f"✅ Bot Token: {bot_token[:10]}...")
        print(f"✅ CryptoBot Token: {crypto_token[:10]}...")
        print("💳 Webhook готовий приймати платежі!")
        print("🌐 Webhook URL: http://localhost:5000/webhook/cryptobot")

        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())