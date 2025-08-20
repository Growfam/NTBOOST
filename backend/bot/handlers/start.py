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


# ===================================

# backend/bot/handlers/packages.py
"""
Обробники для роботи з пакетами
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog

from backend.bot.keyboards.inline import KeyboardBuilder, format_package_info
from backend.bot.states.user_states import UserStates
from backend.services.order_service import OrderService
from backend.services.payment_service import PaymentService
from backend.utils.constants import MESSAGES, EMOJI

router = Router()
logger = structlog.get_logger(__name__)


@router.callback_query(F.data == "select_packages")
async def show_packages(callback: CallbackQuery, state: FSMContext):
    """Показ списку пакетів"""
    try:
        packages = await OrderService.get_packages()

        if not packages:
            await callback.answer("Пакети тимчасово недоступні")
            return

        await state.set_state(UserStates.SELECTING_PACKAGE)

        await callback.message.edit_text(
            MESSAGES['packages_header'],
            reply_markup=KeyboardBuilder.packages_menu(packages),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing packages for user {callback.from_user.id}", error=str(e))
        await callback.answer("Помилка при завантаженні пакетів")


@router.callback_query(F.data.startswith("pkg_"))
async def show_package_details(callback: CallbackQuery, state: FSMContext):
    """Показ деталей пакету"""
    try:
        package_slug = callback.data.replace("pkg_", "")
        package = await OrderService.get_package_by_slug(package_slug)

        if not package:
            await callback.answer("Пакет не знайдено")
            return

        await state.set_state(UserStates.VIEWING_PACKAGE_DETAILS)
        await state.update_data(selected_package=package_slug)

        package_text = format_package_info(package)

        await callback.message.edit_text(
            package_text,
            reply_markup=KeyboardBuilder.package_details(package),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing package details", error=str(e), package_slug=package_slug)
        await callback.answer("Помилка при завантаженні деталей пакету")


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    """Підтвердження замовлення"""
    try:
        package_slug = callback.data.replace("confirm_", "")

        # Створюємо замовлення
        order_result = await OrderService.create_new_order(
            str(callback.from_user.id),
            package_slug
        )

        if not order_result.get('success'):
            await callback.answer(f"Помилка: {order_result.get('error', 'Невідома помилка')}")
            return

        await state.set_state(UserStates.CONFIRMING_ORDER)
        await state.update_data(order_data=order_result)

        # Форматуємо повідомлення про замовлення
        order_text = MESSAGES['order_created'].format(
            amount=order_result['amount'],
            currency=order_result['currency'],
            package_name=order_result['package_name']
        )

        await callback.message.edit_text(
            order_text,
            reply_markup=KeyboardBuilder.order_confirmation(order_result),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error confirming order", error=str(e))
        await callback.answer("Помилка при створенні замовлення")


@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    """Обробка оплати"""
    try:
        order_id = callback.data.replace("pay_", "")
        state_data = await state.get_data()
        order_data = state_data.get('order_data', {})

        # Створюємо рахунок в CryptoBot
        invoice_result = await PaymentService.create_invoice(
            order_id=order_id,
            amount=order_data.get('amount', 0),
            currency=order_data.get('currency', 'USD'),
            description=f"Пакет: {order_data.get('package_name', 'SocialBoost')}"
        )

        if not invoice_result.get('success'):
            await callback.answer("Помилка при створенні рахунку для оплати")
            return

        await state.set_state(UserStates.WAITING_PAYMENT)
        await state.update_data(invoice_data=invoice_result)

        payment_text = f"""
{EMOJI['money']} <b>Оплата замовлення</b>

{EMOJI['package']} Пакет: <b>{order_data.get('package_name')}</b>
{EMOJI['money']} Сума: <b>{order_data.get('amount')} {order_data.get('currency')}</b>

Натисніть кнопку нижче для оплати через CryptoBot:
"""

        await callback.message.edit_text(
            payment_text,
            reply_markup=KeyboardBuilder.payment_invoice(invoice_result['pay_url']),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error processing payment", error=str(e))
        await callback.answer("Помилка при обробці оплати")


@router.callback_query(F.data == "check_payment")
async def check_payment_status(callback: CallbackQuery, state: FSMContext):
    """Перевірка статусу оплати"""
    try:
        # Отримуємо свіжу статистику користувача
        user_stats = await UserService.get_user_stats_fresh(str(callback.from_user.id))

        current_package = user_stats.get('current_package')

        if current_package:
            # Оплата пройшла успішно
            await state.set_state(UserStates.MAIN_MENU)

            await callback.message.edit_text(
                MESSAGES['payment_success'],
                reply_markup=KeyboardBuilder.main_menu(),
                parse_mode="HTML"
            )

            # Очищаємо кеш користувача
            await UserService.invalidate_cache(str(callback.from_user.id))
        else:
            await callback.answer("Оплата ще не підтверджена. Спробуйте через хвилину.")

    except Exception as e:
        logger.error(f"Error checking payment status", error=str(e))
        await callback.answer("Помилка при перевірці статусу оплати")


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    """Скасування замовлення"""
    try:
        await state.set_state(UserStates.MAIN_MENU)

        await callback.message.edit_text(
            f"{EMOJI['info']} Замовлення скасовано.",
            reply_markup=KeyboardBuilder.main_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error canceling order", error=str(e))
        await callback.answer("Помилка при скасуванні замовлення")


# ===================================

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
            await callback.message.edit_text(
                MESSAGES['no_active_package'],
                reply_markup=KeyboardBuilder.packages_menu(await OrderService.get_packages()),
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
            # Отримуємо деталі поста (якщо є в результаті)
            post_details = ""
            if 'post_id' in result:
                # Можна додати логіку для отримання деталей з БД
                pass

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