from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


class TelegramView:
    """
    Класс для отображения сообщений в Telegram.
    Не содержит бизнес-логики, только методы для формирования интерфейса бота
    """
    # Вид главного меню
    async def show_main_menu(self, update: Update, is_admin: bool):
        """Показывает главное меню бота с кнопками"""
        keyboard = []
        # Кнопки для всех пользователей
        keyboard.append([InlineKeyboardButton("📋 Помощь", callback_data="help")])

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

    # Статические методы для сообщений с фиксированным текстом
    async def send_welcome_message(self, update: Update):
        """Отправляет приветственное сообщение пользователю"""
        message = "Привет! Я бот для проверки номеров в Telegram. Используйте /help для просмотра команд."
        await update.message.reply_text(message)

    async def send_help_message(self, update: Update):
        """Отправляет справочное сообщение"""
        message = ("Доступные команды:\n"
                   "/start - Запуск бота\n"
                   "/help - Справка\n"
                   "/status - Статус прокси и сессий\n"
                   "/add_session - Добавить сессию\n"
                   "/check_sessions - Проверить сессии\n"
                   "/update_session - Обновить данные сессии\n"
                   "/delete_session - Удалить сессию\n")
        await update.message.reply_text(message)

    @staticmethod
    async def send_access_denied(update: Update):
        """Отправляет сообщение об отказе в доступе"""
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")

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

    async def send_status_message(self, update: Update, sessions_status: str,
                                  proxies_status: str):
        """Отправляет сообщение со статусом сессий и прокси"""
        message = f"Статус сессий: {sessions_status}\nСтатус прокси: {proxies_status}"
        await update.message.reply_text(message)

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
