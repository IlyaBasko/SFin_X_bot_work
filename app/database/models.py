import os
import csv
import aiosqlite
import aiofiles
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB лимит Telegram


async def init_db():
    """Инициализация базы данных"""
    try:
        async with aiosqlite.connect('SFin_X_bot.db') as db:
            # Включаем поддержку внешних ключей
            await db.execute("PRAGMA foreign_keys = ON")

            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registration_date TEXT,
                    last_activity_date TEXT
                )
            ''')

            # Таблица операций
            await db.execute('''
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT CHECK(type IN ('income', 'expense')),
                    amount REAL,
                    category TEXT,
                    comment TEXT,
                    operation_date TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')

            # Индексы для ускорения запросов
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_operations_user 
                ON operations(user_id)
            ''')
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_operations_date 
                ON operations(operation_date)
            ''')

            await db.commit()
            print("База данных успешно инициализирована")
    except Exception as e:
        print(f"Ошибка инициализации БД: {str(e)}")
        raise


async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    """Добавление нового пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            '''
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, registration_date, last_activity_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (user_id, username, first_name, last_name, now, now)
        )
        await db.commit()


async def update_user_activity(user_id: int):
    """Обновление даты последней активности пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            '''
            UPDATE users 
            SET last_activity_date = ?
            WHERE user_id = ?
            ''',
            (now, user_id)
        )
        await db.commit()


async def get_operations(user_id: int, period: str = None) -> List[Tuple]:
    """Получение операций пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        query = '''
        SELECT type, amount, category, comment, operation_date 
        FROM operations 
        WHERE user_id = ?
        '''
        params = [user_id]

        if period:
            now = datetime.now()
            if period == 'day':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            query += ' AND operation_date >= ?'
            params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))

        cursor = await db.execute(query, tuple(params))
        return await cursor.fetchall()


async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получение статистики пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        # Общая статистика
        cursor = await db.execute('''
        SELECT 
            COUNT(*) as total_ops,
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as total_income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expense
        FROM operations
        WHERE user_id = ?
        ''', (user_id,))

        stats = await cursor.fetchone()
        result = {
            'total_operations': stats[0] if stats[0] else 0,
            'total_income': float(stats[1]) if stats[1] else 0.0,
            'total_expense': float(stats[2]) if stats[2] else 0.0
        }

        # Статистика по категориям
        cursor = await db.execute('''
        SELECT 
            type, 
            category,
            COUNT(*) as count,
            SUM(amount) as sum
        FROM operations
        WHERE user_id = ?
        GROUP BY type, category
        ORDER BY type, sum DESC
        ''', (user_id,))

        result['categories'] = {}
        async for row in cursor:
            op_type, category, count, sum_amount = row
            if op_type not in result['categories']:
                result['categories'][op_type] = []
            result['categories'][op_type].append({
                'category': category,
                'count': count,
                'sum': float(sum_amount)
            })

        return result


async def export_to_csv(user_id: int) -> Optional[str]:
    """Асинхронный экспорт операций в CSV файл"""
    try:
        operations = await get_operations(user_id)
        if not operations:
            return None

        filename = f"temp/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs('temp', exist_ok=True)

        async with aiofiles.open(filename, mode='w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            await writer.writerow(['Дата', 'Тип', 'Категория', 'Сумма', 'Комментарий'])
            for op in operations:
                await writer.writerow([
                    op[4],  # Дата
                    'Доход' if op[0] == 'income' else 'Расход',
                    op[2],  # Категория
                    op[1],  # Сумма
                    op[3]  # Комментарий
                ])

        return filename
    except Exception as e:
        print(f"Export error: {e}")
        return None


async def cleanup_file(filename: str):
    """Удаление временного файла"""
    try:
        if filename and os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print(f"Ошибка при удалении файла: {e}")
