import os
import asyncpg
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal, InvalidOperation

from app.database.locales import get_localized_text
from app.keyboards.kbReply import (main, operation_category_keyboard, get_localized_keyboard,
                                   settings_keyboard, currency_keyboard, language_keyboard)
from app.database.models import (update_user_activity, export_to_csv, get_user_stats,
                                 MAX_FILE_SIZE, get_user_currency_settings, set_user_language,
                                 set_user_currency, get_connection, get_currency_rate, convert_amount,
                                 get_user_language, set_notification_status, get_notification_status)
from aiogram.types import FSInputFile

router = Router()


# Состояния для FSM
class AddOperation(StatesGroup):
    category = State()
    amount = State()
    comment = State()

class CurrencyStates(StatesGroup):
    waiting_currency = State()

class ReportStates(StatesGroup):
    choose_report_type = State()

class LanguageStates(StatesGroup):
    waiting_language = State()

class NotificationStates(StatesGroup):
    waiting_choice = State()

# ---- Функции для работы с БД ----
async def add_operation_to_db(user_id: int, op_type: str, amount: float, category: str, comment: str) -> bool:
    """Добавление операции в базу данных"""
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432))
        )

        async with conn.transaction():
            # Добавляем операцию
            await conn.execute(
                '''
                INSERT INTO operations 
                (user_id, type, amount, category, comment, operation_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                ''',
                user_id, op_type, amount, category, comment, datetime.now()
            )

            # Обновляем активность пользователя
            await conn.execute(
                '''
                UPDATE users 
                SET last_activity_date = $1
                WHERE user_id = $2
                ''',
                datetime.now(), user_id
            )

        return True
    except Exception as e:
        print(f"Ошибка при добавлении операции: {e}")
        return False
    finally:
        if conn:
            await conn.close()


