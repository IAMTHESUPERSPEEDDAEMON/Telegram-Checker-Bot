from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from utils.state_manager import StateManager
from controllers.checker_controller import CheckerController
from controllers.message_handler_controller import MessageHandlerController
from controllers.session_controller import SessionController
from controllers.proxy_controller import ProxyController
from controllers.user_controller import UserController
from utils.logger import Logger
from views.telegram_view import TelegramView
from config.config import BOT_TOKEN
from utils.admin_checker import is_admin

logger = Logger()


class BotController:
    def __init__(self):
        self.state_manager = StateManager()
        self.view = TelegramView(self.state_manager)
        self.checker = CheckerController(self.view, self.state_manager)
        self.session_controller = SessionController(self.view, self.state_manager)
        self.proxy_controller = ProxyController(self.view, self.state_manager)
        self.user_controller = UserController(self.view)

        # Создаем приложение
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Регистрируем обработчики
        self.message_handler_controller = MessageHandlerController(
            self.state_manager,
            self.proxy_controller,
            self.session_controller
        )
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики команд и сообщений"""
        # Базовые команды
        self.app.add_handler(CommandHandler("start", self.show_main_menu))
        self.app.add_handler(CommandHandler("menu", self.show_main_menu))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # Общий обработчик для всех кнопок
        self.app.add_handler(CallbackQueryHandler(self.handle_button_press))

        # Обработчик сообщений
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler_controller.handle))
        # Файл CSV
        self.app.add_handler(MessageHandler(filters.Document.FileExtension('csv'), self.checker.start_processing_csv))

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

        # Обработка действий
        if callback_data == "help":
            await self.help_command(update, context)
        elif callback_data == "status":
            await self.status_command(update, context)
        elif callback_data == "add_proxy":
            await self.proxy_controller.add_proxy_command(update, context)
        elif callback_data == "update_proxy":
            await self.proxy_controller.update_proxy_command(update, context)
        elif callback_data == "delete_proxy":
            await self.proxy_controller.delete_proxy_command(update, context)
        elif callback_data == "check_proxies":
            await self.proxy_controller.check_proxies_command(update, context)
        elif callback_data == "add_session":
            # TODO: проверить добавление сессии и сделать возможность отменить процесс
            await self.session_controller.add_session_command(update, context)
        elif callback_data == "update_session":
            await self.session_controller.update_session_command(update, context)
        elif callback_data == "delete_session":
            await self.session_controller.delete_session_command(update, context)
        elif callback_data == "check_sessions":
            await self.session_controller.check_sessions_command(update, context)
        elif callback_data == "assign_proxys_to_sessions":
            # TODO: проверить работу
            await self.session_controller.assign_proxies_to_sessions_command(update, context)

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
        await self.view.show_status_results_menu(update, sessions_stats['message'], proxies_stats['message'])


    def run(self):
        """Запускает бота"""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
