import os
import csv
import aiohttp
from io import BytesIO
import pandas as pd
from aiogram import Bot
import asyncpg
import aiofiles
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB лимит Telegram


async def init_db():
    """Инициализация базы данных"""
    try:
        # Подключение к PostgreSQL
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )

        # Создание таблицы пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registration_date TIMESTAMP,
                last_activity_date TIMESTAMP
            )
        ''')

        # Создание таблицы операций
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS operations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                type TEXT CHECK(type IN ('income', 'expense')),
                amount DECIMAL(12, 2),
                category TEXT,
                comment TEXT,
                operation_date TIMESTAMP
            )
        ''')

        # Создание индексов
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_operations_user 
            ON operations(user_id)
        ''')
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_operations_date 
            ON operations(operation_date)
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS currencies (
                code TEXT PRIMARY KEY,
                rate_to_rub DECIMAL(10, 4),
                updated_at TIMESTAMP
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                currency TEXT DEFAULT 'RUB',
                original_currency TEXT DEFAULT 'RUB',
                updated_at TIMESTAMP DEFAULT NOW()
            )
            ''')

        # Вставляем базовые курсы (примерные)
        await conn.execute('''
            INSERT INTO currencies (code, rate_to_rub, updated_at)
            VALUES 
                ('RUB', 1.0, NOW()),
                ('USD', 0.011, NOW()),
                ('EUR', 0.0095, NOW())
            ON CONFLICT (code) DO NOTHING
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_languages (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                language_code TEXT DEFAULT 'ru',
                updated_at TIMESTAMP DEFAULT NOW()
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_notifications (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                enabled BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT NOW()
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                username TEXT,
                added_at TIMESTAMP DEFAULT NOW(),
                is_superadmin BOOLEAN DEFAULT FALSE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                name TEXT NOT NULL,
                target_amount DECIMAL(12, 2) NOT NULL,
                current_amount DECIMAL(12, 2) DEFAULT 0,
                deadline TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_goals_user 
            ON goals(user_id)
        ''')

        print("База данных успешно инициализирована")
    except Exception as e:
        print(f"Ошибка инициализации БД PostgreSQL: {str(e)}")
        raise
    finally:
        if conn:
            await conn.close()


async def get_connection():
    return await asyncpg.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432))
    )


async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    """Добавление нового пользователя"""
    conn = await get_connection()
    try:
        now = datetime.now()
        await conn.execute(
            '''
            INSERT INTO users 
            (user_id, username, first_name, last_name, registration_date, last_activity_date)
            VALUES ($1, $2, $3, $4, $5, $5)
            ON CONFLICT (user_id) DO NOTHING
            ''',
            user_id, username, first_name, last_name, now
        )
    finally:
        await conn.close()


async def update_user_activity(user_id: int):
    """Обновление даты последней активности пользователя"""
    conn = await get_connection()
    try:
        now = datetime.now()
        await conn.execute(
            '''
            UPDATE users 
            SET last_activity_date = $1
            WHERE user_id = $2
            ''',
            now, user_id
        )
    finally:
        await conn.close()


async def get_operations(user_id: int, period: str = None) -> List[Tuple]:
    """Получение операций пользователя"""
    conn = await get_connection()
    try:
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
        await conn.close()


