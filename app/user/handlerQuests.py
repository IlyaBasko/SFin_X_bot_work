import os
import aiosqlite
import aiofiles
from aiogram import Router, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from app.keyboards.kbReply import main, operation_category_keyboard
from app.database.models import update_user_activity, export_to_csv, get_user_stats, MAX_FILE_SIZE
from aiogram.types import FSInputFile

router = Router()


# Состояния для FSM
class AddOperation(StatesGroup):
    category = State()
    amount = State()
    comment = State()


class ReportStates(StatesGroup):
    choose_report_type = State()


# ---- Функции для работы с БД ----
async def add_operation_to_db(user_id: int, op_type: str, amount: float, category: str, comment: str) -> bool:
    """Добавление операции в базу данных"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        try:
            operation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Добавляем операцию
            await db.execute('''
                INSERT INTO operations 
                (user_id, type, amount, category, comment, operation_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, op_type, amount, category, comment, operation_date))

            # Обновляем активность пользователя
            await db.execute('''
                UPDATE users 
                SET last_activity_date = ?
                WHERE user_id = ?
            ''', (operation_date, user_id))

            await db.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении операции: {e}")
            await db.rollback()
            return False


async def get_operations(user_id: int, period: Optional[str] = None) -> List[Tuple]:
    """Получение операций пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        query = '''
            SELECT type, amount, category, comment, operation_date 
            FROM operations 
            WHERE user_id = ?
        '''
        params = [user_id]

        if period:
            now = datetime.now()
            if period == 'day':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            query += ' AND operation_date >= ?'
            params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))

        cursor = await db.execute(query, tuple(params))
        return await cursor.fetchall()


# ---- Обработчики команд ----
@router.message(lambda message: message.text == "НАЗАД")
async def handle_back_button(message: Message, state: FSMContext):
    """Обработчик кнопки 'Назад'"""
    await message.answer(
        "Возвращаемся в главное меню:",
        reply_markup=main
    )
    await state.clear()
    await update_user_activity(message.from_user.id)


@router.message(lambda message: message.text == "Добавить операцию")
async def add_operation(message: Message, state: FSMContext):
    """Начало добавления операции"""
    await update_user_activity(message.from_user.id)
    await message.answer(
        "Выберите категорию:",
        reply_markup=operation_category_keyboard()
    )
    await state.set_state(AddOperation.category)


@router.message(AddOperation.category)
async def process_category(message: Message, state: FSMContext):
    """Обработка категории операции"""
    if message.text not in ["Добавить расход", "Добавить доход"]:
        await message.answer("Пожалуйста, выберите категорию из предложенных.")
        return

    await state.update_data(
        category="income" if message.text == "Добавить доход" else "expense",
        category_name=message.text
    )
    await message.answer("Введите сумму:")
    await state.set_state(AddOperation.amount)


