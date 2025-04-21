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
from app.keyboards.kbReply import (operation_category_keyboard, get_localized_keyboard,
                                   settings_keyboard, currency_keyboard, language_keyboard, report_period_keyboard)
from app.database.models import (update_user_activity, export_to_csv, get_user_stats,
                                 MAX_FILE_SIZE, get_user_currency_settings, set_user_language,
                                 set_user_currency, get_connection, convert_amount,
                                 get_user_language, set_notification_status, get_notification_status,
                                 set_category_limit, get_category_limits, get_category_spending)
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

class LimitStates(StatesGroup):
    choosing_category = State()
    setting_limit = State()

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
@router.message((F.text == get_localized_text('ru', 'back')) | (F.text == get_localized_text('en', 'back')))  # Назад
async def handle_back_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await message.answer(
        get_localized_text(language, 'select_option'),
        reply_markup=get_localized_keyboard(language)
    )
    await state.clear()
    await update_user_activity(user_id)


@router.message((F.text == get_localized_text('ru', 'add_operation')) | (
        F.text == get_localized_text('en', 'add_operation')))  # Добавить операцию
async def add_operation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await message.answer(
        get_localized_text(language, 'select_category'),
        reply_markup=operation_category_keyboard(language)
    )
    await state.set_state(AddOperation.category)
    await update_user_activity(user_id)


