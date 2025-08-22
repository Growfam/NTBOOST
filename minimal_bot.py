#!/usr/bin/env python3
"""
Мінімальний бот для тесту
"""
import os
import asyncio
import logging
from dotenv import load_dotenv

# Завантажуємо .env
load_dotenv()


async def main():
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.filters import CommandStart

        # Налаштовуємо логування
        logging.basicConfig(level=logging.INFO)

        # Створюємо бота
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            print("❌ TELEGRAM_BOT_TOKEN не знайдено в .env файлі!")
            return

        bot = Bot(token=bot_token)
        dp = Dispatcher()

        @dp.message(CommandStart())
        async def start_command(message: Message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Вибрати пакет", callback_data="packages")],
                [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                [InlineKeyboardButton(text="🔗 Додати пост", callback_data="add_post")]
            ])

            await message.answer(
                "🚀 <b>Вітаємо в SocialBoost Bot!</b>\n\n"
                "Оберіть дію з меню нижче:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        @dp.callback_query()
        async def handle_callback(callback):
            if callback.data == "packages":
                packages_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🥉 Starter Mini - $99.99", callback_data="pkg_starter")],
                    [InlineKeyboardButton(text="🥈 Pro Advanced - $299.99", callback_data="pkg_pro")],
                    [InlineKeyboardButton(text="🥇 Enterprise Elite - $999.99", callback_data="pkg_enterprise")],
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "📦 <b>Доступні пакети:</b>\n\n"
                    "Оберіть пакет для деталей:",
                    reply_markup=packages_keyboard,
                    parse_mode="HTML"
                )
            elif callback.data == "stats":
                stats_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "📊 <b>Ваша статистика:</b>\n\n"
                    f"👤 Користувач: @{callback.from_user.username or 'Невідомо'}\n"
                    "💰 Баланс: $0.00\n"
                    "📝 Постів: 0\n"
                    "📦 Активний пакет: Немає",
                    reply_markup=stats_keyboard,
                    parse_mode="HTML"
                )
            elif callback.data == "add_post":
                back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="back")]
                ])

                await callback.message.edit_text(
                    "🔗 <b>Додавання поста</b>\n\n"
                    "Спочатку оберіть та оплатіть пакет у меню 'Вибрати пакет'.",
                    reply_markup=back_keyboard,
                    parse_mode="HTML"
                )
            elif callback.data.startswith("pkg_"):
                await callback.message.edit_text(
                    "💳 <b>Деталі пакету</b>\n\n"
                    "Для повноцінного функціонала потрібна інтеграція з CryptoBot.\n\n"
                    "Тестова версія працює! ✅",
                    parse_mode="HTML"
                )
            elif callback.data == "back":
                # Повертаємось до головного меню
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Вибрати пакет", callback_data="packages")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                    [InlineKeyboardButton(text="🔗 Додати пост", callback_data="add_post")]
                ])

                await callback.message.edit_text(
                    "🚀 <b>Вітаємо в SocialBoost Bot!</b>\n\n"
                    "Оберіть дію з меню нижче:",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            await callback.answer()

        print("🚀 Мінімальний бот запущений!")
        print(f"✅ Токен: {bot_token[:10]}...")
        print("🔍 Шукайте свого бота в Telegram і пишіть /start")

        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())