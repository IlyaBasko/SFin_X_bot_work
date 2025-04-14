from typing import Dict


def get_localized_text(language_code: str, text_key: str) -> str:
    translations: Dict[str, Dict[str, str]] = {
        'ru': {
            # Главное меню
            'balance': "Баланс",
            'report': "Отчёт",
            'add_operation': "Добавить операцию",
            'settings': "Настройки",
            'help': "Справка",
            'back': "НАЗАД",

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
            'help_message': (
                "📚 Справка по функциям бота:\n\n"
                "Баланс - показывает ваш текущий баланс\n"
                "Отчёт - предоставляет детализированный отчет\n"
                "Настройки - изменение параметров бота"
            ),

            # Валюты
            'currency_rub': "RUB ₽",
            'currency_usd': "USD $",
            'currency_eur': "EUR €",

            # Уведомления
            'notifications_menu': "🔔 Настройки уведомлений",
            'notifications_on': "✅ Уведомления включены",
            'notifications_off': "🔕 Уведомления выключены",
            'notifications_current': "Текущий статус: {status}",
            'notifications_toggle': "Нажмите, чтобы {action}",

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
            'help': "Help",
            'back': "BACK",

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
            'help_message': (
                "📚 Bot functions help:\n\n"
                "Balance - shows your current balance\n"
                "Report - provides detailed statistics\n"
                "Settings - change bot parameters"
            ),

            # Валюты
            'currency_rub': "RUB ₽",
            'currency_usd': "USD $",
            'currency_eur': "EUR €",

            # Уведомления
            'notifications_menu': "🔔 Notifications settings",
            'notifications_on': "✅ Notifications enabled",
            'notifications_off': "🔕 Notifications disabled",
            'notifications_current': "Current status: {status}",
            'notifications_toggle': "Click to {action}",

            # Системные сообщения
            'operation_added': "✅ Operation added",
            'settings_saved': "Settings saved",
            'select_option': "Select option:"
        }
    }
    return translations.get(language_code, translations['ru']).get(text_key, text_key)