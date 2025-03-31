import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, List, Union, Optional


async def add_operation(user_id: int, op_type: str, amount: float,
                        category: str, comment: str) -> bool:
    """Добавление новой операции"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Добавляем операцию
            await db.execute(
                '''
                INSERT INTO operations 
                (user_id, type, amount, category, comment, operation_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (user_id, op_type, amount, category, comment, now)
            )

            # Обновляем активность пользователя
            await db.execute(
                '''
                UPDATE users 
                SET last_activity_date = ?
                WHERE user_id = ?
                ''',
                (now, user_id)
            )

            await db.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении операции: {e}")
            await db.rollback()
            return False


async def get_balance(user_id: int,
                      period_days: Optional[int] = None) -> Dict[str, float]:
    """Получение баланса пользователя"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        query = '''
        SELECT 
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM operations
        WHERE user_id = ?
        '''

        params = [user_id]

        if period_days:
            date_from = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d %H:%M:%S")
            query += ' AND operation_date >= ?'
            params.append(date_from)

        cursor = await db.execute(query, tuple(params))
        result = await cursor.fetchone()

        if not result:
            return {'income': 0.0, 'expense': 0.0, 'balance': 0.0}

        income = result[0] or 0.0
        expense = result[1] or 0.0
        return {
            'income': float(income),
            'expense': float(expense),
            'balance': float(income - expense)
        }


async def get_operations_report(user_id: int,
                                days: int = 7) -> Dict[str, List[Dict]]:
    """Получение отчета за период"""
    async with aiosqlite.connect('SFin_X_bot.db') as db:
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        cursor = await db.execute('''
            SELECT type, category, SUM(amount), COUNT(*)
            FROM operations
            WHERE user_id = ? AND operation_date >= ?
            GROUP BY type, category
            ORDER BY type, SUM(amount) DESC
            ''', (user_id, date_from))

        report = {'income': [], 'expense': []}
        async for row in cursor:
            op_type, category, total, count = row
            report[op_type].append({
                'category': category,
                'total': float(total),
                'count': count
            })

        return report