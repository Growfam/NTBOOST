# backend/bot/handlers/start.py
"""
Обробники команди /start та головного меню
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import structlog

from backend.bot.keyboards.inline import KeyboardBuilder, format_user_stats
from backend.bot.states.user_states import UserStates
from backend.services.user_service import UserService
from backend.utils.constants import MESSAGES, EMOJI

router = Router()
logger = structlog.get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обробка команди /start"""
    try:
        user = message.from_user

        # Створюємо або отримуємо користувача
        user_stats = await UserService.get_or_create_user(
            telegram_id=str(user.id),
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        if user_stats.get('error'):
            await message.answer(f"{EMOJI['cross']} Помилка при реєстрації. Спробуйте пізніше.")
            return

        # Встановлюємо стан головного меню
        await state.set_state(UserStates.MAIN_MENU)

        # Відправляємо привітання
        await message.answer(
            MESSAGES['welcome'],
            reply_markup=KeyboardBuilder.main_menu(),
            parse_mode="HTML"
        )

        logger.info(f"User {user.id} started bot", username=user.username)

    except Exception as e:
        logger.error(f"Error in start command for user {user.id}", error=str(e))
        await message.answer(f"{EMOJI['cross']} Сталася помилка. Спробуйте пізніше.")


@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Повернення до головного меню"""
    try:
        await state.set_state(UserStates.MAIN_MENU)

        await callback.message.edit_text(
            MESSAGES['welcome'],
            reply_markup=KeyboardBuilder.main_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error returning to menu for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при поверненні до меню")


@router.callback_query(F.data == "my_stats")
async def show_user_stats(callback: CallbackQuery, state: FSMContext):
    """Показ статистики користувача"""
    try:
        user_stats = await UserService.get_user_stats_fresh(str(callback.from_user.id))

        if user_stats.get('error'):
            await callback.answer("Помилка при отриманні статистики")
            return

        stats_text = format_user_stats(user_stats)

        await callback.message.edit_text(
            stats_text,
            reply_markup=KeyboardBuilder.user_stats_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing stats for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при отриманні статистики")


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery, state: FSMContext):
    """Показ меню підтримки"""
    try:
        support_text = f"""
{EMOJI['settings']} <b>Підтримка</b>

Якщо у вас виникли питання або проблеми, ви можете:

{EMOJI['admin']} Зв'язатися з нашою підтримкою
{EMOJI['info']} Переглянути часті питання

Ми готові допомогти вам 24/7!
"""

        await callback.message.edit_text(
            support_text,
            reply_markup=KeyboardBuilder.support_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing support for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при відображенні підтримки")


@router.callback_query(F.data == "show_faq")
async def show_faq(callback: CallbackQuery, state: FSMContext):
    """Показ FAQ"""
    try:
        faq_text = f"""
{EMOJI['info']} <b>Часті питання (FAQ)</b>

<b>❓ Як працює сервіс?</b>
Ви обираєте пакет, оплачуєте його та додаєте посилання на свої пости для розкрутки.

<b>❓ Які платформи підтримуються?</b>
Telegram, Instagram, TikTok, YouTube.

<b>❓ Як довго триває розкрутка?</b>
Залежить від пакету - зазвичай від кількох годин до тижня.

<b>❓ Безпечно це?</b>
Так, ми використовуємо тільки безпечні методи просування.

<b>❓ Можна повернути гроші?</b>
Повернення можливе до початку обробки замовлення.
"""

        await callback.message.edit_text(
            faq_text,
            reply_markup=KeyboardBuilder.support_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing FAQ for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при відображенні FAQ")