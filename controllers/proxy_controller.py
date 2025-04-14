from telegram import Update
from telegram.ext import ContextTypes

from services.proxy_service import ProxyService
from views.telegram_view import TelegramView
from utils.admin_checker import is_admin

class ProxyController:
    def __init__(self):
        self.proxy_service = ProxyService()
        self.view = TelegramView()

    async def delete_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет прокси из базы данных"""
        if not await is_admin(update):
            return

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 1:
            await self.view.send_message(update, "Не указан ID прокси для удаления.")
            return

        proxy_id = int(context.args[0])
        await self.view.send_result_message(update, result=await self.proxy_service.delete_by_id(proxy_id))


    async def add_proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавляет новый прокси в базу данных"""
        if not await is_admin(update):
            return

        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                "Использование: /add_proxy <тип> <хост> <порт> [имя пользователя] [пароль]"
            )
            return

        proxy_type = context.args[0]
        host = context.args[1]
        port = int(context.args[2])
        username = context.args[3] if len(context.args) > 3 else None
        password = context.args[4] if len(context.args) > 4 else None

        await self.view.send_result_message(update, await self.proxy_service.add_proxy(proxy_type, host, port, username, password))


    async def update_proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные прокси."""
        if not await is_admin(update):
            return

        if not context.args or len(context.args) < 4:
            await self.view.send_message(
                update,
                "Использование: /update_proxy <proxy_id> <тип> <хост> <порт> [имя пользователя] [пароль]"
            )
            return

        proxy_id = int(context.args[0])
        await self.view.send_result_message(update, await self.proxy_service.update_proxy(proxy_id, context.args))


    async def check_proxies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /check_proxies - проверяет работоспособность прокси"""
        # Проверяем, является ли пользователь администратором
        if not await is_admin(update):
            return

        await self.view.send_message(update, "Начинаем проверку прокси...")
        await self.view.send_result_message(update, await self.proxy_service.check_all_proxies())

    async def get_proxies_stats(self):
        """Получет стату по прокси"""
        return await self.proxy_service.get_proxies_stats()