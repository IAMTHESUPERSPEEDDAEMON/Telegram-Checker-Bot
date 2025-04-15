import os
from dao.database import DatabaseManager
from config.config import SESSIONS_DIR
from telethon import TelegramClient
from telethon.sessions import StringSession
from utils.logger import Logger

logger = Logger()


class SessionModel:
    def __init__(self):
        self.db = DatabaseManager()

    async def delete_session(self, session_id):
        """Удаляет сессию из бд"""
        query = """
                DELETE FROM telegram_sessions
                WHERE id = %s
                """
        params = (session_id,)

        try:
            self.db.execute_query(query, params)
            logger.info(f"Session {session_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    async def update_session(self, session_id, phone=None, api_id=None, api_hash=None, proxy_id=None):
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

        query = f"""
                    UPDATE telegram_sessions 
                    SET {', '.join(fields)}
                    WHERE id = %s
                    """
        params.append(session_id)
        try:
            self.db.execute_query(query, params)
            logger.info(f"Session {session_id} updated")
            return True
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False

    async def add_session_to_db(self, session_data_list):
        """Добавляет новую сессию в базу данных"""
        phone = session_data_list[0]
        api_id = session_data_list[1]
        api_hash = session_data_list[2]
        string_session = session_data_list[3]
        # Записываем информацию в базу данных
        query = """
        INSERT INTO telegram_sessions 
        (phone, api_id, api_hash, session_file) 
        VALUES (%s, %s, %s, %s)
        """
        params = (phone, api_id, api_hash, string_session)

        result = self.db.execute_query(query, params)
        logger.info(f'Успех! id Добавленной сессии для телефона {phone}: {result}')
        return result

    @staticmethod
    async def create_session(phone, api_id, api_hash, code_callback=None, password_callback=None, proxy=None):
        session_file = f"session_{phone}"
        session_path = os.path.join(SESSIONS_DIR, session_file)

        # Проверка и создание директории для сессий, если она не существует
        if not os.path.exists(SESSIONS_DIR):
            os.makedirs(SESSIONS_DIR)
        # Проверяем существование файла сессии
        if os.path.exists(f"{SESSIONS_DIR}/{session_file}.session"):
            logger.info(f"Сессия для {phone} уже есть. Пересоздаю...")
            # Удаляем старую сессию
            os.remove(f'{session_path}.session')
        try:
            # Создаем клиента с указанием system_version и device_model
            client = TelegramClient(
                session_path,
                api_id,
                api_hash,
                proxy=proxy if proxy else None,
                system_version="4.16.30-vxCUSTOM",
                device_model="Desktop",
                lang_code="en"
            )

            # Запускаем клиент для создания файла сессии
            await client.connect()

            # Проверяем авторизацию
            if not await client.is_user_authorized():
                logger.error(f"Необходима авторизация для аккаунта {phone}")
                try:
                    sent_code = await client.send_code_request(phone)

                    # запрашиваем код
                    code = await code_callback(phone, sent_code.phone_code_hash)

                    try:
                        await client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
                    except Exception as e:
                        if "Two-steps verification is enabled" in str(e):
                            password = input("Введите пароль двухфакторной аутентификации: ")
                            await client.sign_in(password=password)
                        else:
                            raise e
                except Exception as e:
                    logger.error(f"Ошибка при авторизации: {e}")
                    return None

            # Получаем строковое представление сессии
            string_session = StringSession.save(client.session)
            # Закрываем клиент
            await client.disconnect()
            #Удаляю файл
            os.remove(f'{session_path}.session')

            return [phone, api_id, api_hash, string_session]
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}")
            raise e

    async def get_session_by_id(self, session_id):
        """Получает сессию по id"""
        query = """
        SELECT s.*, p.type as proxy_type,
               p.host, p.port, p.username, p.password
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.id = %s
        """
        try:
            session_data = self.db.execute_query(query, (session_id,))
            return session_data[0] if session_data else None
        except Exception as e:
            logger.error(f"Ошибка получения сессии по id {session_id}: {e}")
            raise

    async def get_session_by_phone(self, phone):
        """Получает сессию по номеру телефона"""
        query = """
        SELECT s.*, p.type as proxy_type,
               p.host, p.port, p.username, p.password
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        WHERE s.phone = %s
        """

        try:
            session = self.db.execute_query(query, (phone,))
            return session[0] if session else None
        except Exception as e:
            logger.error(f"Ошибка получения сессии по номеру телефона {phone}: {e}")
            raise

    def get_available_sessions(self, limit=10):
        """Получает доступные активные сессии"""
        query = """
        SELECT s.phone, s.api_id, s.api_hash, s.session_file, s.proxy_id
        FROM telegram_sessions s
        WHERE s.is_active = TRUE 
        ORDER BY s.last_used ASC
        LIMIT %s
        """

        try:
            sessions = self.db.execute_query(query, (limit,))
            logger.info(f"Найдено {len(sessions)} активных сессий.")
            return sessions
        except Exception as e:
            logger.error(f"Ошибка при получении активных сессий: {e}")
            raise

    def get_available_sessions_without_proxy(self, limit=10):
        """Получает доступные активные сессии не привязанные к прокси"""
        query = """
        SELECT s.*
        FROM telegram_sessions s
        WHERE s.is_active = TRUE AND s.proxy_id IS NULL
        ORDER BY s.last_used ASC
        LIMIT %s
        """
        try:
            sessions = self.db.execute_query(query, (limit,))
            logger.info(f"Доступные сессии без прокси получены в кол-ве: {len(sessions)}")
            return sessions
        except Exception as e:
            logger.error(f"Ошибка получения доступных активных сессий без прокси: {e}")
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
            logger.info(f"Session {session_id} статус обновлён на {status}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса сессии {session_id} status: {e}")
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
            logger.info(f"Session {session_id} обновлена в таблице telegram_sessions")
        except Exception as e:
            logger.error(f"Ошибка обновления времени последнего использования сессии {session_id}: {e}")
            raise

    def batch_update_sessions_status(self, session_updates):
        """
        Пакетно обновляет статусы нескольких сессий одним запросом

        Args:
            session_updates: Список кортежей (session_id, is_active)
        """
        if not session_updates:
            return

        # Создаем основу запроса
        query = """
        UPDATE telegram_sessions
        SET is_active = CASE id 
        """

        # Добавляем условные выражения для каждой сессии
        id_list = []
        for session_id, is_active in session_updates:
            query += f" WHEN {session_id} THEN {1 if is_active else 0} "
            id_list.append(str(session_id))

        # Завершаем запрос
        query += " END, last_used = CURRENT_TIMESTAMP "
        query += f" WHERE id IN ({','.join(id_list)})"

        try:
            self.db.execute_query(query)
            logger.info(f"Статусы {len(session_updates)} сессий успешно обновлены")
            return len(session_updates)
        except Exception as e:
            logger.error(f"Ошибка пакетного обновления статусов сессий: {e}")
            return None

    def assign_proxies_to_sessions(self, params_list):
        """Назначает прокси для сессий"""
        query = """
        UPDATE telegram_sessions
        SET proxy_id = %s
        WHERE id = %s
        """

        try:
            assigned_count = self.db.execute_batch_query(query, params_list)
            logger.info(f"Колличество прокси успешно назначен: {assigned_count}")
            return assigned_count
        except Exception as e:
            logger.error(f"Ошибка привязки проксей к сессиям: {e}")
            return e

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
            logger.error(f"Ошибка получения сессий: {e}")
            raise

    async def get_sessions_stats(self):
        """Получает статистику по сессиям"""
        try:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN proxy_id IS NOT NULL THEN 1 ELSE 0 END) as with_proxy
            FROM telegram_sessions
            """
            result = self.db.execute_query(query)[0]
            return {
                'total': int(result['total']),
                'active': int(result['active']),
                'inactive': int(result['total']) - int(result['active']),
                'with_proxy': int(result['with_proxy']),
                'without_proxy': int(result['total']) - int(result['with_proxy'])
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики по сессиям: {e}")
            return None
