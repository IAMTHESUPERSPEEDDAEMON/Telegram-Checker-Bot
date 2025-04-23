from telegram import Update
from telegram.ext import ContextTypes


class MessageHandlerController:
    def __init__(self, state_manager, proxy_controller, session_controller):
        self.state_manager          = state_manager
        self.proxy_controller       = proxy_controller
        self.session_controller     = session_controller

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = self.state_manager.get_state(user_id)

        if state == "AWAITING_PROXY_INPUT":
            await self.proxy_controller.handle_proxy_input(update, context)
            self.state_manager.clear_state(user_id)
        elif state == "AWAITING_DELETE_PROXY_INPUT":
            await self.proxy_controller.handle_proxy_delete_input(update, context)
            self.state_manager.clear_state(user_id)
        elif state == "AWAITING_PROXY_UPDATE_INPUT":
            await self.proxy_controller.handle_proxy_update_input(update, context)
            self.state_manager.clear_state(user_id)
        elif state == "AWAITING_SESSION_INPUT":
            await self.session_controller.handle_session_input(update, context)
        elif state == "AWAITING_CODE_INPUT_FOR_SESSION":
            await self.session_controller.handle_code_input(update, context)
        elif state == "AWAITING_2FA_INPUT_FOR_SESSION":
            await self.session_controller.handle_2fa_input(update, context)
        elif state == "AWAITING_DELETE_SESSION_INPUT":
            await self.session_controller.handle_delete_session_input(update, context)
            self.state_manager.clear_state(user_id)
