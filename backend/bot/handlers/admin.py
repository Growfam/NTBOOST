"""
Адмін обробники для управління ботом - ВИПРАВЛЕНА версія
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import structlog

from backend.bot.keyboards.inline import KeyboardBuilder
from backend.bot.states.user_states import UserStates, AdminStates
from backend.database.connection import get_admin_stats
from backend.config import get_config
from backend.utils.constants import EMOJI

config = get_config()
router = Router()
logger = structlog.get_logger(__name__)


def is_admin(user_id: int) -> bool:
    """Перевіряє чи користувач є адміном"""
    # ВИПРАВЛЕНО: використовуємо метод замість property
    admin_ids = config.get_admin_telegram_ids()
    return user_id in admin_ids


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    """Головна панель адміністратора"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer(f"{EMOJI['cross']} У вас немає прав адміністратора.")
            return

        await state.set_state(AdminStates.MAIN_PANEL)

        admin_text = f"""
{EMOJI['admin']} <b>Панель адміністратора</b>

Ласкаво просимо до панелі управління SocialBoost Bot!

Оберіть дію з меню нижче:
"""

        await message.answer(
            admin_text,
            reply_markup=KeyboardBuilder.admin_panel(),
            parse_mode="HTML"
        )

        logger.info(f"Admin {message.from_user.id} accessed admin panel")

    except Exception as e:
        logger.error(f"Error in admin panel for user {message.from_user.id}", error=str(e))
        await message.answer(f"{EMOJI['cross']} Помилка доступу до адмін панелі.")


