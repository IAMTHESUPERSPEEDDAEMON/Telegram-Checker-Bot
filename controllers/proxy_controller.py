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

    async def update_proxy_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.add_proxy_menu(update)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_PROXY_UPDATE_INPUT")

    async def check_proxies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.proxy_stats_menu(update)
        await self.view.show_result_message(update, await self.proxy_service.check_all_proxies())

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

    async def handle_proxy_update_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()

        proxy_id, credentials = message_text.split(maxsplit=1)

        result = await self.proxy_service.update_proxy(proxy_id, credentials)
        await self.view.show_result_message(update, result)
