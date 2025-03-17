from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.keyboards.kbReply import main, operation_category_keyboard

router = Router()


user_data = {}

class AddOperation(StatesGroup):
    category = State()
    amount = State()
    comment = State()
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

    if category == "Добавить доход":
        user_data[user_id]['income'].append({'amount': amount, 'comment': comment})
    else:
        user_data[user_id]['expense'].append({'amount': amount, 'comment': comment})

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