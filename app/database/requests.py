import asyncpg
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from app.database.models import get_connection

load_dotenv()


async def add_operation(user_id: int, op_type: str, amount: float, currency: str,
                        category: str, comment: str) -> bool:
    """Добавление новой операции"""
    conn = await get_connection()
    try:
        now = datetime.now()

        async with conn.transaction():
            # Добавляем операцию
            await conn.execute(
                '''
                INSERT INTO operations 
                (user_id, type, amount, category, comment, operation_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                ''',
                user_id, op_type, amount, category, comment, now
            )

            # Обновляем активность пользователя
            await conn.execute(
                '''
                UPDATE users 
                SET last_activity_date = $1
                WHERE user_id = $2
                ''',
                now, user_id
            )

            await conn.execute(
                '''
                INSERT INTO operations 
                (user_id, type, amount, currency, category, comment, operation_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ''',
                user_id, op_type, amount, currency, category, comment, datetime.now()
            )

        return True
    except Exception as e:
        print(f"Ошибка при добавлении операции: {e}")
        return False
    finally:
        await conn.close()


async def get_balance(user_id: int,
                      period_days: Optional[int] = None) -> Dict[str, float]:
    """Получение баланса пользователя"""
    conn = await get_connection()
    try:
        query = '''
        SELECT 
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM operations
        WHERE user_id = $1
        '''

        params = [user_id]

        if period_days:
            date_from = datetime.now() - timedelta(days=period_days)
            query += ' AND operation_date >= $2'
            params.append(date_from)

        result = await conn.fetchrow(query, *params)

        if not result:
            return {'income': 0.0, 'expense': 0.0, 'balance': 0.0}

        income = result['income'] or 0.0
        expense = result['expense'] or 0.0
        return {
            'income': float(income),
            'expense': float(expense),
            'balance': float(income - expense)
        }
    finally:
        await conn.close()


async def get_operations_report(user_id: int,
                                days: int = 7) -> Dict[str, List[Dict]]:
    """Получение отчета за период"""
    conn = await get_connection()
    try:
        date_from = datetime.now() - timedelta(days=days)

        rows = await conn.fetch('''
            SELECT type, category, SUM(amount) as total, COUNT(*) as count
            FROM operations
            WHERE user_id = $1 AND operation_date >= $2
            GROUP BY type, category
            ORDER BY type, SUM(amount) DESC
            ''', user_id, date_from)

        report = {'income': [], 'expense': []}
        for row in rows:
            op_type = row['type']
            report[op_type].append({
                'category': row['category'],
                'total': float(row['total']),
                'count': row['count']
            })

        return report
    finally:
        await conn.close()

# ---- Функции для работы с БД ----
async def add_operation_to_db(user_id: int, op_type: str, amount: float, category: str, comment: str) -> bool:
    """Добавление операции в базу данных"""
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432))
        )

        async with conn.transaction():
            # Добавляем операцию
            await conn.execute(
                '''
                INSERT INTO operations 
                (user_id, type, amount, category, comment, operation_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                ''',
                user_id, op_type, amount, category, comment, datetime.now()
            )

            # Обновляем активность пользователя
            await conn.execute(
                '''
                UPDATE users 
                SET last_activity_date = $1
                WHERE user_id = $2
                ''',
                datetime.now(), user_id
            )

        return True
    except Exception as e:
        print(f"Ошибка при добавлении операции: {e}")
        return False
    finally:
        if conn:
            await conn.close()


async def get_operations(user_id: int, period: Optional[str] = None) -> List[Dict]:
    """Получение операций пользователя из БД"""
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432)))

        query = '''
        SELECT type, amount, category, comment, operation_date 
        FROM operations 
        WHERE user_id = $1
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

            query += ' AND operation_date >= $2'
            params.append(start_date)

        return await conn.fetch(query, *params)
    finally:
        if conn:
            await conn.close()