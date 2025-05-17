import datetime
from app.database.locales import get_localized_text
from app.database.models import get_user_language 
from app.database.requests import get_goals_for_all_users
from aiogram import Bot

async def send_goal_reminders():
    """Отправляет уведомления всем пользователям по их целям"""
    goals = await get_goals_for_all_users()  # Нужно реализовать выборку всех пользователей с целями
    for user_id, user_goals in goals.items():
        language = await get_user_language(user_id)
        for goal in user_goals:
            percent = min(100, round(goal['current_amount'] / goal['target_amount'] * 100, 1))
            message = (
                f"🔔 {get_localized_text(language, 'goal_reminder_title')}\n"
                f"{get_localized_text(language, 'goal_progress')} '{goal['name']}': {percent}% ({goal['current_amount']} из {goal['target_amount']})"
            )
            if goal['deadline']:
                days_left = (goal['deadline'] - datetime.now()).days
                if days_left < 0:
                    message += f"\n⚠️ {get_localized_text(language, 'goal_deadline_passed')}"
                else:
                    message += f"\n📅 {get_localized_text(language, 'goal_days_left').format(days=days_left)}"
            try:
                await Bot.send_message(user_id, message)
            except Exception as e:
                print(f"Failed to send message to {user_id}: {e}")