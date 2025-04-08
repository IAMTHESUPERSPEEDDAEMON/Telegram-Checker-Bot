import os
import logging
from dao.database import DatabaseManager
from config.config import SESSIONS_DIR


class SessionModel:
    def __init__(self):
        self.db = DatabaseManager()

    def delete_session(self, session_id):
        """Удаляет сессию из бд"""
        query = """
                DELETE FROM telegram_sessions
                WHERE id = %s
                """
        params = (session_id,)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Session {session_id} deleted")
            return True
        except Exception as e:
            logging.error(f"Error deleting session {session_id}: {e}")
            return False

    def update_session(self, session_id, phone=None, api_id=None, api_hash=None, proxy_id=None):
        """Обновляет данные сессии в базе данных"""
        fields = []
        params = []

        if phone is not None:
            fields.append("phone = %s")
            params.append(phone)
        if api_id is not None:
            fields.append("api_id = %s")
            params.append(api_id)
        if api_hash is not None:
            fields.append("api_hash = %s")
            params.append(api_hash)
        if proxy_id is not None:
            fields.append("proxy_id = %s")
            params.append(proxy_id)

        if not fields:
            logging.warning(f"No fields to update for session {session_id}")
            return False  # або True, якщо ти хочеш просто проігнорувати

        query = f"""
                    UPDATE telegram_sessions 
                    SET {', '.join(fields)}
                    WHERE id = %s
                    """
        params.append(session_id)
        try:
            self.db.execute_query(query, params)
            logging.info(f"Session {session_id} updated")
            return True
        except Exception as e:
            logging.error(f"Error updating session {session_id}: {e}")
            return False

    def add_session(self, phone, api_id, api_hash, proxy_id=None):
        """Добавляет новую сессию в базу данных"""
        session_file = f"session_{phone}"
        session_path = os.path.join(SESSIONS_DIR, session_file)

        query = """
        INSERT INTO telegram_sessions 
        (phone, api_id, api_hash, session_file, proxy_id) 
        VALUES (%s, %s, %s, %s, %s)
        """
        params = (phone, api_id, api_hash, session_path, proxy_id)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Added new session for phone {phone}")
            # Получение последнего вставленного id
            last_inserted_id_query = "SELECT LAST_INSERT_ID()"
            return self.db.execute_scalar(last_inserted_id_query)
        except Exception as e:
            logging.error(f"Error adding session for phone {phone}: {e}")

    def get_session_by_id(self, session_id):
        """Получает сессию по id"""
        query = """
        SELECT s.*, p.type as proxy_type,
               p.host, p.port, p.username as proxy_username, p.password as proxy_password
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.id = %s
        """
        try:
            session_data = self.db.execute_query(query, (session_id,))
            return session_data[0] if session_data else None
        except Exception as e:
            logging.error(f"Ошибка получения сессии по id {session_id}: {e}")
            raise

    def get_session_by_phone(self, phone):
        """Получает сессию по номеру телефона"""
        query = """
        SELECT s.*, p.type as proxy_type,
               p.host, p.port, p.username as proxy_username, p.password as proxy_password
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.phone = %s
        """

        try:
            sessions = self.db.execute_query(query, (phone,))
            return sessions[0] if sessions else None
        except Exception as e:
            logging.error(f"Ошибка получения сессии по номеру телефона {phone}: {e}")
            raise

    def get_available_sessions_with_proxy(self, limit=10):
        """Получает доступные активные сессии с привязанными прокси"""
        query = """
        SELECT s.phone, s.api_id, s.api_hash, s.session_file, s.proxy_id, p.type as proxy_type,
               p.host, p.port, p.username as proxy_username, p.password as proxy_password
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.is_active = TRUE AND (p.is_active IS NULL OR p.is_active = TRUE)
        ORDER BY s.last_used ASC
        LIMIT %s
        """

        try:
            sessions = self.db.execute_query(query, (limit,))
            logging.info(f"Получено {len(sessions)} сессий с привязанными прокси")
            return sessions
        except Exception as e:
            logging.error(f"Ошибка при получении доступных сессий с привязанными прокси: {e}")
            raise

    def get_available_sessions_without_proxy(self, limit=10):
        """Получает доступные активные сессии не привязанные к прокси"""
        query = """
        SELECT s.phone, s.api_id, s.api_hash, s.session_file
        FROM telegram_sessions s
        WHERE s.is_active = TRUE AND s.proxy_id IS NULL
        ORDER BY s.last_used ASC
        LIMIT %s
        """
        try:
            sessions = self.db.execute_query(query, (limit,))
            logging.info(f"Доступные сессии без прокси получены в кол-ве: {len(sessions)}")
            return sessions
        except Exception as e:
            logging.error(f"Ошибка получения доступных активных сессий без прокси: {e}")
            raise

    def update_session_status(self, session_id, is_active):
        """Обновляет статус сессии"""
        query = """
        UPDATE telegram_sessions
        SET is_active = %s, last_used = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = (is_active, session_id)

        try:
            self.db.execute_query(query, params)
            status = "активна" if is_active else "неактивна"
            logging.info(f"Session {session_id} статус обновлён на {status}")
        except Exception as e:
            logging.error(f"Ошибка обновления статуса сессии {session_id} status: {e}")
            raise

    def update_last_used(self, session_id):
        """Обновляет время последнего использования сессии"""
        query = """
        UPDATE telegram_sessions
        SET last_used = CURRENT_TIMESTAMP
        WHERE id = %s
        """

        try:
            self.db.execute_query(query, (session_id,))
            logging.info(f"Session {session_id} обновлена в таблице telegram_sessions")
        except Exception as e:
            logging.error(f"Ошибка обновления времени последнего использования сессии {session_id}: {e}")
            raise

    def assign_proxy_to_session(self, session_id, proxy_id):
        """Назначает прокси для сессии"""
        query = """
        UPDATE telegram_sessions
        SET proxy_id = %s
        WHERE id = %s
        """
        params = (proxy_id, session_id)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Привязана прокси {proxy_id} к сессии {session_id}")
        except Exception as e:
            logging.error(f"Ошибка привязки прокси к сессии {session_id}: {e}")
            raise

    def get_all_sessions(self):
        """Возвращает все сессии"""
        query = """
        SELECT s.*, p.type as proxy_type, p.host, p.port, p.username as proxy_username, 
               p.password as proxy_password 
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        """
        try:
            result = self.db.execute_query(query)
            return result
        except Exception as e:
            logging.error(f"Ошибка получения сессий: {e}")
            raise