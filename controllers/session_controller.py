import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from services.session_service import SessionService
from utils.logger import Logger

logger = Logger()


class SessionController:
    def __init__(self, view, state_manager):
        self.session_service = SessionService()
        self.view = view
        self.state_manager = state_manager
        self._session_data = {}

    async def add_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.add_session_menu(update, context)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_SESSION_INPUT")

    async def delete_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.delete_session_menu(update, context)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_DELETE_SESSION_INPUT")

    async def update_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.view.update_session_menu(update, context)
        self.state_manager.set_state(update.effective_user.id, "AWAITING_SESSION_UPDATE_INPUT")

    async def check_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = await self.session_service.check_all_sessions()
        # Удаляем меню, которое было до этого
        last_menu_id = context.user_data.get("last_menu_message_id")
        if last_menu_id:
            try:
                await update.effective_chat.delete_message(last_menu_id)
            except Exception as e:
                print(f"Ошибка при удалении старого меню: {e}")
        await self.view.show_result_message(update, result)

    async def assign_proxies_to_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Присваивает прокси к сессиям."""
        # Удаляем меню, которое было до этого
        last_menu_id = context.user_data.get("last_menu_message_id")
        if last_menu_id:
            try:
                await update.effective_chat.delete_message(last_menu_id)
            except Exception as e:
                print(f"Ошибка при удалении старого меню: {e}")
        result = await self.session_service.assign_proxies_to_sessions()
        await self.view.show_result_message(update, result)

    async def get_sessions_stats(self):
        """Получить статистику по сессиям"""
        return await self.session_service.get_sessions_stats()

    async def handle_session_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        parts = message_text.split()
        phone, api_id, api_hash = parts[:3]
        if user_id not in self._session_data:
            self._session_data[user_id] = {
                'phone': phone,
                'api_id': api_id,
                'api_hash': api_hash,
            }
        asyncio.create_task(self._start_session_flow(update, context, user_id))
        self.state_manager.set_state(user_id, "AWAITING_CODE_INPUT_FOR_SESSION")
        # Удаляем меню, которое было до этого
        last_menu_id = context.user_data.get("last_menu_message_id")
        if last_menu_id:
            try:
                await update.effective_chat.delete_message(last_menu_id)
            except Exception as e:
                print(f"Ошибка при удалении старого меню: {e}")
        await self.view.show_get_session_code_menu(update, phone)

    async def handle_code_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        code = update.message.text.strip()

        if user_id in self._session_data and "waiting_code" in self._session_data[user_id]:
            self._session_data[user_id]["waiting_code"].set_result(code)

    async def handle_2fa_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        password = update.message.text.strip()

        if user_id in self._session_data and "waiting_password" in self._session_data[user_id]:
            self._session_data[user_id]["waiting_password"].set_result(password)

    async def _start_session_flow(self, update, context, user_id):
        data = self._session_data[user_id]

        async def code_callback(phone_number=None, phone_code_hash=None):
            future = asyncio.Future()
            self._session_data[user_id]["waiting_code"] = future
            return await future

        async def password_callback(phone):
            future = asyncio.Future()
            self._session_data[user_id]["waiting_password"] = future
            self.state_manager.set_state(user_id, "AWAITING_2FA_INPUT_FOR_SESSION")
            await self.view.show_get_session_code_menu(update, phone)
            return await future

        try:
            result = await self.session_service.add_session(
                data["phone"], data["api_id"], data["api_hash"],
                code_callback=code_callback,
                password_callback=password_callback
            )
            print(result)
            # Удаляем меню, которое было до этого
            last_menu_id = context.user_data.get("last_menu_message_id")
            if last_menu_id:
                try:
                    await update.effective_chat.delete_message(last_menu_id)
                except Exception as e:
                    print(f"Ошибка при удалении старого меню: {e}")
            await self.view.show_result_message(update, result)
            # очистка состояния диалога
            self.state_manager.clear_state(user_id)
            self._session_data.pop(user_id, None)
        except Exception as e:
            print(f"Ошибка при добавлении сессии: {e}")
            # Удаляем меню, которое было до этого
            last_menu_id = context.user_data.get("last_menu_message_id")
            if last_menu_id:
                try:
                    await update.effective_chat.delete_message(last_menu_id)
                except Exception as e:
                    print(f"Ошибка при удалении старого меню: {e}")
            await self.view.show_result_message(update, result)
            await self.view.show_custom_menu(update,context, str(e))
            self.state_manager.clear_state(user_id)
            self._session_data.pop(user_id, None)

    async def handle_delete_session_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()

        result = await self.session_service.delete_session_by_id(session_id=message_text)
        await self.view.show_result_message(update, result)

    async def handle_session_update_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()
        parts = message_text.split()
        session_id, phone, api_id, api_hash = parts[:4]
        result = await self.session_service.update_session(session_id=session_id, phone=phone, api_id=int(api_id), api_hash=api_hash)
        await self.view.show_result_message(update, result)

