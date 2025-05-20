from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.requests import get_goals_for_all_users
from app.database.models import get_user_language, get_connection
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


async def check_reminders(bot):
    """Проверяет и отправляет напоминания"""
    conn = await get_connection()
    try:
        now = datetime.now()
        reminders = await conn.fetch(
            "SELECT * FROM reminders WHERE due_date <= $1 AND NOT is_completed",
            now
        )

        for reminder in reminders:
            try:
                language = await get_user_language(reminder['user_id'])
                await bot.send_message(
                    reminder['user_id'],
                    get_localized_text(language, 'reminder_notification').format(
                        task=reminder['task']
                    )
                )
                await conn.execute(
                    "UPDATE reminders SET is_completed = TRUE WHERE id = $1",
                    reminder['id']
                )
            except Exception as e:
                print(f"Failed to send reminder {reminder['id']}: {e}")

    finally:
        await conn.close()


def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_goals, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.add_job(check_reminders, 'interval', minutes=1, args=(bot,))  # Проверка каждую минуту
    scheduler.start()