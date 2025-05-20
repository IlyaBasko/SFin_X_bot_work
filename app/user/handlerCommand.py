import os

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from app.database.locales import get_localized_text
from app.database.models import add_user, update_user_activity, get_user_language
from app.keyboards.kbReply import get_localized_keyboard

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    language = await get_user_language(user.id)  # Получаем сохраненный язык или 'ru' по умолчанию
    # Регистрируем пользователя в БД
    await add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Обновляем активность
    await update_user_activity(user.id)

    # Локализованное приветствие
    welcome_text = get_localized_text(language, 'welcome_message').format(
        first_name=user.first_name,
        commands=get_localized_text(language, 'available_commands')
    )

    await message.answer(
        welcome_text,
        reply_markup=get_localized_keyboard(language)  # Локализованная клавиатура
    )


from app.database.models import export_to_csv, cleanup_file
from aiogram.types import FSInputFile


@router.message(
    (F.text == get_localized_text('ru', 'export')) |
    (F.text == get_localized_text('en', 'export')) |
    (F.text == '/export'))
async def handle_export(message: Message):
    user_id = message.from_user.id
    language = await get_user_language(user_id)

    try:
        filename = await export_to_csv(user_id)

        if not filename:
            await message.answer(get_localized_text(language, 'no_data'))
            return

        await message.answer_document(
            FSInputFile(filename),
            caption=get_localized_text(language, 'export_success')
        )
    except Exception as e:
        print(f"Export failed: {e}")
        await message.answer(get_localized_text(language, 'export_failed'))
    finally:
        if filename and os.path.exists(filename):
            await cleanup_file(filename)