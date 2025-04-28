from typing import Dict


def get_localized_text(language_code: str, text_key: str) -> str:
    translations: Dict[str, Dict[str, str]] = {
        'ru': {
            # Главное меню
            'balance': "Баланс",
            'report': "Отчёт",
            'add_operation': "Добавить операцию",
            'settings': "Настройки",
            'back': "НАЗАД",
            'add_expense': "Добавить расход",
            'add_income': "Добавить доход",
            'select_category': "Выберите категорию:",
            'select_report_period': "Выберите период для отчета",
            'report_for_period': "Отчет за {period}",
            'income_by_category': "Доходы по категориям",
            'expense_by_category': "Расходы по категориям",
            'daily_report': "Ежедневный отчет",
            'weekly_report': "Еженедельный отчет",
            'monthly_report': "Ежемесячный отчет",
            'currency_changed': "✅ Валюта изменена на {currency}",
            'currency_not_changed': "Валюта не изменилась",
            'export': "Экспорт",
            'statistics': "Статистика",
            'russian_language': "Русский",
            'english_language': "English",  # Оставляем English для единообразия
            'language_changed': "✅ Язык изменен на Русский",
            'amount': "Сумма",
            'category': "Категория",
            'comment': "Комментарий",
            'day': "день",
            'week': "неделю",
            'month': "месяц",
            'current_balance': "Текущий баланс",
            'total_operations': "Количество операций",
            'total_income': "Общий доход",
            'total_expense': "Общий расход",
            'top_income_categories': "Топ категорий доходов",
            'top_expense_categories': "Топ категорий расходов",
            'operations_count': "операций",
            'please_select': "Пожалуйста, выберите из предложенных вариантов",
            'invalid_amount': "Пожалуйста, введите корректную сумму (положительное число)",
            'no_data': "Нет данных",
            'file_too_large': "Файл слишком большой для отправки",
            'finance_operations': "Ваши финансовые операции",
            'help': "Справка",
            'balance_help_desc': "показывает текущий баланс и финансовую статистику",
            'report_help_desc': "генерация отчетов за выбранный период",
            'settings_help_desc': "настройки валюты, языка и уведомлений",
            'add_operation_help_desc': "добавление новых доходов/расходов",
            'statistics_help_desc': "подробная статистика по операциям",
            'export_help_desc': "экспорт данных в CSV-файл",
            'help_footer': "Выберите нужный пункт в меню для работы с функцией.",

            # Настройки
            'change_currency': "Изменить валюту",
            'set_limits': "Установить лимиты",
            'language': "Язык",
            'notifications': "Уведомления",

            # Команды
            'welcome_message': (
                "Привет, {first_name}! Я бот для учета финансов.\n\n"
                "Доступные команды:\n"
                "{commands}"
            ),
            'available_commands': (
                "• Баланс - текущее состояние\n"
                "• Отчёт - статистика\n"
                "• Добавить операцию - новая запись"
            ),

            # Валюты
            'currency_rub': "RUB ₽",
            'currency_usd': "USD $",
            'currency_eur': "EUR €",

            # Уведомления
            'notifications_menu': "🔔 Настройки уведомлений",
            'notifications_status_on': "✅ Уведомления включены",
            'notifications_status_off': "🔕 Уведомления выключены",
            'notifications_current': "Текущий статус: {status}",
            'notifications_toggle': "Нажмите, чтобы {action}",
            'notifications_on': "🔔 Включить уведомдения",
            'notifications_off': "🔕 Выключить уведомдения",

            # Системные сообщения
            'operation_added': "✅ Операция добавлена",
            'settings_saved': "Настройки сохранены",
            'select_option': "Выберите опцию:"

        },
        'en': {
            # Главное меню
            'balance': "Balance",
            'report': "Report",
            'add_operation': "Add operation",
            'settings': "Settings",
            'back': "BACK",
            'add_expense': "Add expense",
            'add_income': "Add income",
            'select_category': "Select category:",
            'select_report_period': "Select report period",
            'report_for_period': "Report for {period}",
            'income_by_category': "Income by category",
            'expense_by_category': "Expense by category",
            'daily_report': "Daily report",
            'weekly_report': "Weekly report",
            'monthly_report': "Monthly report",
            'currency_changed': "✅ Currency changed to {currency}",
            'currency_not_changed': "Currency not changed",
            'export': "Export",
            'statistics': "Statistics",
            'russian_language': "Russian",
            'english_language': "English",
            'language_changed': "✅ Language changed to English",
            'amount': "Amount",
            'category': "Category",
            'comment': "Comment",
            'day': "day",
            'week': "week",
            'month': "month",
            'current_balance': "Current balance",
            'total_operations': "Number of operations",
            'total_income': "Total income",
            'total_expense': "Total expense",
            'top_income_categories': "Top income categories",
            'top_expense_categories': "Top expense categories",
            'operations_count': "operations",
            'please_select': "Please select from the available options",
            'invalid_amount': "Please enter a valid amount (positive number)",
            'no_data': "No data available",
            'file_too_large': "File is too large to send",
            'finance_operations': "Your financial operations",
            'help': "Help",
            'balance_help_desc': "shows current balance and financial statistics",
            'report_help_desc': "generate reports for selected period",
            'settings_help_desc': "currency, language and notifications settings",
            'add_operation_help_desc': "add new income/expense operations",
            'statistics_help_desc': "detailed operations statistics",
            'export_help_desc': "export data to CSV file",
            'help_footer': "Select menu item to work with the function.",

            # Настройки
            'change_currency': "Change currency",
            'set_limits': "Set limits",
            'language': "Language",
            'notifications': "Notifications",

            # Команды
            'welcome_message': (
                "Hello, {first_name}! I'm a finance tracking bot.\n\n"
                "Available commands:\n"
                "{commands}"
            ),
            'available_commands': (
                "• Balance - current state\n"
                "• Report - statistics\n"
                "• Add operation - new record"
            ),

            # Валюты
            'currency_rub': "RUB ₽",
            'currency_usd': "USD $",
            'currency_eur': "EUR €",

            # Уведомления
            'notifications_menu': "🔔 Notifications settings",
            'notifications_status_on': "✅ Notifications enabled",
            'notifications_status_off': "🔕 Notifications disabled",
            'notifications_current': "Current status: {status}",
            'notifications_toggle': "Click to {action}",
            'notifications_on': "🔔 Turn on notifications",
            'notifications_off': "🔕 Turn off notifications",

            # Системные сообщения
            'operation_added': "✅ Operation added",
            'settings_saved': "Settings saved",
            'select_option': "Select option:"
        }
    }
    return translations.get(language_code, translations['ru']).get(text_key, text_key)