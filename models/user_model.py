from dao.database import DatabaseManager
from utils.logger import Logger

logger = Logger()
class UserModel:
    def __init__(self):
        self.db = DatabaseManager()

    async def add_user(self, telegram_id, username=None, is_admin=False):
        """Добавляет юзера в бд"""
        query = """
        INSERT INTO users (telegram_id, username, is_admin) VALUES (%s, %s, %s)
        """
        params = (telegram_id, username, is_admin)

        try:
            user_id = self.db.execute_query(query, params)
            logger.info(f"Юзер {username} добавлен в бд, ID: {telegram_id}")
            return user_id
        except Exception as e:
            logger.error(f"Ошибка добавления юзера в бд: {e}")
            return None


    async def update_user(self, telegram_id, username=None, is_admin=False, paid_status=False, paid_until=None):
        """Обновляет данные юзера"""
        fields = []
        params = []

        if username is not None:
            fields.append("username = %s")
            params.append(username)
        if is_admin:
            fields.append("is_admin = %s")
            params.append(is_admin)
        if paid_status:
            fields.append("paid_status = %s")
            params.append(paid_status)
        if paid_until is not None:
            fields.append("paid_until = CURRENT_TIMESTAMP + INTERVAL '30 DAY'")

        query = f"""
                            UPDATE users 
                            SET {', '.join(fields)}
                            WHERE telegram_id = %s
                            """
        params.append(telegram_id)

        try:
            self.db.execute_query(query, params)
            logger.info(f"Юзер {telegram_id} успешно обновлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении юзера {telegram_id} детали: {e}")
            return False


    async def delete_user(self, telegram_id):
        """Удаляет пользователя из базы данных"""
        query = f"""DELETE FROM users WHERE telegram_id = %s;"""
        params = (telegram_id,)

        try:
            self.db.execute_query(query, params)
            logger.info(f"Юзер {telegram_id} успешно удален")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении юзера {telegram_id} детали: {e}")
            return False


    async def get_user_by_telegram_id(self, telegram_id):
        """Возвращает пользователя по его telegram_id"""
        query = f"""SELECT * FROM users WHERE telegram_id = %s;"""
        params = (telegram_id,)

        try:
            result = self.db.execute_query(query, params)
            logger.info(f"Пытаюсь получить юзера: {telegram_id} из бд")
            return result[0]
        except Exception as e:
            logger.error(f"Ошибка при получении юзера {telegram_id} детали: {e}")
            return None

    async def get_all_users(self):
        """Возвращает всех пользователей"""
        query = f"""SELECT * FROM users;"""
        try:
            result = self.db.execute_query(query)
            logger.info(f"Пользователи успешно получены из бд")
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении всех пользователей детали: {e}")