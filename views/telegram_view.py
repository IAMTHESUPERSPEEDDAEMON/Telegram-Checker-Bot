from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


class TelegramView:
    """
    Класс для отображения сообщений в Telegram.
    Не содержит бизнес-логики, только методы для формирования интерфейса бота
    """
    def __init__(self, state_manager):
        self.state_manager = state_manager
    # Вид главного меню
    async def show_main_menu(self, update: Update, is_admin: bool):
        """Показывает главное меню бота с кнопками"""
        # Кнопки для всех пользователей
        keyboard = [[InlineKeyboardButton("📋 Помощь", callback_data="help")]]

        # Кнопки только для админов
        if is_admin:
            keyboard.append([
                InlineKeyboardButton("🔑 Управление сессиями", callback_data="session_menu"),
                InlineKeyboardButton("🌐 Управление прокси", callback_data="proxy_menu")
            ])
            keyboard.append([
                InlineKeyboardButton("📊 Статус всей хуйни", callback_data="status")
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        if hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
            await update.callback_query.message.edit_text(
                "📱 *Главное меню*\n\nЭтот бот предназначен для проверки номеров из CSV на наличие тг\n\nВыберите действие:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "📱 *Главное меню*\n\nЭтот бот предназначен для проверки номеров из CSV на наличие тг\n\nВыберите действие:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_proxy_menu(self, update: Update):
        """Показывает меню управления прокси"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Добавить прокси", callback_data="add_proxy"),
                InlineKeyboardButton("✏️ Изменить прокси", callback_data="update_proxy")
            ],
            [
                InlineKeyboardButton("❌ Удалить прокси", callback_data="delete_proxy"),
                InlineKeyboardButton("🔍 Проверить прокси", callback_data="check_proxies")
            ],
            [InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "🌐 *Управление прокси*\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def show_session_menu(self, update: Update):
        """Показывает меню управления сессиями"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Добавить сессию", callback_data="add_session"),
                InlineKeyboardButton("✏️ Изменить сессию", callback_data="update_session")
            ],
            [
                InlineKeyboardButton("❌ Удалить сессию", callback_data="delete_session"),
                InlineKeyboardButton("🔍 Проверить сессии", callback_data="check_sessions")
            ],
            [
                InlineKeyboardButton("🔄 Назначить прокси сессиям", callback_data="assign_proxys_to_sessions")
            ],
            [InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "🔑 *Управление сессиями*\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def send_help_message(self, update: Update):
        """Отправляет справочное сообщение"""
        keyboard = [[InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "🔑 *Help menu*\n\nВ даном боте вы можете загрузить CSV документ для проверки номеров на наличие ТГ, "
            "бот вернёт документ в исходном виде, но только с номерами где есть ТГ\n"
            "\n*Формат таблицы файла: phone, name, ...*\n"
            "\n📋*Важно чтобы первый столбец был номером*"
            "\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def add_proxy_menu(self, update: Update):
        """Показывает меню добавления сессии"""
        keyboard = [[InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "➕ <b>Добавление прокси</b>\n"
            "\nЧтобы добавить прокси, отправьте сообщение в формате: "
            "<code>&lt;proxy_type&gt; &lt;login:password@host:port&gt;</code>\n"
            "\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    async def show_result_message(self, update: Update, result: dict):
        """Отправляет результат операции на основе словаря с ключами status и message"""
        text = ''
        keyboard = [[InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if result['status'] == 'success':
            text = f"✅ {result['message']}"
        else:
            text = f"❌ Ошибка: {result['message']}"

        await update.callback_query.message.edit_text(
            "➕ <b>Результат выполнения:<b>\n"
            f"\n{text}\n"
            "\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    async def show_status_results_menu(self, update: Update, sessions_status: str, proxies_status: str):
        """Отправляет сообщение со статусом сессий и прокси"""
        keyboard = [[InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="main_menu")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "➕ *Статус сессий и прокси:*\n"
            f"\nСтатус сессий: {sessions_status}\nСтатус прокси: {proxies_status} \n"
            "\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    # Методы для динамического контента
    async def send_message(self, update: Update, message: str):
        """Отправляет обычное текстовое сообщение"""
        await update.message.reply_text(message)

    async def send_result_message(self, update: Update, result: dict):
        """
        Отправляет результат операции на основе словаря с ключами status и message
        """
        if result['status'] == 'success':
            await update.message.reply_text(f"✅ {result['message']}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {result['message']}")

    async def send_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_path: str, caption: str):
        """Отправляет файл пользователю"""
        with open(file_path, 'rb') as file:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=file, caption=caption)

    async def send_code_request(self, chat_id, context, phone):
        """Отправляет запрос кода подтверждения пользователю"""
        message = f"📱 Введите код подтверждения для номера {phone}:"
        sent_msg = await context.bot.send_message(chat_id=chat_id, text=message)
        return sent_msg.message_id

    async def send_password_request(self, chat_id, context, phone):
        """Отправляет запрос пароля двухфакторной аутентификации"""
        message = f"🔐 Введите пароль двухфакторной аутентификации для номера {phone}:"
        sent_msg = await context.bot.send_message(chat_id=chat_id, text=message)
        return sent_msg.message_id

    async def send_start_csv_process(self, update: Update):
        """Отправляет сообщение о начале обработки CSV файла"""
        message = f"Начинаю обработку файла {update.message.document.file_name}. Это может занять некоторое время..."
        await update.message.reply_text(message)
