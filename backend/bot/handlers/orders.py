# backend/bot/handlers/orders.py
"""
Обробники для додавання постів
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog

from backend.bot.keyboards.inline import KeyboardBuilder
from backend.bot.states.user_states import UserStates
from backend.services.user_service import UserService
from backend.services.external_service import ExternalService
from backend.services.order_service import OrderService
from backend.utils.constants import MESSAGES, EMOJI
from backend.utils.validators import validate_post_url

router = Router()
logger = structlog.get_logger(__name__)


@router.callback_query(F.data == "add_post")
async def start_add_post(callback: CallbackQuery, state: FSMContext):
    """Початок додавання поста"""
    try:
        # Перевіряємо чи є у користувача активний пакет
        user_stats = await UserService.get_user_stats_fresh(str(callback.from_user.id))

        current_package = user_stats.get('current_package')
        if not current_package:
            packages = await OrderService.get_packages()
            await callback.message.edit_text(
                MESSAGES['no_active_package'],
                reply_markup=KeyboardBuilder.packages_menu(packages),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Перевіряємо ліміт постів
        posts_remaining = current_package.get('posts_remaining', 0)
        if posts_remaining <= 0:
            await callback.message.edit_text(
                MESSAGES['limit_reached'],
                reply_markup=KeyboardBuilder.main_menu(),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        await state.set_state(UserStates.SELECTING_PLATFORM)

        await callback.message.edit_text(
            f"{EMOJI['link']} <b>Вибір платформи</b>\n\nОберіть платформу вашого поста:",
            reply_markup=KeyboardBuilder.post_platform_selection(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error starting add post for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при додаванні поста")


@router.callback_query(F.data.startswith("platform_"))
async def select_platform(callback: CallbackQuery, state: FSMContext):
    """Вибір платформи"""
    try:
        platform = callback.data.replace("platform_", "")
        await state.update_data(selected_platform=platform)
        await state.set_state(UserStates.WAITING_POST_URL)

        platform_names = {
            'telegram': 'Telegram',
            'instagram': 'Instagram',
            'tiktok': 'TikTok',
            'youtube': 'YouTube'
        }

        platform_name = platform_names.get(platform, platform)

        await callback.message.edit_text(
            f"{EMOJI['link']} <b>Додавання поста {platform_name}</b>\n\n"
            f"Надішліть посилання на ваш пост:",
            reply_markup=KeyboardBuilder.cancel_action(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error selecting platform", error=str(e))
        await callback.answer("Помилка при виборі платформи")


@router.message(UserStates.WAITING_POST_URL)
async def process_post_url(message: Message, state: FSMContext):
    """Обробка URL поста"""
    try:
        url = message.text.strip()
        state_data = await state.get_data()
        selected_platform = state_data.get('selected_platform', 'telegram')

        # Валідуємо URL
        is_valid, detected_platform = validate_post_url(url)

        if not is_valid:
            await message.answer(
                MESSAGES['invalid_url'],
                reply_markup=KeyboardBuilder.cancel_action(),
                parse_mode="HTML"
            )
            return

        # Використовуємо обрану платформу або автоматично визначену
        final_platform = detected_platform or selected_platform

        await state.set_state(UserStates.PROCESSING_POST)

        # Показуємо повідомлення про обробку
        processing_msg = await message.answer(
            f"{EMOJI['time']} <b>Обробка поста...</b>\n\nБудь ласка, зачекайте.",
            parse_mode="HTML"
        )

        # Додаємо пост через сервіс
        result = await ExternalService.add_post_for_processing(
            str(message.from_user.id),
            url,
            final_platform
        )

        if result.get('success'):
            success_text = f"{EMOJI['check']} <b>Пост успішно додано!</b>\n\n"
            success_text += f"{EMOJI['link']} URL: {url}\n"
            success_text += f"{EMOJI['settings']} Платформа: {final_platform.title()}\n\n"
            success_text += f"{EMOJI['rocket']} Накрутка розпочнеться незабаром!"

            await processing_msg.edit_text(
                success_text,
                reply_markup=KeyboardBuilder.main_menu(),
                parse_mode="HTML"
            )

            # Очищаємо кеш користувача
            await UserService.invalidate_cache(str(message.from_user.id))

        else:
            error_text = f"{EMOJI['cross']} <b>Помилка!</b>\n\n"
            error_text += result.get('error', 'Невідома помилка')

            await processing_msg.edit_text(
                error_text,
                reply_markup=KeyboardBuilder.main_menu(),
                parse_mode="HTML"
            )

        await state.set_state(UserStates.MAIN_MENU)

    except Exception as e:
        logger.error(f"Error processing post URL for user {message.from_user.id}",
                     error=str(e), url=url)
        await message.answer(
            f"{EMOJI['cross']} Сталася помилка при обробці поста.",
            reply_markup=KeyboardBuilder.main_menu(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "cancel_action")
async def cancel_current_action(callback: CallbackQuery, state: FSMContext):
    """Скасування поточної дії"""
    try:
        await state.set_state(UserStates.MAIN_MENU)

        await callback.message.edit_text(
            f"{EMOJI['info']} Дію скасовано.",
            reply_markup=KeyboardBuilder.main_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error canceling action", error=str(e))
        await callback.answer("Помилка при скасуванні дії")