@router.message(AddOperation.amount)
async def process_amount(message: Message, state: FSMContext):
    """Обработка суммы операции"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await message.answer("Введите комментарий:")
        await state.set_state(AddOperation.comment)
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму (положительное число).")


@router.message(AddOperation.comment)
async def process_comment(message: Message, state: FSMContext):
    """Финализация добавления операции"""
    data = await state.get_data()
    user_id = message.from_user.id

    # Добавляем операцию в БД
    await add_operation_to_db(
        user_id=user_id,
        op_type=data['category'],
        amount=data['amount'],
        category=data['category_name'],
        comment=message.text
    )

    await message.answer(
        f"✅ Операция добавлена!\n"
        f"Тип: {data['category_name']}\n"
        f"Сумма: {data['amount']:.2f} руб.\n"
        f"Комментарий: {message.text}",
        reply_markup=main
    )
    await state.clear()


# ---- Функции для работы с балансом ----
async def calculate_balance(user_id: int, period: Optional[str] = None) -> Dict:
    """Асинхронный расчет баланса пользователя"""
    operations = await get_operations(user_id, period)

    result = {
        'total_income': 0.0,
        'total_expense': 0.0,
        'income_by_category': {},
        'expense_by_category': {}
    }

    for op in operations:
        op_type, amount, category, comment, _ = op
        amount = float(amount)

        if op_type == 'income':
            result['total_income'] += amount
            if category not in result['income_by_category']:
                result['income_by_category'][category] = 0.0
            result['income_by_category'][category] += amount
        else:
            result['total_expense'] += amount
            if category not in result['expense_by_category']:
                result['expense_by_category'][category] = 0.0
            result['expense_by_category'][category] += amount

    result['balance'] = result['total_income'] - result['total_expense']
    return result


@router.message(lambda message: message.text == "Баланс")
async def handle_balance(message: Message):
    """Обработчик команды 'Баланс'"""
    user_id = message.from_user.id
    balance_data = await calculate_balance(user_id)

    response = (
        f"💰 Текущий баланс: {balance_data['balance']:.2f} руб.\n"
        f"Доходы: {balance_data['total_income']:.2f} руб.\n"
        f"Расходы: {balance_data['total_expense']:.2f} руб.\n\n"
    )

    if balance_data['income_by_category']:
        response += "📈 Доходы по категориям:\n"
        for category, amount in balance_data['income_by_category'].items():
            response += f"• {category}: {amount:.2f} руб.\n"

    if balance_data['expense_by_category']:
        response += "\n📉 Расходы по категориям:\n"
        for category, amount in balance_data['expense_by_category'].items():
            response += f"• {category}: {amount:.2f} руб.\n"

    await message.answer(response, reply_markup=main)
    await update_user_activity(user_id)


# ---- Отчеты ----
@router.message(lambda message: message.text == "Отчёт")
async def handle_report(message: Message, state: FSMContext):
    """Обработчик команды 'Отчёт'"""
    await message.answer(
        "Выберите тип отчета:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Ежедневный отчет")],
                [KeyboardButton(text="Еженедельный отчет")],
                [KeyboardButton(text="Ежемесячный отчет")],
                [KeyboardButton(text="НАЗАД")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(ReportStates.choose_report_type)
    await update_user_activity(message.from_user.id)


@router.message(ReportStates.choose_report_type)
async def process_report_type(message: Message, state: FSMContext):
    """Генерация отчетов"""
    period_map = {
        "Ежедневный отчет": "day",
        "Еженедельный отчет": "week",
        "Ежемесячный отчет": "month"
    }

    if message.text not in period_map:
        await message.answer("Пожалуйста, выберите тип отчета из меню.", reply_markup=main)
        await state.clear()
        return

    period = period_map[message.text]
    balance_data = await calculate_balance(message.from_user.id, period)

    period_name = {
        "day": "день",
        "week": "неделю",
        "month": "месяц"
    }[period]

    response = f"📊 Отчет за {period_name}:\n\n"
    response += f"Баланс: {balance_data['balance']:.2f} руб.\n"
    response += f"Доходы: {balance_data['total_income']:.2f} руб.\n"
    response += f"Расходы: {balance_data['total_expense']:.2f} руб.\n\n"

    if balance_data['income_by_category']:
        response += "Доходы по категориям:\n"
        for category, amount in balance_data['income_by_category'].items():
            response += f"• {category}: {amount:.2f} руб.\n"

    if balance_data['expense_by_category']:
        response += "\nРасходы по категориям:\n"
        for category, amount in balance_data['expense_by_category'].items():
            response += f"• {category}: {amount:.2f} руб.\n"

    await message.answer(response, reply_markup=main)
    await state.clear()
    await update_user_activity(message.from_user.id)


@router.message(lambda message: message.text == "Статистика")
async def handle_stats(message: Message):
    """Полная статистика по операциям"""
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)

    response = (
        f"📊 Полная статистика:\n\n"
        f"Всего операций: {stats['total_operations']}\n"
        f"Общий доход: {stats['total_income']:.2f} руб.\n"
        f"Общий расход: {stats['total_expense']:.2f} руб.\n"
        f"Итоговый баланс: {stats['total_income'] - stats['total_expense']:.2f} руб.\n\n"
    )

    if 'income' in stats['categories']:
        response += "Топ категорий доходов:\n"
        for cat in stats['categories']['income'][:3]:
            response += f"• {cat['category']}: {cat['sum']:.2f} руб. ({cat['count']} операций)\n"

    if 'expense' in stats['categories']:
        response += "\nТоп категорий расходов:\n"
        for cat in stats['categories']['expense'][:3]:
            response += f"• {cat['category']}: {cat['sum']:.2f} руб. ({cat['count']} операций)\n"

    await message.answer(response, reply_markup=main)
    await update_user_activity(user_id)


@router.message(F.text == "Экспорт")
async def handle_export(message: Message):
    user_id = message.from_user.id
    filename = await export_to_csv(user_id)

    if not filename:
        await message.answer("Нет данных для экспорта")
        return

    try:
        file_size = os.path.getsize(filename)
        if file_size > MAX_FILE_SIZE:
            await message.answer("Файл слишком большой для отправки")
            return

        await message.answer_document(
            FSInputFile(filename),
            caption="Ваши финансовые операции"
        )
    finally:
        if os.path.exists(filename):
            os.remove(filename)

    await update_user_activity(user_id)
