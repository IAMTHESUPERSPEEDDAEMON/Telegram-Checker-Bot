import os
import logging
from dao.database import DatabaseManager
from config.config import SESSIONS_DIR


class SessionModel:
    def __init__(self):
        self.db = DatabaseManager()

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
            session_id = self.db.execute_query(query, params)
            logging.info(f"Added new session for phone {phone}")
            return session_id
        except Exception as e:
            logging.error(f"Error adding session for phone {phone}: {e}")

    def get_available_sessions(self, limit=10):
        """Получает доступные активные сессии с привязанными прокси"""
        query = """
        SELECT s.*, p.type as proxy_type, p.host, p.port, p.username as proxy_username, 
               p.password as proxy_password 
        FROM telegram_sessions s
        JOIN proxies p ON s.proxy_id = p.id
        WHERE s.is_active = TRUE AND p.is_active = TRUE
        ORDER BY s.last_used ASC
        LIMIT %s
        """

        try:
            sessions = self.db.execute_query(query, (limit,))
            return sessions
        except Exception as e:
            logging.error(f"Error getting available sessions: {e}")
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
            logging.info(f"Session {session_id} status updated to {status}")
        except Exception as e:
            logging.error(f"Error updating session {session_id} status: {e}")
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
        except Exception as e:
            logging.error(f"Error updating last_used for session {session_id}: {e}")
            raise

    def get_session_by_phone(self, phone):
        """Получает сессию по номеру телефона"""
        query = """
        SELECT s.*, p.type as proxy_type, p.host, p.port, p.username as proxy_username, 
               p.password as proxy_password 
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.phone = %s
        """

        try:
            sessions = self.db.execute_query(query, (phone,))
            return sessions[0] if sessions else None
        except Exception as e:
            logging.error(f"Error getting session for phone {phone}: {e}")
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
            logging.info(f"Assigned proxy {proxy_id} to session {session_id}")
        except Exception as e:
            logging.error(f"Error assigning proxy to session: {e}")
            raise