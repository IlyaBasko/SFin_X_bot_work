from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.keyboards.kbReply import main, operation_category_keyboard

router = Router()

user_data = {}

class AddOperation(StatesGroup):
    category = State()
    amount = State()
    comment = State()

class ReportStates(StatesGroup):
    choose_report_type = State()

@router.message(lambda message: message.text == "НАЗАД")
async def handle_back_button(message: Message, state: FSMContext):
    await message.answer(
        "Возвращаемся в главное меню:",
        reply_markup=main
    )
    await state.clear()

@router.message(lambda message: message.text == "Добавить операцию")
async def add_operation(message: Message, state: FSMContext):
    await message.answer(
        "Выберите категорию:",
        reply_markup=operation_category_keyboard()
    )
    await state.set_state(AddOperation.category)

@router.message(AddOperation.category)
async def process_category(message: Message, state: FSMContext):
    if message.text not in ["Добавить расход", "Добавить доход"]:
        await message.answer("Пожалуйста, выберите категорию из предложенных.")
        return

    await state.update_data(category=message.text)
    await message.answer("Введите сумму:")
    await state.set_state(AddOperation.amount)

@router.message(AddOperation.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        await state.update_data(amount=amount)
        await message.answer("Введите комментарий:")
        await state.set_state(AddOperation.comment)
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму.")

@router.message(AddOperation.comment)
async def process_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data['category']
    amount = data['amount']
    comment = message.text

    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {'income': [], 'expense': []}

    operation = {
        'amount': amount,
        'comment': comment,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Добавляем дату операции
    }

    if category == "Добавить доход":
        user_data[user_id]['income'].append(operation)
    else:
        user_data[user_id]['expense'].append(operation)

    await message.answer(
        f"Операция успешно добавлена!\n"
        f"Категория: {category}\n"
        f"Сумма: {amount}\n"
        f"Комментарий: {comment}",
        reply_markup=main
    )
    await state.clear()

def calculate_balance(user_id: int) -> dict:
    if user_id not in user_data:
        return {
            'balance': 0.0,
            'incomes': {},
            'expenses': {}
        }

    incomes = user_data[user_id].get('income', [])
    expenses = user_data[user_id].get('expense', [])

    total_income = sum(item['amount'] for item in incomes)
    total_expense = sum(item['amount'] for item in expenses)

    income_by_category = {}
    for item in incomes:
        category = item['comment']
        if category not in income_by_category:
            income_by_category[category] = 0.0
        income_by_category[category] += item['amount']

    expense_by_category = {}
    for item in expenses:
        category = item['comment']
        if category not in expense_by_category:
            expense_by_category[category] = 0.0
        expense_by_category[category] += item['amount']

    return {
        'balance': total_income - total_expense,
        'incomes': income_by_category,
        'expenses': expense_by_category
    }

@router.message(lambda message: message.text == "Баланс")
async def handle_balance(message: Message):
    user_id = message.from_user.id
    balance_data = calculate_balance(user_id)

    response = f"Ваш текущий баланс: {balance_data['balance']:.2f} руб.\n\n"

    response += "Доходы:\n"
    for category, amount in balance_data['incomes'].items():
        response += f"- {category}: {amount:.2f} руб.\n"

    response += "\nРасходы:\n"
    for category, amount in balance_data['expenses'].items():
        response += f"- {category}: {amount:.2f} руб.\n"

    await message.answer(response, reply_markup=main)

@router.message(lambda message: message.text == "Отчёт")
async def handle_report(message: Message, state: FSMContext):
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

@router.message(ReportStates.choose_report_type)
async def process_report_type(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Нет данных для отчета.", reply_markup=main)
        await state.clear()
        return

    report_type = message.text
    now = datetime.now()

    if report_type == "Ежедневный отчет":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        period = "день"
    elif report_type == "Еженедельный отчет":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(weeks=1)
        period = "неделю"
    elif report_type == "Ежемесячный отчет":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        period = "месяц"
    else:
        await message.answer("Пожалуйста, выберите тип отчета из предложенных.", reply_markup=main)
        return

    # Фильтрация данных по дате
    incomes = user_data[user_id].get('income', [])
    expenses = user_data[user_id].get('expense', [])

    filtered_incomes = [
        item for item in incomes
        if start_date <= datetime.strptime(item.get('date', now.isoformat()), "%Y-%m-%d %H:%M:%S") < end_date
    ]
    filtered_expenses = [
        item for item in expenses
        if start_date <= datetime.strptime(item.get('date', now.isoformat()), "%Y-%m-%d %H:%M:%S") < end_date
    ]

    if not filtered_incomes and not filtered_expenses:
        await message.answer(f"Нет данных для отчета за {period}.", reply_markup=main)
        await state.clear()
        return

    # Формирование отчета
    total_income = sum(item['amount'] for item in filtered_incomes)
    total_expense = sum(item['amount'] for item in filtered_expenses)
    balance = total_income - total_expense

    income_by_category = {}
    for item in filtered_incomes:
        category = item['comment']
        if category not in income_by_category:
            income_by_category[category] = 0.0
        income_by_category[category] += item['amount']

    expense_by_category = {}
    for item in filtered_expenses:
        category = item['comment']
        if category not in expense_by_category:
            expense_by_category[category] = 0.0
        expense_by_category[category] += item['amount']

    # Текстовый отчет
    report = f"Отчет за {period}:\n\n"
    if income_by_category:
        report += "Доходы:\n"
        for category, amount in income_by_category.items():
            report += f"- {category}: {amount:.2f} руб.\n"
    if expense_by_category:
        report += "\nРасходы:\n"
        for category, amount in expense_by_category.items():
            report += f"- {category}: {amount:.2f} руб.\n"
    report += f"\nОбщий доход: {total_income:.2f} руб.\n"
    report += f"Общий расход: {total_expense:.2f} руб.\n"
    report += f"Баланс: {balance:.2f} руб."

    await message.answer(report, reply_markup=main)
    await state.clear()