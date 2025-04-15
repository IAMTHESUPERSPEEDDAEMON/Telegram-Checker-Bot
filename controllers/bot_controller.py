from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from controllers.checker_controller import CheckerController
from controllers.session_controller import SessionController
from controllers.proxy_controller import ProxyController
from controllers.user_controller import UserController
from utils.logger import Logger
from views.telegram_view import TelegramView
from utils.csv_handler import CSVHandler
from config.config import BOT_TOKEN, WAITING_FOR_CODE, WAITING_FOR_PASSWORD
from utils.admin_checker import is_admin

logger = Logger()


class BotController:
    def __init__(self):
        self.checker = CheckerController()
        self.session_controller = SessionController()
        self.proxy_controller = ProxyController()
        self.user_controller = UserController()
        self.view = TelegramView()
        self.csv_handler = CSVHandler()

        # Создаем приложение
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики команд и сообщений"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.user_controller.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # Админские команды
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("update_session", self.session_controller.update_session_command))
        self.app.add_handler(CommandHandler("delete_session", self.session_controller.delete_session_command))
        self.app.add_handler(CommandHandler("check_sessions", self.session_controller.check_sessions_command))
        self.app.add_handler(
            CommandHandler("assign_proxys_to_sessions", self.session_controller.assign_proxies_to_sessions_command))
        self.app.add_handler(CommandHandler("add_proxy", self.proxy_controller.add_proxy_command))
        self.app.add_handler(CommandHandler("update_proxy", self.proxy_controller.update_proxy_command))
        self.app.add_handler(CommandHandler("delete_proxy", self.proxy_controller.delete_proxy_command))
        self.app.add_handler(CommandHandler("check_proxies", self.proxy_controller.check_proxies_command))
        # Регистрация обработчика беседы для добавления сессии
        add_session_conv = ConversationHandler(
            entry_points=[CommandHandler('add_session', self.session_controller.start_add_session)],
            states={
                WAITING_FOR_CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.session_controller.process_code)],
                WAITING_FOR_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.session_controller.process_password)]
            },
            fallbacks=[CommandHandler('cancel', self.session_controller.cancel_add_session)]
        )
        self.app.add_handler(add_session_conv)

        # Файлы
        self.app.add_handler(MessageHandler(filters.Document.FileExtension('csv'), self.process_csv))

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /help"""
        await self.view.send_help_message(update)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /status - показывает статус сессий и прокси"""
        # Проверяем, является ли пользователь администратором
        if not await is_admin(update):
            return

        # Получаем статус сессий и прокси
        sessions_stats = await self.session_controller.get_sessions_stats()
        proxies_stats = await self.proxy_controller.get_proxies_stats()

        # Отправляем статус
        await self.view.send_status_message(update, sessions_stats['message'], proxies_stats['message'])

    """Блок работы чекера ==========================================================================================="""

    async def process_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный CSV файл"""
        # Получаем информацию о файле
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name

        # Сообщаем пользователю, что начинаем обработку
        await self.view.send_message(
            update,
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
                "Проверяю номера из файла на наличие в Telegram..."
            )

            # Запускаем процесс проверки
            result = await self.checker.process_csv_file(temp_path, update.effective_user.id)

            if result:
                # Отправляем результаты пользователю
                await self.view.send_check_results(update, result)

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
                    "Не удалось найти номера с Telegram в вашем файле или произошла ошибка при обработке."
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке файла: {e}")
            await self.view.send_message(
                update,
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
