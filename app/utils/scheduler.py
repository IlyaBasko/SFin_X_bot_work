from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.requests import get_goals_for_all_users
from app.database.models import get_user_language
from aiogram import Bot
from app.database.locales import get_localized_text

async def check_goals(bot):
    """Проверяет цели и отправляет уведомления о завершении"""
    goals_by_user = await get_goals_for_all_users()
    for user_id, goals in goals_by_user.items():
        language = await get_user_language(user_id)
        for goal in goals:
            percent = min(100, round((goal['current_amount'] / goal['target_amount']) * 100, 1))
            if percent >= 100 and not goal['is_completed']:
                message = f"🎉 Поздравляем! Вы достигли цели '{goal['name']}'!"
                try:
                    await bot.send_message(user_id, message)
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


def start_scheduler(bot):
    """
    Запускает планировщик задач.
    """
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(check_goals, 'cron', hour=9, minute=0, args=(bot,))  # Ежедневно в 9:00
        scheduler.start()
        print("Планировщик задач запущен.")
    except Exception as e:
        print(f"Ошибка при запуске планировщика: {e}")