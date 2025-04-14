from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType
)

from app.database.locales import get_localized_text

main = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Баланс"),
            KeyboardButton(text="Отчёт")
        ],
        [
            KeyboardButton(text="Добавить операцию"),
            KeyboardButton(text="Планирование"),
        ],
        [
            KeyboardButton(text="Настройки"),
            KeyboardButton(text="Справка"),
        ],
        [
            KeyboardButton(text="НАЗАД"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Выберите действие из меню",
    selective=True
)

def operation_category_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить расход")],
            [KeyboardButton(text="Добавить доход")],
            [KeyboardButton(text="НАЗАД")]
        ],
        resize_keyboard=True
    )

def settings_keyboard():
    """Клавиатура настроек"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Изменить валюту")],
            [KeyboardButton(text="Установить лимиты")],
            [KeyboardButton(text="Язык")],
            [KeyboardButton(text="Уведомления")],
            [KeyboardButton(text="НАЗАД")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def currency_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="RUB ₽")],
            [KeyboardButton(text="USD $")],
            [KeyboardButton(text="EUR €")],
            [KeyboardButton(text="НАЗАД")]
        ],
        resize_keyboard=True
    )

def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Русский"), KeyboardButton(text="English")],
            [KeyboardButton(text="НАЗАД")]
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
                KeyboardButton(text=get_localized_text(language_code, 'help'))
            ],
            [
                KeyboardButton(text=get_localized_text(language_code, 'back'))
            ]
        ],
        resize_keyboard=True
    )
