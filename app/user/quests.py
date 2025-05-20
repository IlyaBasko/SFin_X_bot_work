from typing import Dict, Optional
from decimal import Decimal
from app.database.models import get_connection, convert_amount
from app.database.requests import get_operations

# ---- Функции для работы с балансом ----
async def calculate_balance(user_id: int, period: Optional[str] = None) -> Dict:
    """Асинхронный расчет баланса пользователя"""
    operations = await get_operations(user_id, period)

    result = {
        'total_income': 0.0,
        'total_expense': 0.0,
        'income_by_category': {},
        'expense_by_category': {}
    }

    for op in operations:
        op_type = op['type']
        amount = float(op['amount'])
        category = op['comment'] if op['comment'] else op['category']  # Используем комментарий как категорию

        if op_type == 'income':
            result['total_income'] += amount
            if category not in result['income_by_category']:
                result['income_by_category'][category] = 0.0
            result['income_by_category'][category] += amount
        else:
            result['total_expense'] += amount
            if category not in result['expense_by_category']:
                result['expense_by_category'][category] = 0.0
            result['expense_by_category'][category] += amount

    result['balance'] = result['total_income'] - result['total_expense']
    return result

async def convert_user_operations(user_id: int, from_currency: str, to_currency: str):
    """Конвертирует все операции пользователя из одной валюты в другую"""
    conn = await get_connection()
    try:
        operations = await conn.fetch(
            'SELECT id, amount FROM operations WHERE user_id = $1',
            user_id
        )

        for op in operations:
            original_amount = Decimal(op['amount'])
            converted_amount = await convert_amount(original_amount, from_currency, to_currency)

            await conn.execute(
                'UPDATE operations SET amount = $1 WHERE id = $2',
                float(converted_amount), op['id']
            )
    finally:
        await conn.close()