async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получение статистики пользователя"""
    conn = await get_connection()
    try:
        # Общая статистика
        stats = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total_ops,
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as total_income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expense
        FROM operations
        WHERE user_id = $1
        ''', user_id)

        result = {
            'total_operations': stats['total_ops'] if stats['total_ops'] else 0,
            'total_income': float(stats['total_income']) if stats['total_income'] else 0.0,
            'total_expense': float(stats['total_expense']) if stats['total_expense'] else 0.0
        }

        # Статистика по категориям
        rows = await conn.fetch('''
        SELECT 
            type, 
            category,
            COUNT(*) as count,
            SUM(amount) as sum
        FROM operations
        WHERE user_id = $1
        GROUP BY type, category
        ORDER BY type, sum DESC
        ''', user_id)

        result['categories'] = {}
        for row in rows:
            op_type = row['type']
            category = row['category']
            if op_type not in result['categories']:
                result['categories'][op_type] = []
            result['categories'][op_type].append({
                'category': category,
                'count': row['count'],
                'sum': float(row['sum'])
            })

        return result
    finally:
        await conn.close()


async def export_to_csv(user_id: int) -> Optional[str]:
    """Экспорт операций в CSV файл"""
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
                    op['operation_date'],  # Дата
                    'Доход' if op['type'] == 'income' else 'Расход',
                    op['category'],  # Категория
                    op['amount'],  # Сумма
                    op['comment']  # Комментарий
                ])

        return filename
    except Exception as e:
        print(f"Export error: {e}")
        return None


async def get_currency_rate(currency: str) -> Decimal:
    conn = await get_connection()
    try:
        rate = await conn.fetchval(
            'SELECT rate_to_rub FROM currencies WHERE code = $1',
            currency
        )
        return Decimal(rate) if rate else Decimal(1)
    finally:
        await conn.close()


async def set_user_currency(user_id: int, currency: str):
    conn = await get_connection()
    try:
        original_currency = await conn.fetchval(
            'SELECT original_currency FROM user_settings WHERE user_id = $1',
            user_id
        ) or 'RUB'

        await conn.execute('''
        INSERT INTO user_settings (user_id, currency, original_currency)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE
        SET currency = EXCLUDED.currency,
            updated_at = NOW()
        ''', user_id, currency, original_currency)
    finally:
        await conn.close()


async def get_user_currency_settings(user_id: int) -> dict:
    conn = await get_connection()
    try:
        return await conn.fetchrow(
            'SELECT currency, original_currency FROM user_settings WHERE user_id = $1',
            user_id
        ) or {'currency': 'RUB', 'original_currency': 'RUB'}
    finally:
        await conn.close()


async def update_currency_rates():
    """
    Получает актуальные курсы валют с сайта ЦБ РФ и сохраняет их в БД.
    """
    url = "https://www.cbr.ru/scripts/XML_daily.asp "
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Ошибка загрузки курсов: {response.status}")
                return

            text = await response.text()
            from xml.etree import ElementTree as ET
            root = ET.fromstring(text)

            rates = {'RUB': Decimal('1.0')}  # RUB всегда равен 1

            for valute in root.findall('Valute'):
                char_code = valute.find('CharCode').text
                value = valute.find('Value').text.replace(',', '.')
                nominal = valute.find('Nominal').text
                try:
                    rate_rub = Decimal(value) / Decimal(nominal)
                    rates[char_code] = rate_rub
                except (InvalidOperation, TypeError):
                    continue

            conn = await get_connection()
            try:
                for currency, rate in rates.items():
                    await conn.execute('''
                        INSERT INTO currencies (code, rate_to_rub, updated_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (code) DO UPDATE
                        SET rate_to_rub = EXCLUDED.rate_to_rub,
                            updated_at = NOW()
                    ''', currency, rate)
                print("Курсы валют успешно обновлены")
            finally:
                await conn.close()


async def set_user_language(user_id: int, language_code: str):
    conn = await get_connection()
    try:
        await conn.execute('''
        INSERT INTO user_languages (user_id, language_code)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE
        SET language_code = EXCLUDED.language_code,
            updated_at = NOW()
        ''', user_id, language_code)
    finally:
        await conn.close()


async def get_user_language(user_id: int) -> str:
    conn = await get_connection()
    try:
        lang = await conn.fetchval(
            'SELECT language_code FROM user_languages WHERE user_id = $1',
            user_id
        )
        return lang if lang else 'ru'
    finally:
        await conn.close()


async def convert_amount(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return amount

    from_rate = await get_currency_rate(from_currency)
    to_rate = await get_currency_rate(to_currency)

    # Конвертируем через RUB как базовую валюту
    return (amount / from_rate) * to_rate


async def set_notification_status(user_id: int, enabled: bool):
    conn = await get_connection()
    try:
        await conn.execute('''
        INSERT INTO user_notifications (user_id, enabled)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            updated_at = NOW()
        ''', user_id, enabled)
    finally:
        await conn.close()


async def get_notification_status(user_id: int) -> bool:
    conn = await get_connection()
    try:
        status = await conn.fetchval(
            'SELECT enabled FROM user_notifications WHERE user_id = $1',
            user_id
        )
        return status if status is not None else True  # По умолчанию включены
    finally:
        await conn.close()


async def cleanup_file(filename: str):
    """Удаление временного файла"""
    try:
        if filename and os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print(f"Ошибка при удалении файла: {e}")


async def add_admin(user_id: int, username: str, is_superadmin: bool = False):
    """Добавление администратора"""
    conn = await get_connection()
    try:
        # Проверяем существование пользователя
        user_exists = await conn.fetchval(
            'SELECT 1 FROM users WHERE user_id = $1',
            user_id
        )

        if not user_exists:
            await add_user(user_id, username, '', '')  # Добавляем базовую информацию

        await conn.execute('''
            INSERT INTO admins (user_id, username, is_superadmin)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                is_superadmin = EXCLUDED.is_superadmin
        ''', user_id, username, is_superadmin)
    except Exception as e:
        print(f"Ошибка при добавлении администратора: {e}")
        raise
    finally:
        await conn.close()


async def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    conn = await get_connection()
    try:
        return await conn.fetchval(
            'SELECT 1 FROM admins WHERE user_id = $1',
            user_id
        ) is not None
    finally:
        await conn.close()


async def is_superadmin(user_id: int) -> bool:
    """Проверка прав суперадминистратора"""
    conn = await get_connection()
    try:
        return await conn.fetchval(
            'SELECT is_superadmin FROM admins WHERE user_id = $1',
            user_id
        ) or False
    finally:
        await conn.close()


async def get_all_users_stats():
    """Получение статистики по всем пользователям"""
    conn = await get_connection()
    try:
        # Общая статистика
        stats = await conn.fetchrow('''
            SELECT 
                COUNT(DISTINCT user_id) as total_users,
                SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expense
            FROM operations
        ''')

        # Топ категорий
        top_income = await conn.fetch('''
            SELECT category, SUM(amount) as amount 
            FROM operations 
            WHERE type = 'income'
            GROUP BY category 
            ORDER BY amount DESC 
            LIMIT 5
        ''')

        top_expense = await conn.fetch('''
            SELECT category, SUM(amount) as amount 
            FROM operations 
            WHERE type = 'expense'
            GROUP BY category 
            ORDER BY amount DESC 
            LIMIT 5
        ''')

        return {
            'total_users': stats['total_users'],
            'total_income': float(stats['total_income']) if stats['total_income'] else 0.0,
            'total_expense': float(stats['total_expense']) if stats['total_expense'] else 0.0,
            'top_income_categories': [
                {'category': row['category'], 'amount': float(row['amount'])}
                for row in top_income
            ],
            'top_expense_categories': [
                {'category': row['category'], 'amount': float(row['amount'])}
                for row in top_expense
            ]
        }
    finally:
        await conn.close()


async def export_all_to_excel() -> BytesIO:
    """Экспорт всех данных в Excel"""
    conn = await get_connection()
    try:
        output = BytesIO()

        # Создаем Excel writer с настройками
        with pd.ExcelWriter(
                output,
                engine='xlsxwriter',
                engine_kwargs={'options': {'strings_to_numbers': True}}
        ) as writer:
            workbook = writer.book

            # Лист с пользователями
            users = await conn.fetch("SELECT * FROM users")
            if users:
                df_users = pd.DataFrame(users)
                df_users.to_excel(writer, sheet_name='Пользователи', index=False)
                worksheet = writer.sheets['Пользователи']
                worksheet.set_column('A:F', 20)  # Ширина колонок

            # Лист с операциями
            operations = await conn.fetch("SELECT * FROM operations")
            if operations:
                df_ops = pd.DataFrame(operations)
                df_ops.to_excel(writer, sheet_name='Операции', index=False)
                worksheet = writer.sheets['Операции']
                worksheet.set_column('A:G', 15)

            # Лист с администраторами
            admins = await conn.fetch("SELECT * FROM admins")
            if admins:
                df_admins = pd.DataFrame(admins)
                df_admins.to_excel(writer, sheet_name='Администраторы', index=False)
                worksheet = writer.sheets['Администраторы']
                worksheet.set_column('A:D', 20)

        output.seek(0)
        return output
    except Exception as e:
        print(f"Ошибка при экспорте в Excel: {e}")
        raise
    finally:
        await conn.close()


# Функции для планирования "Цели"
async def add_goal(user_id: int, name: str, target_amount: Decimal, deadline: datetime = None):
    """Создание новой цели"""
    conn = await get_connection()
    try:
        await conn.execute(
            '''
            INSERT INTO goals (user_id, name, target_amount, deadline)
            VALUES ($1, $2, $3, $4)
            ''',
            user_id, name, target_amount, deadline
        )
    finally:
        await conn.close()


async def get_goals(user_id: int) -> List[Dict]:
    """Получить список целей пользователя"""
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            'SELECT * FROM goals WHERE user_id = $1 AND NOT is_completed ORDER BY created_at DESC',
            user_id
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def update_goal_progress(user_id: int, goal_id: int, amount: Decimal, bot: Bot):
    conn = await get_connection()
    try:
        result = await conn.fetchrow(
            'SELECT current_amount, target_amount, name FROM goals WHERE id = $1 AND user_id = $2',
            goal_id, user_id
        )
        if not result:
            return False

        new_amount = result['current_amount'] + amount
        is_completed = False
        message_text = ""

        if new_amount >= result['target_amount']:
            new_amount = result['target_amount']
            is_completed = True
            message_text = f"🎉 Поздравляем! Вы достигли цели '{result['name']}'!"

        await conn.execute(
            '''
            UPDATE goals SET current_amount = $1, is_completed = $2
            WHERE id = $3 AND user_id = $4
            ''',
            new_amount, is_completed, goal_id, user_id
        )

        # Отправка уведомления, если цель завершена
        if is_completed:
            await bot.send_message(user_id, message_text)

        return True
    finally:
        await conn.close()


async def complete_goal(user_id: int, goal_id: int):
    """Завершить цель вручную"""
    conn = await get_connection()
    try:
        await conn.execute(
            'UPDATE goals SET is_completed = TRUE, current_amount = target_amount WHERE id = $1 AND user_id = $2',
            goal_id, user_id
        )
    finally:
        await conn.close()