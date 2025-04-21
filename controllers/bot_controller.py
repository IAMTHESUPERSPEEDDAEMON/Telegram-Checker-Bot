from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler
from controllers.checker_controller import CheckerController
from controllers.session_controller import SessionController
from controllers.proxy_controller import ProxyController
from controllers.user_controller import UserController
from utils.logger import Logger
from views.telegram_view import TelegramView
from config.config import BOT_TOKEN, WAITING_FOR_CODE, WAITING_FOR_PASSWORD
from utils.admin_checker import is_admin

logger = Logger()


class BotController:
    def __init__(self):
        self.view = TelegramView()
        self.checker = CheckerController(self.view)
        self.session_controller = SessionController(self.view)
        self.proxy_controller = ProxyController(self.view)
        self.user_controller = UserController(self.view)

        # Создаем приложение
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики команд и сообщений"""
        # Базовые команды
        self.app.add_handler(CommandHandler("start", self.show_main_menu))
        self.app.add_handler(CommandHandler("menu", self.show_main_menu))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # Общий обработчик для всех кнопок
        self.app.add_handler(CallbackQueryHandler(self.handle_button_press))

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
        self.app.add_handler(MessageHandler(filters.Document.FileExtension('csv'), self.checker.start_processing_csv))

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает главное меню бота с кнопками"""
        await self.user_controller.save_user_data(update)
        is_admin_user = await is_admin(update)
        await self.view.show_main_menu(update, is_admin_user)

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

    async def handle_button_press(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает нажатия на кнопки меню"""
        query = update.callback_query
        await query.answer()  # Отвечаем на callback запрос

        callback_data = query.data

        # Обработка навигации по меню
        if callback_data == "main_menu":
            await self.show_main_menu(update, context)
            return
        elif callback_data == "proxy_menu":
            if await is_admin(update):
                await self.view.show_proxy_menu(update)
            return
        elif callback_data == "session_menu":
            if await is_admin(update):
                await self.view.show_session_menu(update)
            return

    def run(self):
        """Запускает бота"""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
