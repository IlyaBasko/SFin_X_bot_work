from aiogram import Router

from aiogram.types import Message
from aiogram.filters import Command, CommandObject, CommandStart

from app.keyboards import kbReply

router = Router()

@router.message(CommandStart())
async  def start(message: Message):
    await message.answer("Hello", reply_markup=kbReply.main )