import asyncio
from aiogram import Bot, Dispatcher

from app.user import handlerCommand, handlerQuests
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(BOT_TOKEN,
              default=DefaultBotProperties(parse_mode='HTML')
    )
    dp = Dispatcher()
    dp.include_routers(
        handlerCommand.router,
        handlerQuests.router
    )
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')