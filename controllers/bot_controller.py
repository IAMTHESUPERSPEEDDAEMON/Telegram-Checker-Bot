import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from controllers.checker_controller import CheckerController
from controllers.session_controller import SessionController
from controllers.proxy_controller import ProxyController
from views.telegram_view import TelegramView
from utils.csv_handler import CSVHandler
from config.config import BOT_TOKEN, ADMIN_IDS, TEMP_DIR


class BotController:
    def __init__(self):
        self.checker = CheckerController()
        self.session_controller = SessionController()
        self.proxy_controller = ProxyController()
        self.view = TelegramView()
        self.csv_handler = CSVHandler()

        # Добавляем обработчик ошибок
        self.checker.add_error_handler(self.handle_error)

        # Создаем приложение
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики команд и сообщений"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # Админские команды
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("add_session", self.add_session_command))
        self.app.add_handler(CommandHandler("add_proxy", self.add_proxy_command))
        self.app.add_handler(CommandHandler("check_sessions", self.check_sessions_command))
        self.app.add_handler(CommandHandler("check_proxies", self.check_proxies_command))
        self.app.add_handler(CommandHandler("update_proxy", self.update_proxy_command))
        self.app.add_handler(CommandHandler("update_session", self.update_session_command))
        self.app.add_handler(CommandHandler("delete_session", self.delete_session_command))
        self.app.add_handler(CommandHandler("delete_proxy", self.delete_proxy_command))
        self.app.add_handler(CommandHandler("assign_proxys_to_sessions", self.assign_proxys_to_sessions_command))

        # Файлы
        self.app.add_handler(MessageHandler(filters.Document.CSV, self.process_csv))

        # Обработчик колбеков
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Обработчик ошибок
        self.app.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /start"""
        await self.view.send_welcome_message(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /help"""
        await self.view.send_help_message(update, context)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /status - показывает статус сессий и прокси"""
        # Проверяем, является ли пользователь администратором
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        # Получаем статус сессий и прокси
        sessions_stats = await self.session_controller.get_sessions_stats()
        proxies_stats = await self.proxy_controller.get_proxies_stats()

        # Отправляем статус
        await self.view.send_status_message(update, context, sessions_stats, proxies_stats)

    async def add_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /add_session - добавляет новую сессию"""
        # Проверяем, является ли пользователь администратором
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                context,
                "Использование: /add_session <телефон> <api_id> <api_hash> [proxy_id]"
            )
            return

        phone = context.args[0]
        api_id = context.args[1]
        api_hash = context.args[2]
        proxy_id = int(context.args[3]) if len(context.args) > 3 else None

        # Добавляем сессию
        try:
            session_id = self.session_controller.add_session(phone, api_id, api_hash, proxy_id)
            await self.view.send_message(
                update,
                context,
                f"Сессия успешно добавлена (ID: {session_id})"
            )
        except Exception as e:
            await self.view.send_message(
                update,
                context,
                f"Ошибка при добавлении сессии: {str(e)}"
            )

    async def add_proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /add_proxy - добавляет новый прокси"""
        # Проверяем, является ли пользователь администратором
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                context,
                "Использование: /add_proxy <тип> <хост> <порт> [имя пользователя] [пароль]"
            )
            return

        proxy_type = context.args[0]
        host = context.args[1]
        port = int(context.args[2])
        username = context.args[3] if len(context.args) > 3 else None
        password = context.args[4] if len(context.args) > 4 else None

        # Добавляем прокси
        try:
            proxy_id = self.proxy_controller.add_proxy(proxy_type, host, port, username, password)
            await self.view.send_message(
                update,
                context,
                f"Прокси успешно добавлен (ID: {proxy_id})"
            )
        except Exception as e:
            await self.view.send_message(
                update,
                context,
                f"Ошибка при добавлении прокси: {str(e)}"
            )

    async def check_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /check_sessions - проверяет работоспособность сессий"""
        # Проверяем, является ли пользователь администратором
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        await self.view.send_message(update, context, "Начинаем проверку сессий...")

        try:
            results = await self.session_controller.check_all_sessions()
            await self.view.send_sessions_check_results(update, context, results)
        except Exception as e:
            await self.view.send_message(
                update,
                context,
                f"Ошибка при проверке сессий: {str(e)}"
            )

    async def check_proxies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /check_proxies - проверяет работоспособность прокси"""
        # Проверяем, является ли пользователь администратором
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        await self.view.send_message(update, context, "Начинаем проверку прокси...")
        results = await self.proxy_controller.check_all_proxies()
        if results['status'] == 'error':
            await self.view.send_message(update, context, results['message'])
            return
        else:
            await self.view.send_proxies_check_results(update, context, results)


    async def update_proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные прокси."""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 2:
            await self.view.send_message(
                update, context,
                "Использование: /update_proxy <proxy_id> <новые параметры (тип, хост, порт, имя, пароль)>"
            )
            return

        proxy_id = int(context.args[0])
        new_params = context.args[1:]

        success = self.proxy_controller.update_proxy(proxy_id, new_params)
        await self.view.send_message(update, context, success['message'])

    async def update_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные сессии."""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 2:
            await self.view.send_message(
                update, context,
                "Использование: /update_session <session_id> <новые параметры в формате JSON>"
            )
            return

        session_id = int(context.args[0])
        try:
            new_params = json.loads(context.args[1])
        except ValueError:
            await self.view.send_message(update, context, "Неверный формат параметров.")
            return

        success = self.session_controller.update_session(session_id, new_params)
        await self.view.send_message(update, context, success['message'])

    async def delete_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет сессию по указанному ID"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 1:
            await self.view.send_message(update, context, "Не указан ID сессии для удаления.")
            return

        session_id = int(context.args[0])
        result = self.session_controller.delete_session(session_id)
        await self.view.send_message(update, context, result['message'])

    async def delete_proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет прокси по указанному ID"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 1:
            await self.view.send_message(update, context, "Не указан ID прокси для удаления.")
            return

        proxy_id = int(context.args[0])
        result = self.proxy_controller.delete_proxy(proxy_id)
        await self.view.send_message(update, context, result['message'])

    async def process_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный CSV файл"""
        # Получаем информацию о файле
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name

        # Сообщаем пользователю, что начинаем обработку
        await self.view.send_message(
            update,
            context,
            f"Начинаю обработку файла {file_name}. Это может занять некоторое время..."
        )

        try:
            # Скачиваем файл
            file_object = await context.bot.get_file(file_id)
            file_content = await file_object.download_as_bytearray()

            # Сохраняем файл во временную директорию
            temp_path = self.csv_handler.save_temp_file(file_content, file_name)

            # Обрабатываем файл и проверяем номера
            processing_message = await self.view.send_message(
                update,
                context,
                "Проверяю номера из файла на наличие в Telegram..."
            )

            # Запускаем процесс проверки
            result = await self.checker.process_csv_file(temp_path, update.effective_user.id)

            if result:
                # Отправляем результаты пользователю
                await self.view.send_check_results(update, context, result)

                # Отправляем файл с результатами
                await self.view.send_document(
                    update,
                    context,
                    result['file_path'],
                    caption=f"Найдено {result['telegram_found']} номеров с Telegram из {result['total_checked']}"
                )
            else:
                await self.view.send_message(
                    update,
                    context,
                    "Не удалось найти номера с Telegram в вашем файле или произошла ошибка при обработке."
                )

        except Exception as e:
            logging.error(f"Ошибка при обработке файла: {e}")
            await self.view.send_message(
                update,
                context,
                f"Произошла ошибка при обработке файла: {str(e)}"
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает нажатия на инлайн-кнопки"""
        query = update.callback_query
        await query.answer()

        # Обрабатываем данные колбека
        callback_data = query.data

        if callback_data.startswith("check_batch_"):
            batch_id = int(callback_data.replace("check_batch_", ""))
            # Отправляем статус проверки
            await self.view.send_batch_status(update, context, batch_id)

    async def handle_error(self, error_type, message, details=None):
        """Обрабатывает ошибки от CheckerController"""
        # Логируем ошибку
        logging.error(f"Error {error_type}: {message} - {details}")

        # Отправляем сообщение администраторам
        for admin_id in ADMIN_IDS:
            try:
                error_text = f"🚨 Ошибка {error_type}: {message}"
                if details:
                    error_text += f"\nДетали: {details}"

                await self.app.bot.send_message(chat_id=admin_id, text=error_text)
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об ошибке администратору {admin_id}: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ошибки телеграм-бота"""
        logging.error(f"Exception while handling an update: {context.error}")

        # Отправляем сообщение об ошибке администраторам
        for admin_id in ADMIN_IDS:
            try:
                error_text = f"🚨 Ошибка в боте: {context.error}"
                await self.app.bot.send_message(chat_id=admin_id, text=error_text)
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об ошибке администратору {admin_id}: {e}")

    def run(self):
        """Запускает бота"""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)