@router.message(AddOperation.category)
async def process_category(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    valid_options = [
        get_localized_text(language, 'add_expense'),
        get_localized_text(language, 'add_income')
    ]

    if message.text not in valid_options:
        await message.answer(get_localized_text(language, 'please_select'))
        return

    await state.update_data(
        category="income" if message.text == get_localized_text(language, 'add_income') else "expense",
        category_name=message.text
    )
    await message.answer(get_localized_text(language, 'amount') + ":")
    await state.set_state(AddOperation.amount)


@router.message(AddOperation.amount)
async def process_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    try:
        amount = Decimal(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError

        data = await state.get_data()
        if data['category'] == 'expense':
            # Проверяем лимиты
            limits = await get_category_limits(user_id)
            category_limit = limits.get(data['category_name'], None)

            if category_limit is not None:
                current_spending = await get_category_spending(user_id, data['category_name'])
                if current_spending + float(amount) > category_limit:
                    settings = await get_user_currency_settings(user_id)
                    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")
                    remaining = category_limit - current_spending

                    await message.answer(
                        get_localized_text(language, 'limit_warning').format(
                            limit=f"{category_limit:.2f}{currency_symbol}",
                            remaining=f"{remaining:.2f}{currency_symbol}" if remaining > 0 else "0"
                        )
                    )
                    return

        settings = await get_user_currency_settings(user_id)
        await state.update_data(
            amount=float(amount),
            currency=settings['currency'],
            original_amount=float(amount),
            original_currency=settings['original_currency']
        )

        await message.answer(get_localized_text(language, 'comment') + ":")
        await state.set_state(AddOperation.comment)
    except (ValueError, InvalidOperation):
        await message.answer(get_localized_text(language, 'invalid_amount'))


@router.message(AddOperation.comment)
async def process_comment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    data = await state.get_data()

    await add_operation_to_db(
        user_id=user_id,
        op_type=data['category'],
        amount=data['original_amount'],
        category=data['category_name'],
        comment=message.text
    )

    settings = await get_user_currency_settings(user_id)
    current_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    response = (
        f"{get_localized_text(language, 'operation_added')}\n"
        f"{get_localized_text(language, 'amount')}: {data['amount']:.2f}{current_symbol}\n"
        f"{get_localized_text(language, 'category')}: {data['category_name']}\n"
        f"{get_localized_text(language, 'comment')}: {message.text}"
    )

    await message.answer(response, reply_markup=get_localized_keyboard(language))
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


@router.message(
    (F.text == get_localized_text('ru', 'balance')) | (F.text == get_localized_text('en', 'balance')))  # Баланс
async def handle_balance(message: Message):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    balance_data = await calculate_balance(user_id)
    settings = await get_user_currency_settings(user_id)
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    response = (
        f"{get_localized_text(language, 'current_balance')}: {balance_data['balance']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'total_income')}: {balance_data['total_income']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'total_expense')}: {balance_data['total_expense']:.2f}{currency_symbol}\n\n"
    )

    if balance_data['income_by_category']:
        response += f"{get_localized_text(language, 'top_income_categories')}:\n"
        for category, amount in balance_data['income_by_category'].items():
            response += f"• {category}: {amount:.2f}{currency_symbol}\n"

    if balance_data['expense_by_category']:
        response += f"\n{get_localized_text(language, 'top_expense_categories')}:\n"
        for category, amount in balance_data['expense_by_category'].items():
            response += f"• {category}: {amount:.2f}{currency_symbol}\n"

    await message.answer(response, reply_markup=get_localized_keyboard(language))
    await update_user_activity(user_id)


# ---- Отчёты ----
@router.message(
    (F.text == get_localized_text('ru', 'report')) | (F.text == get_localized_text('en', 'report')))  # Отчёт
async def handle_report(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await message.answer(
        get_localized_text(language, 'select_report_period'),
        reply_markup=report_period_keyboard(language)
    )
    await state.set_state(ReportStates.choose_report_type)
    await update_user_activity(user_id)


@router.message(ReportStates.choose_report_type)
async def process_report_type(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    period_map = {
        get_localized_text(language, 'daily_report'): 'day',
        get_localized_text(language, 'weekly_report'): 'week',
        get_localized_text(language, 'monthly_report'): 'month'
    }

    if message.text not in period_map:
        await message.answer(get_localized_text(language, 'please_select'))
        return

    period = period_map[message.text]
    balance_data = await calculate_balance(user_id, period)
    settings = await get_user_currency_settings(user_id)
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    response = (
        f"{get_localized_text(language, 'report_for_period').format(period=get_localized_text(language, period))}:\n\n"
        f"{get_localized_text(language, 'balance')}: {balance_data['balance']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'total_income')}: {balance_data['total_income']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'total_expense')}: {balance_data['total_expense']:.2f}{currency_symbol}\n\n"
    )

    if balance_data['income_by_category']:
        response += f"{get_localized_text(language, 'income_by_category')}:\n"
        for category, amount in balance_data['income_by_category'].items():
            response += f"• {category}: {amount:.2f}{currency_symbol}\n"

    if balance_data['expense_by_category']:
        response += f"\n{get_localized_text(language, 'expense_by_category')}:\n"
        for category, amount in balance_data['expense_by_category'].items():
            response += f"• {category}: {amount:.2f}{currency_symbol}\n"

    await message.answer(response, reply_markup=get_localized_keyboard(language))
    await state.clear()
    await update_user_activity(user_id)


@router.message((F.text == get_localized_text('ru', 'help')) | (F.text == get_localized_text('en', 'help')))  # Справка
async def handle_help(message: Message):
    """Обработчик команды 'Справка'"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    # Формируем текст справки
    help_text = (
        f"📚 <b>{get_localized_text(language, 'help')}</b> 📚\n\n"
        f"<b>{get_localized_text(language, 'balance')}</b> - {get_localized_text(language, 'balance_help_desc')}\n"
        f"<b>{get_localized_text(language, 'report')}</b> - {get_localized_text(language, 'report_help_desc')}\n"
        f"<b>{get_localized_text(language, 'settings')}</b> - {get_localized_text(language, 'settings_help_desc')}\n"
        f"<b>{get_localized_text(language, 'add_operation')}</b> - {get_localized_text(language, 'add_operation_help_desc')}\n"
        f"<b>{get_localized_text(language, 'statistics')}</b> - {get_localized_text(language, 'statistics_help_desc')}\n"
        f"<b>{get_localized_text(language, 'export')}</b> - {get_localized_text(language, 'export_help_desc')}\n\n"
        f"{get_localized_text(language, 'help_footer')}"
    )

    # Отправляем сообщение
    await message.answer(
        text=help_text,
        reply_markup=get_localized_keyboard(language),
        parse_mode="HTML"
    )
    await update_user_activity(user_id)


@router.message((F.text == get_localized_text('ru', 'statistics')) | (
        F.text == get_localized_text('en', 'statistics')))  # Статистика
async def handle_stats(message: Message):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    stats = await get_user_stats(user_id)
    settings = await get_user_currency_settings(user_id)
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

    response = (
        f"{get_localized_text(language, 'statistics')}:\n\n"
        f"{get_localized_text(language, 'total_operations')}: {stats['total_operations']}\n"
        f"{get_localized_text(language, 'total_income')}: {stats['total_income']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'total_expense')}: {stats['total_expense']:.2f}{currency_symbol}\n"
        f"{get_localized_text(language, 'current_balance')}: {stats['total_income'] - stats['total_expense']:.2f}{currency_symbol}\n\n"
    )

    if 'income' in stats['categories']:
        response += f"{get_localized_text(language, 'top_income_categories')}:\n"
        for cat in stats['categories']['income'][:3]:
            response += f"• {cat['category']}: {cat['sum']:.2f}{currency_symbol} ({cat['count']} {get_localized_text(language, 'operations_count')})\n"

    if 'expense' in stats['categories']:
        response += f"\n{get_localized_text(language, 'top_expense_categories')}:\n"
        for cat in stats['categories']['expense'][:3]:
            response += f"• {cat['category']}: {cat['sum']:.2f}{currency_symbol} ({cat['count']} {get_localized_text(language, 'operations_count')})\n"

    await message.answer(response, reply_markup=get_localized_keyboard(language))
    await update_user_activity(user_id)


@router.message(
    (F.text == get_localized_text('ru', 'export')) | (F.text == get_localized_text('en', 'export')))  # Экспорт
async def handle_export(message: Message):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    filename = await export_to_csv(user_id)

    if not filename:
        await message.answer(get_localized_text(language, 'no_data'))
        return

    try:
        file_size = os.path.getsize(filename)
        if file_size > MAX_FILE_SIZE:
            await message.answer(get_localized_text(language, 'file_too_large'))
            return

        await message.answer_document(
            FSInputFile(filename),
            caption=get_localized_text(language, 'finance_operations')
        )
    finally:
        if os.path.exists(filename):
            os.remove(filename)

    await update_user_activity(user_id)


@router.message(
    (F.text == get_localized_text('ru', 'settings')) | (F.text == get_localized_text('en', 'settings')))  # Настройки
async def handle_settings(message: Message):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await message.answer(
        get_localized_text(language, 'settings'),
        reply_markup=settings_keyboard(language)
    )


@router.message((F.text == get_localized_text('ru', 'change_currency')) | (
        F.text == get_localized_text('en', 'change_currency')))  # Изменить валюту
async def handle_currency(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await state.set_state(CurrencyStates.waiting_currency)
    await message.answer(
        get_localized_text(language, 'change_currency'),
        reply_markup=currency_keyboard(language)
    )


async def convert_user_operations(user_id: int, from_currency: str, to_currency: str):
    """Конвертирует все операции пользователя из одной валюты в другую"""
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


@router.message(CurrencyStates.waiting_currency)
async def set_currency(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    currency_buttons = [
        get_localized_text(language, 'currency_rub'),
        get_localized_text(language, 'currency_usd'),
        get_localized_text(language, 'currency_eur')
    ]

    if message.text not in currency_buttons:
        await message.answer(get_localized_text(language, 'please_select'))
        return

    currency_map = {
        get_localized_text(language, 'currency_rub'): "RUB",
        get_localized_text(language, 'currency_usd'): "USD",
        get_localized_text(language, 'currency_eur'): "EUR"
    }

    new_currency = currency_map[message.text]
    settings = await get_user_currency_settings(user_id)

    if settings['currency'] != new_currency:
        await convert_user_operations(user_id, settings['currency'], new_currency)
        await set_user_currency(user_id, new_currency)

        await message.answer(
            get_localized_text(language, 'currency_changed').format(currency=message.text),
            reply_markup=settings_keyboard(language)
        )
    else:
        await message.answer(
            get_localized_text(language, 'currency_not_changed'),
            reply_markup=settings_keyboard(language)
        )

    await state.clear()


@router.message(
    (F.text == get_localized_text('ru', 'language')) | (F.text == get_localized_text('en', 'language')))  # Язык
async def handle_language(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    await state.set_state(LanguageStates.waiting_language)
    await message.answer(
        get_localized_text(language, 'language'),
        reply_markup=language_keyboard(language)
    )


@router.message(LanguageStates.waiting_language)
async def set_language(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Проверяем, какой язык выбрал пользователь
    if message.text in ["Русский", "Russian"]:
        new_language = "ru"
        response = get_localized_text(new_language, 'language_changed')  # "✅ Язык изменен на Русский"
    elif message.text in ["English", "Английский"]:  # На случай, если кнопка будет локализована
        new_language = "en"
        response = get_localized_text(new_language, 'language_changed')  # "✅ Language changed to English"
    else:
        await message.answer("Пожалуйста, выберите язык из предложенных вариантов.")
        return

    await set_user_language(user_id, new_language)
    await message.answer(response, reply_markup=get_localized_keyboard(new_language))
    await state.clear()


@router.message((F.text == get_localized_text('ru', 'notifications')) |  # Уведомления
                (F.text == get_localized_text('en', 'notifications')))
async def handle_notifications(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    current_status = await get_notification_status(user_id)

    status_text = get_localized_text(language,
                                     'notifications_status_on' if current_status else 'notifications_status_off')
    action_text = get_localized_text(language, 'notifications_toggle').format(
        action=get_localized_text(language, 'notifications_off' if current_status else 'notifications_on')
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


@router.message((F.text == get_localized_text('ru', 'set_limits')) |
                (F.text == get_localized_text('en', 'set_limits')))
async def handle_set_limits(message: Message, state: FSMContext):
    """Обработчик кнопки 'Установить лимиты'"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    # Получаем все категории расходов пользователя
    categories = await get_expense_categories(user_id)

    if not categories:
        await message.answer(get_localized_text(language, 'no_expense_categories'))
        return

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for category in categories:
        keyboard.add(KeyboardButton(text=category))
    keyboard.add(KeyboardButton(text=get_localized_text(language, 'back')))

    await message.answer(
        get_localized_text(language, 'select_category_for_limit'),
        reply_markup=keyboard
    )
    await state.set_state(LimitStates.choosing_category)


async def get_expense_categories(user_id: int) -> List[str]:
    """Получение уникальных категорий расходов пользователя"""
    conn = await asyncpg.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432)))

    try:
        records = await conn.fetch(
            'SELECT DISTINCT category FROM operations WHERE user_id = $1 AND type = \'expense\'',
            user_id
        )
        return [rec['category'] for rec in records]
    finally:
        await conn.close()


@router.message(LimitStates.choosing_category)
async def process_category_selection(message: Message, state: FSMContext):
    """Обработка выбора категории для установки лимита"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    if message.text == get_localized_text(language, 'back'):
        await handle_back_button(message, state)
        return

    categories = await get_expense_categories(user_id)
    if message.text not in categories:
        await message.answer(get_localized_text(language, 'invalid_category'))
        return

    await state.update_data(category=message.text)

    # Получаем текущий лимит (если есть)
    limits = await get_category_limits(user_id)
    current_limit = limits.get(message.text, 0)

    await message.answer(
        get_localized_text(language, 'current_limit_info').format(
            category=message.text,
            limit=current_limit
        ) + "\n\n" + get_localized_text(language, 'enter_new_limit'),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=get_localized_text(language, 'cancel'))]],
            resize_keyboard=True
        )
    )
    await state.set_state(LimitStates.setting_limit)


@router.message(LimitStates.setting_limit)
async def process_limit_setting(message: Message, state: FSMContext):
    """Обработка установки нового лимита"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    data = await state.get_data()

    if message.text == get_localized_text(language, 'cancel'):
        await handle_back_button(message, state)
        return

    try:
        limit = float(message.text.replace(',', '.'))
        if limit < 0:
            raise ValueError

        await set_category_limit(user_id, data['category'], limit)

        settings = await get_user_currency_settings(user_id)
        currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(settings['currency'], "₽")

        await message.answer(
            get_localized_text(language, 'limit_set_success').format(
                category=data['category'],
                limit=f"{limit:.2f}{currency_symbol}"
            ),
            reply_markup=settings_keyboard(language)
        )
        await state.clear()
    except ValueError:
        await message.answer(get_localized_text(language, 'invalid_amount'))

@router.message(NotificationStates.waiting_choice)
async def process_notification_choice(message: Message, state: FSMContext):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    if message.text in [get_localized_text(language, 'notifications_on'),
                        get_localized_text(language, 'notifications_off')]:
        new_status = message.text == get_localized_text(language, 'notifications_on')
        await set_notification_status(user_id, new_status)

        status_text = get_localized_text(language,
                                         'notifications_status_on' if new_status else 'notifications_status_off')
        await message.answer(
            status_text,
            reply_markup=settings_keyboard(language)
        )
    else:
        await message.answer(
            get_localized_text(language, 'select_option'),
            reply_markup=settings_keyboard(language)
        )

    await state.clear()
