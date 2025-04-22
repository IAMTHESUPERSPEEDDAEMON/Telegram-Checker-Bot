from telegram import Update
from telegram.ext import ContextTypes

from services.proxy_service import ProxyService
from utils.admin_checker import is_admin

class ProxyController:
    def __init__(self, view, state_manager):
        self.proxy_service  = ProxyService()
        self.view           = view
        self.state_manager  = state_manager

    async def delete_proxy_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.delete_proxy_menu(update)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_DELETE_PROXY_INPUT")

    async def add_proxy_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.add_proxy_menu(update)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_PROXY_INPUT")

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

    async def handle_proxy_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()

        proxy_type, credentials = message_text.split(maxsplit=1)
        login_password, host_port = credentials.split("@")
        username, password = login_password.split(":")
        host, port = host_port.split(":")

        result = await self.proxy_service.add_proxy(proxy_type, host, int(port), username, password)
        await self.view.show_result_message(update, result)

    async def handle_proxy_delete_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()

        result = await self.proxy_service.delete_by_id(proxy_id=message_text)
        await self.view.show_result_message(update, result)
