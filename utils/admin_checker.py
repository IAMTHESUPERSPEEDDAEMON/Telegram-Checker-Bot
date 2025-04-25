from config.config import ADMIN_IDS


async def is_admin(update):
    """Проверяет, является ли пользователь администратором"""
    if update.effective_user.id not in ADMIN_IDS:
        return False
    else:
        return True


class AdminChecker:
    pass