async def get_operations(user_id: int, period: Optional[str] = None) -> List[Dict]:
    """Получение операций пользователя из БД"""
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432)))

        query = '''
        SELECT type, amount, category, comment, operation_date 
        FROM operations 
        WHERE user_id = $1
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

            query += ' AND operation_date >= $2'
            params.append(start_date)

        return await conn.fetch(query, *params)
    finally:
        if conn:
            await conn.close()


# ---- Обработчики команд ----
@router.message(F.text == "НАЗАД")
async def handle_back_button(message: Message, state: FSMContext):
    """Обработчик кнопки 'Назад'"""
    await message.answer(
        "Возвращаемся в главное меню:",
        reply_markup=main
    )
    await state.clear()
    await update_user_activity(message.from_user.id)


@router.message(F.text == "Добавить операцию")
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
    data = await state.get_data()
    user_id = message.from_user.id

    await add_operation_to_db(
        user_id=user_id,
        op_type=data['type'],
        amount=data['original_amount'],  # Сохраняем в исходной валюте
        currency=data['original_currency'],  # Добавляем поле валюты
        category=data['category'],
        comment=message.text
    )

    settings = await get_user_currency_settings(user_id)
    current_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    await message.answer(
        f"✅ Операция добавлена:\n"
        f"Сумма: {data['amount']:.2f}{current_symbol}\n"
        f"Категория: {data['category']}\n"
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
        op_type = op['type']
        amount = float(op['amount'])
        category = op['category']

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


@router.message(F.text == "Баланс")
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
@router.message(F.text == "Отчёт")
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


@router.message(F.text == "Справка")
async def handle_help(message: Message):
    """Обработчик кнопки 'Справка'"""
    help_text = (
        "📚 <b>Справка по функциям бота</b> 📚\n\n"
        "<b>Баланс</b> - показывает ваш текущий баланс (разницу между доходами и расходами)\n"
        "<b>Отчёт</b> - предоставляет детализированный отчет за выбранный период (день/неделя/месяц)\n"
        "<b>Добавить операцию</b> - позволяет добавить новую операцию (доход или расход)\n"
        "<b>Планирование</b> - функции для планирования бюджета\n"
        "<b>Статистика</b> - показывает полную статистику по всем операциям\n"
        "<b>Экспорт</b> - выгружает все ваши операции в CSV-файл\n\n"
        "Выберите нужный пункт в меню для работы с функцией."
    )

    await message.answer(help_text, reply_markup=main)
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


@router.message(F.text == "Статистика")
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

@router.message(F.text == "Настройки")
async def handle_settings(message: Message):
    await message.answer(
        "⚙️ Раздел настроек. Выберите опцию:",
        reply_markup = settings_keyboard()
    )


@router.message(F.text == "Изменить валюту")
async def handle_currency(message: Message, state: FSMContext):
    await state.set_state(CurrencyStates.waiting_currency)
    await message.answer(
        "Выберите новую валюту:",
        reply_markup=currency_keyboard()
    )


@router.message(CurrencyStates.waiting_currency, F.text.in_(["RUB ₽", "USD $", "EUR €"]))
async def set_currency(message: Message, state: FSMContext):
    user_id = message.from_user.id
    currency_map = {"RUB ₽": "RUB", "USD $": "USD", "EUR €": "EUR"}
    new_currency = currency_map[message.text]

    # Получаем текущие настройки
    settings = await get_user_currency_settings(user_id)
    current_currency = settings['currency']

    if current_currency != new_currency:
        # Конвертируем все существующие операции
        await convert_user_operations(user_id, current_currency, new_currency)

        # Обновляем валюту пользователя
        await set_user_currency(user_id, new_currency)

        await message.answer(
            f"✅ Валюта изменена на {message.text}\n"
            f"Все суммы были автоматически пересчитаны",
            reply_markup=settings_keyboard()
        )
    else:
        await message.answer(
            "Валюта не изменилась",
            reply_markup=settings_keyboard()
        )

    await state.clear()


async def convert_user_operations(user_id: int, from_currency: str, to_currency: str):
    conn = await get_connection()
    try:
        operations = await conn.fetch(
            'SELECT id, amount FROM operations WHERE user_id = $1',
            user_id
        )

        for op in operations:
            original_amount = Decimal(op['amount'])
            converted_amount = await convert_amount(original_amount, from_currency, to_currency)

            await conn.execute(
                'UPDATE operations SET amount = $1 WHERE id = $2',
                float(converted_amount), op['id']
            )
    finally:
        await conn.close()


@router.message(F.text == "Баланс")
async def handle_balance(message: Message):
    user_id = message.from_user.id
    settings = await get_user_currency_settings(user_id)
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    balance_data = await calculate_balance(user_id)

    await message.answer(
        f"💰 Баланс: {balance_data['balance']:.2f}{currency_symbol}\n"
        f"Доходы: {balance_data['total_income']:.2f}{currency_symbol}\n"
        f"Расходы: {balance_data['total_expense']:.2f}{currency_symbol}\n\n"
        f"Курс: 1{currency_symbol} = {await get_currency_rate(settings['currency']):.2f}₽",
        reply_markup=main
    )


@router.message(AddOperation.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = Decimal(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError

        user_id = message.from_user.id
        settings = await get_user_currency_settings(user_id)

        # Сохраняем сумму в оригинальной валюте пользователя
        await state.update_data(
            amount=float(amount),
            currency=settings['currency'],
            original_amount=float(amount),
            original_currency=settings['original_currency']
        )

        await message.answer(
            f"Сумма: {amount:.2f}{ {'RUB': '₽', 'USD': '$', 'EUR': '€'}.get(settings['currency'], '₽')}\n"
            "Введите комментарий:"
        )
        await state.set_state(AddOperation.comment)

    except (ValueError, InvalidOperation):
        await message.answer("Пожалуйста, введите корректную сумму (положительное число).")


@router.message(F.text == "Язык")
async def handle_language(message: Message, state: FSMContext):
    await state.set_state(LanguageStates.waiting_language)
    await message.answer(
        "Выберите язык / Choose language:",
        reply_markup=language_keyboard()
    )


@router.message(LanguageStates.waiting_language, F.text.in_(["Русский", "English"]))
async def set_language(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language_map = {"Русский": "ru", "English": "en"}
    language_code = language_map[message.text]

    await set_user_language(user_id, language_code)

    # Получаем локализованный текст
    response_text = {
        'ru': "✅ Язык изменен на Русский",
        'en': "✅ Language changed to English"
    }.get(language_code, "✅ Язык изменен")

    await message.answer(
        response_text,
        reply_markup=get_localized_keyboard(language_code)
    )
    await state.clear()


@router.message(F.text.in_([get_localized_text('ru', 'notifications'),
                            get_localized_text('en', 'notifications')]))
async def handle_notifications(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    current_status = await get_notification_status(user_id)

    status_text = get_localized_text(language, 'notifications_on' if current_status else 'notifications_off')
    action_text = get_localized_text(language, 'notifications_toggle').format(
        action=get_localized_text(language, 'notifications_off' if current_status else 'notifications_on').lower()
    )

    await message.answer(
        f"{get_localized_text(language, 'notifications_menu')}\n\n"
        f"{get_localized_text(language, 'notifications_current').format(status=status_text)}\n\n"
        f"{action_text}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=get_localized_text(language,
                                                        'notifications_on' if not current_status else 'notifications_off'))],
                [KeyboardButton(text=get_localized_text(language, 'back'))]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(NotificationStates.waiting_choice)


@router.message(NotificationStates.waiting_choice)
async def process_notification_choice(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    if message.text in [get_localized_text(language, 'notifications_on'),
                        get_localized_text(language, 'notifications_off')]:
        new_status = message.text == get_localized_text(language, 'notifications_on')
        await set_notification_status(user_id, new_status)

        status_text = get_localized_text(language, 'notifications_on' if new_status else 'notifications_off')
        await message.answer(
            f"{status_text}",
            reply_markup=settings_keyboard(language)
        )
    else:
        await message.answer(
            get_localized_text(language, 'select_option'),
            reply_markup=settings_keyboard(language)
        )

    await state.clear()