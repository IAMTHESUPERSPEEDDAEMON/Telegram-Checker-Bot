from config.config import ADMIN_IDS
from views.telegram_view import TelegramView


async def is_admin(update):
    """Проверяет, является ли пользователь администратором"""
    if update.effective_user.id not in ADMIN_IDS:
        await TelegramView.send_access_denied(update)
        return False
    else:
        return True


class AdminChecker:
    pass