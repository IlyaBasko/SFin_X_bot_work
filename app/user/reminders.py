from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from app.database.models import get_connection
from app.database.locales import get_localized_text
from app.database.models import get_user_language

router = Router()


class ReminderStates(StatesGroup):
    waiting_task = State()
    waiting_period = State()
    waiting_time = State()


@router.message(
    (F.text == get_localized_text('ru', 'reminders')) |
    (F.text == get_localized_text('en', 'reminders')))
async def show_reminders_menu(message: Message):
    language = await get_user_language(message.from_user.id)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language, 'add_reminder'))],
            [KeyboardButton(text=get_localized_text(language, 'my_reminders'))],
            [KeyboardButton(text=get_localized_text(language, 'back'))]
        ],
        resize_keyboard=True
    )
    await message.answer(get_localized_text(language, 'reminders'), reply_markup=kb)


@router.message(
    (F.text == get_localized_text('ru', 'add_reminder')) |
    (F.text == get_localized_text('en', 'add_reminder')))
async def add_reminder_start(message: Message, state: FSMContext):
    language = await get_user_language(message.from_user.id)
    await message.answer(get_localized_text(language, 'enter_task'))
    await state.set_state(ReminderStates.waiting_task)


@router.message(ReminderStates.waiting_task)
async def process_task(message: Message, state: FSMContext):
    language = await get_user_language(message.from_user.id)
    await state.update_data(task=message.text)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_localized_text(language, 'today'))],
            [KeyboardButton(text=get_localized_text(language, 'tomorrow'))],
            [KeyboardButton(text=get_localized_text(language, 'next_week'))],
            [KeyboardButton(text=get_localized_text(language, 'back'))]
        ],
        resize_keyboard=True
    )

    await message.answer(get_localized_text(language, 'choose_period'), reply_markup=kb)
    await state.set_state(ReminderStates.waiting_period)


@router.message(ReminderStates.waiting_period)
async def process_period(message: Message, state: FSMContext):
    language = await get_user_language(message.from_user.id)

    period_options = {
        get_localized_text(language, 'today'): timedelta(hours=0),
        get_localized_text(language, 'tomorrow'): timedelta(days=1),
        get_localized_text(language, 'next_week'): timedelta(weeks=1)
    }

    if message.text not in period_options:
        await message.answer(get_localized_text(language, 'please_select'))
        return

    due_date = datetime.now() + period_options[message.text]
    await state.update_data(due_date=due_date.date())

    await message.answer(get_localized_text(language, 'enter_time'))
    await state.set_state(ReminderStates.waiting_time)


@router.message(ReminderStates.waiting_time)
async def process_time(message: Message, state: FSMContext):
    language = await get_user_language(message.from_user.id)
    try:
        time_str = message.text.strip()
        hours, minutes = map(int, time_str.split(':'))

        data = await state.get_data()
        due_date = data['due_date']
        due_datetime = datetime.combine(due_date, datetime.min.time()).replace(hour=hours, minute=minutes)

        if due_datetime < datetime.now():
            await message.answer(get_localized_text(language, 'past_time'))
            return

        conn = await get_connection()
        try:
            await conn.execute(
                "INSERT INTO reminders (user_id, task, due_date) VALUES ($1, $2, $3)",
                message.from_user.id, data['task'], due_datetime
            )
            await message.answer(get_localized_text(language, 'reminder_added').format(
                datetime=due_datetime.strftime('%d.%m.%Y %H:%M')
            ))
        finally:
            await conn.close()

    except ValueError:
        await message.answer(get_localized_text(language, 'invalid_time'))
    finally:
        await state.clear()


@router.message(
    (F.text == get_localized_text('ru', 'my_reminders')) |
    (F.text == get_localized_text('en', 'my_reminders')))
async def show_user_reminders(message: Message):
    language = await get_user_language(message.from_user.id)
    conn = await get_connection()
    try:
        reminders = await conn.fetch(
            "SELECT * FROM reminders WHERE user_id = $1 AND NOT is_completed ORDER BY due_date",
            message.from_user.id
        )

        if not reminders:
            await message.answer(get_localized_text(language, 'no_reminders'))
            return

        response = get_localized_text(language, 'your_reminders') + ":\n\n"
        for reminder in reminders:
            response += f"⏰ {reminder['task']} - {reminder['due_date'].strftime('%d.%m.%Y %H:%M')}\n"

        await message.answer(response)
    finally:
        await conn.close()