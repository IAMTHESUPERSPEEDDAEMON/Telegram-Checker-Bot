from telegram import Update
from telegram.ext import ContextTypes

from services.user_service import UserService


class UserController:
    def __init__(self, view):
        self.user_service = UserService()
        self.view = view

    async def save_user_data(self, update: Update):
        """Обрабатывает команду /start"""
        await self.user_service.add_user(update.effective_user.id, update.effective_user.username)
