"""
FSM стани для Telegram бота
"""
from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    """Стани користувача"""

    # Основні стани
    MAIN_MENU = State()

    # Стани для вибору пакетів
    SELECTING_PACKAGE = State()
    VIEWING_PACKAGE_DETAILS = State()
    CONFIRMING_ORDER = State()
    WAITING_PAYMENT = State()

    # Стани для додавання постів
    SELECTING_PLATFORM = State()
    WAITING_POST_URL = State()
    PROCESSING_POST = State()

    # Стани для адміна
    ADMIN_PANEL = State()
    ADMIN_BROADCAST_MESSAGE = State()
    ADMIN_SETTINGS = State()


class PostStates(StatesGroup):
    """Стани для роботи з постами"""

    WAITING_PLATFORM_SELECTION = State()
    WAITING_URL_INPUT = State()
    VALIDATING_URL = State()
    CREATING_TASK = State()
    TASK_CREATED = State()


class OrderStates(StatesGroup):
    """Стани для замовлень"""

    PACKAGE_SELECTION = State()
    ORDER_CONFIRMATION = State()
    PAYMENT_PROCESSING = State()
    PAYMENT_COMPLETED = State()
    ORDER_ACTIVATED = State()


class AdminStates(StatesGroup):
    """Стани для адміністратора"""

    MAIN_PANEL = State()
    VIEWING_STATS = State()
    BROADCAST_COMPOSE = State()
    BROADCAST_CONFIRM = State()
    SETTINGS_MENU = State()
    PACKAGE_MANAGEMENT = State()


# Допоміжні функції для роботи зі станами
class StateManager:
    """Менеджер станів"""

    @staticmethod
    def is_user_state(state: State) -> bool:
        """Перевіряє чи стан належить до користувацьких"""
        return state in [
            UserStates.MAIN_MENU,
            UserStates.SELECTING_PACKAGE,
            UserStates.VIEWING_PACKAGE_DETAILS,
            UserStates.CONFIRMING_ORDER,
            UserStates.WAITING_PAYMENT,
            UserStates.SELECTING_PLATFORM,
            UserStates.WAITING_POST_URL,
            UserStates.PROCESSING_POST
        ]

    @staticmethod
    def is_admin_state(state: State) -> bool:
        """Перевіряє чи стан належить до адмінських"""
        return state in [
            UserStates.ADMIN_PANEL,
            UserStates.ADMIN_BROADCAST_MESSAGE,
            UserStates.ADMIN_SETTINGS,
            AdminStates.MAIN_PANEL,
            AdminStates.VIEWING_STATS,
            AdminStates.BROADCAST_COMPOSE,
            AdminStates.BROADCAST_CONFIRM,
            AdminStates.SETTINGS_MENU,
            AdminStates.PACKAGE_MANAGEMENT
        ]

    @staticmethod
    def is_payment_state(state: State) -> bool:
        """Перевіряє чи стан пов'язаний з оплатою"""
        return state in [
            UserStates.CONFIRMING_ORDER,
            UserStates.WAITING_PAYMENT,
            OrderStates.ORDER_CONFIRMATION,
            OrderStates.PAYMENT_PROCESSING,
            OrderStates.PAYMENT_COMPLETED
        ]

    @staticmethod
    def is_post_state(state: State) -> bool:
        """Перевіряє чи стан пов'язаний з постами"""
        return state in [
            UserStates.SELECTING_PLATFORM,
            UserStates.WAITING_POST_URL,
            UserStates.PROCESSING_POST,
            PostStates.WAITING_PLATFORM_SELECTION,
            PostStates.WAITING_URL_INPUT,
            PostStates.VALIDATING_URL,
            PostStates.CREATING_TASK,
            PostStates.TASK_CREATED
        ]