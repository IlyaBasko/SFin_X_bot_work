import os
import csv
import asyncpg
import aiofiles
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

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
    # Здесь можно реализовать получение актуальных курсов с ЦБ РФ или другого API
    rates = {
        'USD': 90.50,  # 1 USD = 90.50 RUB
        'EUR': 98.75,  # 1 EUR = 98.75 RUB
        'RUB': 1.0
    }

    conn = await get_connection()
    try:
        for currency, rate in rates.items():
            await conn.execute('''
            INSERT INTO currencies (code, rate_to_rub, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (code) DO UPDATE
            SET rate_to_rub = EXCLUDED.rate_to_rub,
                updated_at = NOW()
            ''', currency, Decimal(rate))
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