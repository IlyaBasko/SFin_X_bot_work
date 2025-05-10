import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from decimal import Decimal, InvalidOperation

from app.database.locales import get_localized_text
from app.database.requests import add_operation_to_db
from app.keyboards.kbReply import (operation_category_keyboard, get_localized_keyboard, pomodoro_keyboard,
                                   settings_keyboard, currency_keyboard, language_keyboard, report_period_keyboard)
from app.database.models import (update_user_activity, export_to_csv, get_user_stats,
                                 MAX_FILE_SIZE, get_user_currency_settings, set_user_language,
                                 set_user_currency, get_user_language,
                                  set_notification_status, get_notification_status)
from aiogram.types import FSInputFile

from app.user.quests import calculate_balance, convert_user_operations

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

class PomodoroStates(StatesGroup):
    pomodoro_active = State()

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

# Добавим словарь для хранения активных таймеров
active_pomodoros = {}

async def start_pomodoro_timer(user_id: int, chat_id: int, bot: Bot, language: str):
    """Функция для запуска помидорки (общая логика)"""
    if user_id in active_pomodoros:
        return False  # Уже запущено

    active_pomodoros[user_id] = True

    # Отправляем сообщение о начале
    await bot.send_message(
        chat_id,
        get_localized_text(language, 'pomodoro_start'),
        reply_markup=pomodoro_keyboard(language)
    )

    # Запускаем таймер
    asyncio.create_task(pomodoro_timer(user_id, chat_id, bot, language))
    return True


async def pomodoro_timer(user_id: int, chat_id: int, bot: Bot, language: str):
    """Функция таймера помидорки"""
    try:
        while user_id in active_pomodoros:
            # Рабочее время
            await asyncio.sleep(25 * 60)

            if user_id not in active_pomodoros:
                break

            # Перерыв
            await bot.send_message(
                chat_id,
                get_localized_text(language, 'pomodoro_work_end'),
                reply_markup=pomodoro_keyboard(language)
            )
            await asyncio.sleep(5 * 60)

            if user_id not in active_pomodoros:
                break

            # Конец цикла
            await bot.send_message(
                chat_id,
                get_localized_text(language, 'pomodoro_break_end'),
                reply_markup=pomodoro_keyboard(language)
            )

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Pomodoro timer error: {e}")
    finally:
        if user_id in active_pomodoros:
            del active_pomodoros[user_id]

@router.message((F.text == get_localized_text('ru', 'pomodoro')) | 
               (F.text == get_localized_text('en', 'pomodoro')))
async def start_pomodoro(message: Message, state: FSMContext):
    """Запуск помидорки"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    success = await start_pomodoro_timer(user_id, message.chat.id, message.bot, language)
    
    if not success:
        await message.answer(get_localized_text(language, 'pomodoro_already_running'))
    else:
        await state.set_state(PomodoroStates.pomodoro_active)

@router.message(F.text.contains("⏹"))
async def stop_pomodoro(message: Message, state: FSMContext):
    """Остановка помидорки"""
    user_id = message.from_user.id
    language = await get_user_language(user_id)
    
    if user_id not in active_pomodoros:
        await message.answer(get_localized_text(language, 'pomodoro_not_running'))
        return
    
    # Удаляем из активных таймеров
    if user_id in active_pomodoros:
        del active_pomodoros[user_id]
    
    await state.clear()
    await message.answer(
        get_localized_text(language, 'pomodoro_stop'),
        reply_markup=get_localized_keyboard(language)
    )