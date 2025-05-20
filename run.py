import os
import asyncio
from aiogram import Bot, Dispatcher
from app.utils.scheduler import start_scheduler
from app.admin.handlers import router as admin_router
from app.user import handlerCommand, handlerQuests, reminders
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from app.database.models import init_db, add_admin


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPERADMIN_ID = int(os.getenv("SUPERADMIN_ID"))

async def shutdown(dispatcher: Dispatcher, bot: Bot):
    """Обработка завершения работы"""
    await dispatcher.storage.close()
    await bot.session.close()

async def main():
    # Инициализация базы данных перед запуском бота
    try:
        await init_db()

        # Добавляем первого администратора (ваш ID)
        await add_admin(SUPERADMIN_ID, "admin", is_superadmin=True)
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        return

    bot = Bot(BOT_TOKEN,
              default=DefaultBotProperties(parse_mode='HTML')
              )
    dp = Dispatcher()
    dp.include_routers(
        handlerCommand.router,
        handlerQuests.router,
        admin_router,
        reminders.router
    )
    start_scheduler(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown(dp, bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')