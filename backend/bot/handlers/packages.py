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
        from backend.services.user_service import UserService
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