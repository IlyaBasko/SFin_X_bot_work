from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType
)

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