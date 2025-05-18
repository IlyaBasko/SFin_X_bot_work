from aiogram import Router, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from datetime import datetime

import os

from app.database.models import (
    is_admin, get_all_users_stats, export_all_to_excel,
    get_user_stats, add_admin, get_user_language
)
from app.keyboards.kbReply import get_localized_keyboard

router = Router()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Проверка прав и вывод админ-панели"""
    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "👑 Админ-панель:\n"
        "/stats - Общая статистика\n"
        "/user_stats [id] - Статистика пользователя\n"
        "/add_admin [id] - Добавить администратора",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Общая статистика")],  # Теперь это список KeyboardButton
                [KeyboardButton(text="📤 Экспорт данных")],
                [KeyboardButton(text="🔙 Выход")]
            ],
            resize_keyboard=True
        )
    )


@router.message(F.text == "📊 Общая статистика")
async def show_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return

    stats = await get_all_users_stats()

    response = (
        f"📊 Общая статистика:\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"💰 Общий доход: {stats['total_income']:.2f} RUB\n"
        f"💸 Общий расход: {stats['total_expense']:.2f} RUB\n\n"
        f"Топ категорий доходов:\n"
    )

    for cat in stats['top_income_categories']:
        response += f"• {cat['category']}: {cat['amount']:.2f} RUB\n"

    response += "\nТоп категорий расходов:\n"
    for cat in stats['top_expense_categories']:
        response += f"• {cat['category']}: {cat['amount']:.2f} RUB"

    await message.answer(response)


@router.message(F.text == "📤 Экспорт данных")
async def export_data(message: Message):
    if not await is_admin(message.from_user.id):
        return

    msg = await message.answer("🔄 Создание отчета...")

    try:
        # Генерируем файл
        excel_data = await export_all_to_excel()

        # Сохраняем временный файл
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with open(filename, 'wb') as f:
            f.write(excel_data.getbuffer())

        # Отправляем файл
        await message.answer_document(
            FSInputFile(filename),
            caption="📊 Финансовый отчет"
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {str(e)}")
    finally:
        await msg.delete()
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)


@router.message(Command("user_stats"))
async def user_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text.split()[1])
        stats = await get_user_stats(user_id)

        response = (
            f"📊 Статистика пользователя ID {user_id}:\n\n"
            f"📈 Операций: {stats['total_operations']}\n"
            f"💰 Доходы: {stats['total_income']:.2f} RUB\n"
            f"💸 Расходы: {stats['total_expense']:.2f} RUB\n\n"
        )

        if 'income' in stats['categories']:
            response += "Топ категорий доходов:\n"
            for cat in stats['categories']['income'][:3]:
                response += f"• {cat['category']}: {cat['sum']:.2f} RUB\n"

        if 'expense' in stats['categories']:
            response += "\nТоп категорий расходов:\n"
            for cat in stats['categories']['expense'][:3]:
                response += f"• {cat['category']}: {cat['sum']:.2f} RUB"

        await message.answer(response)
    except (IndexError, ValueError):
        await message.answer("Используйте: /user_stats [user_id]")


@router.message(Command("add_admin"))
async def add_admin_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return

    try:
        new_admin_id = int(message.text.split()[1])
        await add_admin(new_admin_id, "new_admin")
        await message.answer(f"✅ Пользователь {new_admin_id} добавлен как администратор")
    except (IndexError, ValueError):
        await message.answer("Используйте: /add_admin [user_id]")


@router.message(F.text == "🔙 Выход")
async def exit_admin_panel(message: Message):
    """Обработчик кнопки Выход"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await message.answer(
        "Вы вышли из админ-панели",
        # reply_markup=ReplyKeyboardRemove()  # Убираем клавиатуру
        reply_markup=get_localized_keyboard(language)
    )