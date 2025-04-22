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
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Я не понял сообщение. Пожалуйста, выберите действие через меню.")
