from config.config import ADMIN_IDS
from views.telegram_view import TelegramView as view


async def is_admin(update, context):
    """Проверяет, является ли пользователь администратором"""
    if update.effective_user.id in ADMIN_IDS:
        await view.send_access_denied(update, context)
        return False


class AdminChecker:
    pass