import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

class TelegramView:
    async def send_welcome_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет приветственное сообщение пользователю"""
        message = "Привет! Я бот для проверки номеров в Telegram. Используйте /help для просмотра команд."
        await update.message.reply_text(message)

    async def send_help_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет справочное сообщение"""
        message = "Доступные команды:\n/start - Запуск бота\n/help - Справка\n/status - Статус прокси и сессий"
        await update.message.reply_text(message)

    async def send_access_denied(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет сообщение об отказе в доступе"""
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")

    async def send_status_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, sessions_status, proxies_status):
        """Отправляет сообщение со статусом сессий и прокси"""
        message = f"Статус сессий: {sessions_status}\nСтатус прокси: {proxies_status}"
        await update.message.reply_text(message)

    async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
        """Отправляет обычное текстовое сообщение"""
        await update.message.reply_text(message)

    async def send_check_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, result):
        """Отправляет результаты проверки номеров"""
        message = f"Найдено {result['telegram_found']} номеров с Telegram из {result['total_checked']}"
        await update.message.reply_text(message)

    async def send_sessions_check_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, results):
        """Отправляет результаты проверки сессий"""
        message = f"Проверено {len(results)} сессий. Рабочие: {sum(1 for r in results if r['status'] == 'ok')}"
        await update.message.reply_text(message)

    async def send_proxies_check_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, results):
        """Отправляет результаты проверки прокси"""
        message = f"Проверено {len(results)} прокси. Рабочие: {sum(1 for r in results if r['status'] == 'ok')}"
        await update.message.reply_text(message)

    async def send_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_path: str, caption: str):
        """Отправляет файл пользователю"""
        with open(file_path, 'rb') as file:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=file, caption=caption)

    async def update_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет информацию о прокси"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 3:
            await self.send_message(update, context, "Использование: /update_proxy <id> <хост> <порт>")
            return

        proxy_id = int(context.args[0])
        host = context.args[1]
        port = int(context.args[2])

        try:
            ProxyController.update_proxy(proxy_id, host, port)
            await self.send_message(update, context, f"Прокси {proxy_id} обновлён.")
        except Exception as e:
            await self.send_message(update, context, f"Ошибка при обновлении прокси: {str(e)}")

    async def update_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет информацию о сессии"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 3:
            await self.send_message(update, context, "Использование: /update_session <id> <api_id> <api_hash>")
            return

        session_id = int(context.args[0])
        api_id = context.args[1]
        api_hash = context.args[2]

        try:
            SessionController.update_session(session_id, api_id, api_hash)
            await self.send_message(update, context, f"Сессия {session_id} обновлена.")
        except Exception as e:
            await self.send_message(update, context, f"Ошибка при обновлении сессии: {str(e)}")
