from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from app.keyboards import kbReply
from app.database.models import add_user, update_user_activity

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    # Регистрируем пользователя в БД
    await add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Обновляем активность
    await update_user_activity(user.id)

    await message.answer(
        f"Привет, {user.first_name}! Я бот для учета финансов.\n\n"
        "Доступные команды:\n"
        "• Баланс - текущее состояние\n"
        "• Отчёт - статистика\n"
        "• Добавить операцию - новая запись",
        reply_markup=kbReply.main
    )