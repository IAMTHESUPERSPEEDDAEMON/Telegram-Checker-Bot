import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from controllers.checker_controller import CheckerController
from controllers.session_controller import SessionController
from controllers.proxy_controller import ProxyController
from utils.logger import Logger
from views.telegram_view import TelegramView
from utils.csv_handler import CSVHandler
from config.config import BOT_TOKEN, ADMIN_IDS, TEMP_DIR
import asyncio

logger = Logger()
# Состояния для ConversationHandler
WAITING_FOR_CODE = 1
WAITING_FOR_PASSWORD = 2

# Словарь для хранения данных сессии во время создания
session_data = {}
class BotController:
    def __init__(self):
        self.checker = CheckerController()
        self.session_controller = SessionController()
        self.proxy_controller = ProxyController()
        self.view = TelegramView()
        self.csv_handler = CSVHandler()

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
        self.app.add_handler(CommandHandler("check_sessions", self.check_sessions_command))
        self.app.add_handler(CommandHandler("update_session", self.update_session_command))
        self.app.add_handler(CommandHandler("delete_session", self.delete_session_command))
        self.app.add_handler(CommandHandler("add_proxy", self.add_proxy_command))
        self.app.add_handler(CommandHandler("check_proxies", self.check_proxies_command))
        self.app.add_handler(CommandHandler("update_proxy", self.update_proxy_command))
        self.app.add_handler(CommandHandler("delete_proxy", self.delete_proxy_command))
        self.app.add_handler(CommandHandler("assign_proxys_to_sessions", self.assign_proxys_to_sessions_command))
        # Регистрация обработчика беседы для добавления сессии
        add_session_conv = ConversationHandler(
            entry_points=[CommandHandler('add_session', self.start_add_session)],
            states={
                WAITING_FOR_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_code)],
                WAITING_FOR_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_password)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel_add_session)]
        )
        self.app.add_handler(add_session_conv)

        # Файлы
        self.app.add_handler(MessageHandler(filters.Document.FileExtension('csv'), self.process_csv))


    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /start"""
        await self.view.send_welcome_message(update, context)
        # to-do USER CONTROLLER


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
        await self.view.send_status_message(update, context, sessions_stats['message'], proxies_stats)

    async def start_add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления сессии"""
        user_id = update.effective_user.id

        # Проверяем, является ли пользователь администратором
        if user_id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return ConversationHandler.END

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                context,
                "Использование: /add_session <телефон> <api_id> <api_hash> [proxy_id]"
            )
            return ConversationHandler.END

        phone = context.args[0]
        api_id = context.args[1]
        api_hash = context.args[2]

        # Сохраняем данные в словаре сессий
        session_data[user_id] = {
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'chat_id': update.effective_chat.id,
            'phone_code_hash': None  # Будет заполнено позже
        }

        # Запускаем процесс создания сессии в отдельной задаче
        asyncio.create_task(self.create_session_async(user_id, update, context))

        # Сообщаем пользователю, что процесс начат
        await self.view.send_message(
            update,
            context,
            f"Начинаем создание сессии для номера {phone}. Ожидайте запрос кода..."
        )

        return WAITING_FOR_CODE

    async def create_session_async(self, user_id, update, context):
        """Запускает процесс создания сессии асинхронно"""
        data = session_data[user_id]

        async def code_callback(phone, phone_code_hash):
            """Колбэк для получения кода подтверждения через Telegram"""
            # Сохраняем phone_code_hash для использования при входе
            session_data[user_id]['phone_code_hash'] = phone_code_hash

            # Отправляем запрос кода пользователю
            await self.view.send_code_request(data['chat_id'], context, phone)

            # Ждем, пока код будет введен (это будет сделано в process_code)
            # Создаем и ждем будущее значение
            session_data[user_id]['code_future'] = asyncio.Future()
            return await session_data[user_id]['code_future']

        async def password_callback(phone):
            """Колбэк для получения пароля через Telegram"""
            # Отправляем запрос пароля пользователю
            await self.view.send_password_request(data['chat_id'], context, phone)

            # Ждем, пока пароль будет введен
            session_data[user_id]['password_future'] = asyncio.Future()
            return await session_data[user_id]['password_future']

        # Запускаем создание сессии с нашими колбэками
        result = await self.session_controller.add_session(
            data['phone'],
            data['api_id'],
            data['api_hash'],
            code_callback=code_callback,
            password_callback=password_callback
        )

        # Отправляем результат пользователю
        await self.view.send_result_message(update, context, result)

        # Завершаем диалог
        return ConversationHandler.END

    async def process_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный код подтверждения"""
        user_id = update.effective_user.id
        code = update.message.text.strip()

        if user_id in session_data and 'code_future' in session_data[user_id]:
            # Устанавливаем результат будущего значения
            if not session_data[user_id]['code_future'].done():
                session_data[user_id]['code_future'].set_result(code)

            await self.view.send_message(
                update,
                context,
                f"✅ Код получен: {code}. Выполняется вход..."
            )

            # Если двухфакторная аутентификация не требуется, процесс завершится автоматически
            # Иначе будет запрошен пароль через password_callback
            return WAITING_FOR_PASSWORD
        else:
            await self.view.send_message(
                update,
                context,
                "❌ Что-то пошло не так. Пожалуйста, начните процесс заново с команды /add_session"
            )
            return ConversationHandler.END

    async def process_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный пароль двухфакторной аутентификации"""
        user_id = update.effective_user.id
        password = update.message.text.strip()

        # Для безопасности, удаляем сообщение с паролем
        await update.message.delete()

        if user_id in session_data and 'password_future' in session_data[user_id]:
            # Устанавливаем результат будущего значения
            if not session_data[user_id]['password_future'].done():
                session_data[user_id]['password_future'].set_result(password)

            await self.view.send_message(
                update,
                context,
                "✅ Пароль получен. Выполняется вход..."
            )

            # Процесс завершится автоматически после проверки пароля
            return ConversationHandler.END
        else:
            await self.view.send_message(
                update,
                context,
                "❌ Что-то пошло не так. Пожалуйста, начните процесс заново с команды /add_session"
            )
            return ConversationHandler.END

    async def cancel_add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменяет процесс добавления сессии"""
        user_id = update.effective_user.id

        if user_id in session_data:
            # Если есть активные futures, отменяем их
            if 'code_future' in session_data[user_id] and not session_data[user_id]['code_future'].done():
                session_data[user_id]['code_future'].cancel()

            if 'password_future' in session_data[user_id] and not session_data[user_id]['password_future'].done():
                session_data[user_id]['password_future'].cancel()

            # Удаляем данные сессии
            del session_data[user_id]

        await self.view.send_message(
            update,
            context,
            "🚫 Процесс добавления сессии отменен."
        )

        return ConversationHandler.END


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
        result = self.session_controller.update_session(session_id, json.loads(''.join(context.args[1:])))


    async def delete_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.session_controller.delete_session(update, context)


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

        session_id = int(context.args[0])
        try:
            new_params = json.loads(context.args[1])
        except ValueError:
            await self.view.send_message(update, context, "Неверный формат параметров.")
            return

        success = self.session_controller.update_session(session_id, new_params)
        await self.view.send_message(update, context, success['message'])


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

    async def assign_proxys_to_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Присваивает прокси к сессиям"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        result = await self.session_controller.assign_proxies_to_sessions()
        await self.view.send_result_message(update, context, result)


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
            logger.error(f"Ошибка при обработке файла: {e}")
            await self.view.send_message(
                update,
                context,
                f"Произошла ошибка при обработке файла: {str(e)}"
            )

    # async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Обрабатывает нажатия на инлайн-кнопки"""
    #     query = update.callback_query
    #     await query.answer()
    #
    #     # Обрабатываем данные колбека
    #     callback_data = query.data
    #
    #     if callback_data.startswith("check_batch_"):
    #         batch_id = int(callback_data.replace("check_batch_", ""))
    #         # Отправляем статус проверки
    #         await self.view.send_batch_status(update, context, batch_id)
    #
    # async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
    #     """Обрабатывает ошибки телеграм-бота"""
    #     logger.error(f"Exception while handling an update: {context.error}")
    #
    #     # Отправляем сообщение об ошибке администраторам
    #     for admin_id in ADMIN_IDS:
    #         try:
    #             error_text = f"🚨 Ошибка в боте: {context.error}"
    #             await self.app.bot.send_message(chat_id=admin_id, text=error_text)
    #         except Exception as e:
    #             logger.error(f"Не удалось отправить уведомление об ошибке администратору {admin_id}: {e}")

    def run(self):
        """Запускает бота"""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)