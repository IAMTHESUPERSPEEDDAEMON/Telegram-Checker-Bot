from telegram import Update
from telegram.ext import ContextTypes

from services.user_service import UserService
from views.telegram_view import TelegramView


class UserController:
    def __init__(self):
        self.user_service = UserService()
        self.view = TelegramView()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /start"""
        await self.user_service.add_user(update.effective_user.id, update.effective_user.username)
        await self.view.send_welcome_message(update)