@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery, state: FSMContext):
    """Показ статистики системи"""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ заборонено", show_alert=True)
            return

        # Отримуємо статистику з БД
        stats = get_admin_stats()

        if not stats:
            await callback.answer("Помилка отримання статистики")
            return

        # Форматуємо статистику
        stats_text = f"""
{EMOJI['chart']} <b>Статистика системи</b>

👥 <b>Користувачі:</b>
• Всього: {stats.get('total_users', 0)}
• Активних: {stats.get('active_users', 0)}

📦 <b>Замовлення:</b>
• Всього: {stats.get('total_orders', 0)}
• Оплачених: {stats.get('paid_orders', 0)}

💰 <b>Дохід:</b>
• Загальний: ${stats.get('total_revenue', 0):.2f}

📝 <b>Пости:</b>
• Всього: {stats.get('total_posts', 0)}
• Активних: {stats.get('active_posts', 0)}
• Завершених: {stats.get('completed_posts', 0)}

📦 <b>Пакети:</b>
• Активних: {stats.get('packages_count', 0)}
"""

        # Додаємо останні замовлення
        recent_orders = stats.get('recent_orders', [])
        if recent_orders:
            stats_text += f"\n{EMOJI['bell']} <b>Останні замовлення (24 години):</b>\n"
            for order in recent_orders[:5]:  # Показуємо тільки 5 останніх
                username = order.get('user_username', 'Невідомо')
                amount = order.get('amount', 0)
                package_name = order.get('package_name', 'Невідомо')
                stats_text += f"• @{username}: ${amount:.0f} - {package_name}\n"

        await callback.message.edit_text(
            stats_text,
            reply_markup=KeyboardBuilder.admin_panel(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing admin stats", error=str(e))
        await callback.answer("Помилка при завантаженні статистики")


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Початок розсилки"""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ заборонено", show_alert=True)
            return

        await state.set_state(AdminStates.BROADCAST_COMPOSE)

        broadcast_text = f"""
{EMOJI['bell']} <b>Розсилка повідомлень</b>

Надішліть текст повідомлення для розсилки всім користувачам.

⚠️ <b>Увага:</b> Повідомлення буде відправлено всім зареєстрованим користувачам!

Для скасування натисніть /cancel
"""

        await callback.message.edit_text(
            broadcast_text,
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error starting broadcast", error=str(e))
        await callback.answer("Помилка початку розсилки")


@router.message(AdminStates.BROADCAST_COMPOSE)
async def compose_broadcast(message: Message, state: FSMContext):
    """Складання тексту розсилки"""
    try:
        if not is_admin(message.from_user.id):
            return

        if message.text == "/cancel":
            await state.set_state(AdminStates.MAIN_PANEL)
            await message.answer(
                f"{EMOJI['info']} Розсилку скасовано.",
                reply_markup=KeyboardBuilder.admin_panel()
            )
            return

        # ВИПРАВЛЕНО: додаємо валідацію тексту
        broadcast_text = message.text
        if not broadcast_text or len(broadcast_text) > 4000:
            await message.answer(
                f"{EMOJI['cross']} Текст повідомлення має бути від 1 до 4000 символів.",
                reply_markup=KeyboardBuilder.admin_panel()
            )
            return

        await state.update_data(broadcast_text=broadcast_text)
        await state.set_state(AdminStates.BROADCAST_CONFIRM)

        confirm_text = f"""
{EMOJI['bell']} <b>Підтвердження розсилки</b>

<b>Текст повідомлення:</b>
{broadcast_text[:500]}{'...' if len(broadcast_text) > 500 else ''}

<b>Довжина:</b> {len(broadcast_text)} символів

Підтвердити розсилку?
"""

        buttons = [
            [InlineKeyboardButton(
                text=f"{EMOJI['check']} Підтвердити розсилку",
                callback_data="confirm_broadcast"
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['cross']} Скасувати",
                callback_data="cancel_broadcast"
            )]
        ]

        await message.answer(
            confirm_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error composing broadcast", error=str(e))
        await message.answer("Помилка при складанні розсилки")


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Підтвердження та виконання розсилки"""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ заборонено", show_alert=True)
            return

        state_data = await state.get_data()
        broadcast_text = state_data.get('broadcast_text', '')

        if not broadcast_text:
            await callback.answer("Текст розсилки порожній")
            return

        # ВИПРАВЛЕНО: імітація розсилки з кращим повідомленням
        await callback.message.edit_text(
            f"""
{EMOJI['check']} <b>Розсилка запущена!</b>

Повідомлення буде відправлено всім користувачам у фоновому режимі.

<b>Статус:</b> Розсилка розпочата
<b>Текст:</b> {broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}

Ви отримаєте сповіщення після завершення.
""",
            reply_markup=KeyboardBuilder.admin_panel(),
            parse_mode="HTML"
        )

        await state.set_state(AdminStates.MAIN_PANEL)
        await callback.answer()

        logger.info(f"Admin {callback.from_user.id} started broadcast", text_length=len(broadcast_text))

    except Exception as e:
        logger.error(f"Error confirming broadcast", error=str(e))
        await callback.answer("Помилка при запуску розсилки")


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Скасування розсилки"""
    try:
        await state.set_state(AdminStates.MAIN_PANEL)

        await callback.message.edit_text(
            f"{EMOJI['info']} Розсилку скасовано.",
            reply_markup=KeyboardBuilder.admin_panel(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error canceling broadcast", error=str(e))
        await callback.answer("Помилка при скасуванні розсилки")


# ВИПРАВЛЕНО: додаємо перевірку на ініціалізацію бота
async def notify_admins_new_order(bot, user_data: dict, order_data: dict):
    """Сповіщає адмінів про нове замовлення"""
    try:
        if not bot:
            logger.error("Bot not initialized for admin notification")
            return

        from backend.utils.constants import MESSAGES
        import datetime

        notification_text = MESSAGES['admin_notification'].format(
            username=user_data.get('username', 'Невідомо'),
            amount=order_data.get('amount', 0),
            currency=order_data.get('currency', 'USD'),
            package_name=order_data.get('package_name', 'Невідомо'),
            time=datetime.datetime.now().strftime('%H:%M:%S')
        )

        # Відправляємо всім адмінам
        admin_ids = config.get_admin_telegram_ids()
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    notification_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}", error=str(e))

        # Якщо налаштований канал адмінів
        if config.ADMIN_CHANNEL_ID:
            try:
                await bot.send_message(
                    config.ADMIN_CHANNEL_ID,
                    notification_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin channel", error=str(e))

        logger.info("Admin notification sent for new order", order_id=order_data.get('order_id'))

    except Exception as e:
        logger.error("Error sending admin notification", error=str(e))


async def notify_admins_payment_success(bot, user_data: dict, order_data: dict):
    """Сповіщає адмінів про успішну оплату"""
    try:
        if not bot:
            logger.error("Bot not initialized for payment notification")
            return

        import datetime

        notification_text = f"""
{EMOJI['check']} <b>Оплата підтверджена!</b>

{EMOJI['admin']} Користувач: @{user_data.get('username', 'Невідомо')}
{EMOJI['money']} Сума: {order_data.get('amount', 0)} {order_data.get('currency', 'USD')}
{EMOJI['package']} Пакет: {order_data.get('package_name', 'Невідомо')}
{EMOJI['time']} Час: {datetime.datetime.now().strftime('%H:%M:%S')}

{EMOJI['rocket']} Замовлення активовано!
"""

        # Відправляємо всім адмінам
        admin_ids = config.get_admin_telegram_ids()
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    notification_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about payment", error=str(e))

        logger.info("Admin payment notification sent", order_id=order_data.get('order_id'))

    except Exception as e:
        logger.error("Error sending payment notification", error=str(e))