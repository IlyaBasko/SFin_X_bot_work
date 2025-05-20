from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType
)

from app.database.locales import get_localized_text


def operation_category_keyboard(language_code: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language_code, 'add_expense'))],
            [KeyboardButton(text=get_localized_text(language_code, 'add_income'))],
            [KeyboardButton(text=get_localized_text(language_code, 'back'))]
        ],
        resize_keyboard=True
    )

def settings_keyboard(language_code: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language_code, 'change_currency'))],
            [KeyboardButton(text=get_localized_text(language_code, 'set_limits'))],
            [KeyboardButton(text=get_localized_text(language_code, 'language'))],
            [KeyboardButton(text=get_localized_text(language_code, 'notifications'))],
            [KeyboardButton(text=get_localized_text(language_code, 'back'))]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def currency_keyboard(language: str = 'ru') -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language, 'currency_rub'))],
            [KeyboardButton(text=get_localized_text(language, 'currency_usd'))],
            [KeyboardButton(text=get_localized_text(language, 'currency_eur'))],
            [KeyboardButton(text=get_localized_text(language, 'back'))]
        ],
        resize_keyboard=True
    )

def language_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Русский"), KeyboardButton(text="English")],
            [KeyboardButton(text=get_localized_text(language, 'back'))]
        ],
        resize_keyboard=True
    )


def get_localized_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_localized_text(language_code, 'balance')),
                KeyboardButton(text=get_localized_text(language_code, 'report'))
            ],
            [
                KeyboardButton(text=get_localized_text(language_code, 'add_operation')),
                KeyboardButton(text=get_localized_text(language_code, 'settings'))
            ],
            [
                KeyboardButton(text=get_localized_text(language_code, 'pomodoro')),
                KeyboardButton(text=get_localized_text(language_code, 'goals'))
            ],
            [
                KeyboardButton(text=get_localized_text(language_code, 'reminders')),
                KeyboardButton(text=get_localized_text(language_code, 'help'))
            ],
            [
                KeyboardButton(text=get_localized_text(language_code, 'back'))
            ],
        ],
        resize_keyboard=True
    )

def report_period_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    """Локализованная клавиатура для выбора периода отчета"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language_code, 'daily_report'))],
            [KeyboardButton(text=get_localized_text(language_code, 'weekly_report'))],
            [KeyboardButton(text=get_localized_text(language_code, 'monthly_report'))],
            [KeyboardButton(text=get_localized_text(language_code, 'back'))]
        ],
        resize_keyboard=True
    )

def pomodoro_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    """Клавиатура для управления помидоркой"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"⏹ {get_localized_text(language_code, 'stop')}")],
            [KeyboardButton(text=get_localized_text(language_code, 'back'))]
        ],
        resize_keyboard=True
    )

def goals_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    """Клавиатура для работы с целями"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language_code, 'add_goal'))],
            [KeyboardButton(text=get_localized_text(language_code, 'view_goals'))],
            [KeyboardButton(text=get_localized_text(language_code, 'back'))]
        ],
        resize_keyboard=True
    )