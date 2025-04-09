import os
import logging
from dao.database import DatabaseManager
from config.config import SESSIONS_DIR
from telethon import TelegramClient
from telethon.sessions import StringSession


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

    async def add_session(self, phone, api_id, api_hash, proxy=None):
        """Добавляет новую сессию в базу данных и создаёт файл сессии Telegram"""
        session_file = f"session_{phone}"
        session_path = os.path.join(SESSIONS_DIR, session_file)

        # Проверка и создание директории для сессий, если она не существует
        if not os.path.exists(SESSIONS_DIR):
            os.makedirs(SESSIONS_DIR)
        # Проверяем существование файла сессии
        if not os.path.exists(f"{SESSIONS_DIR}/{session_file}.session"):
            logging.info(f"Сессия для {phone} не найдена. Создаем новую...")


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
                logging.error(f"Необходима авторизация для аккаунта {phone}")
                try:
                    sent_code = await client.send_code_request(phone)

                    # запрашиваем код
                    code = input(f"Введите код для номера {phone}: ")

                    try:
                        await client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
                    except Exception as e:
                        if "Two-steps verification is enabled" in str(e):
                            password = input("Введите пароль двухфакторной аутентификации: ")
                            await client.sign_in(password=password)
                            # Используем сохраненный пароль 2FA или запрашиваем новый
                            # password = account.get('twofa')
                            # if not password:
                            #     password = input("Введите пароль двухфакторной аутентификации: ")
                            # await client.sign_in(password=password)
                        else:
                            raise e
                except Exception as e:
                    logging.error(f"Ошибка при авторизации: {e}")
                    return None


            # Создаем строковую сессию на основе данных текущей сессии
            # Важно: нам нужно получить данные из файловой сессии
            # и создать с ними StringSession

            # Получаем данные текущей сессии
            dc_id = client.session.dc_id
            server_address = client.session.server_address
            port = client.session.port
            auth_key = client.session.auth_key

            # Создаем StringSession и настраиваем её с теми же данными
            string_session = StringSession()
            string_session.set_dc(dc_id, server_address, port)
            string_session._auth_key = auth_key  # Используем приватный атрибут, т.к. нет публичного метода

            # Получаем строковое представление сессии
            session_string = string_session.save()

            # Закрываем клиент
            await client.disconnect()

            # Записываем информацию в базу данных
            query = """
            INSERT INTO telegram_sessions 
            (phone, api_id, api_hash, session_file) 
            VALUES (%s, %s, %s, %s)
            """
            params = (phone, api_id, api_hash, session_string)

            self.db.execute_query(query, params)
            logging.info(f"Added new session for phone {phone}")

            # Получение последнего вставленного id
            last_inserted_id_query = f"SELECT id FROM telegram_sessions WHERE phone='{phone}'"
            result = self.db.execute_scalar(last_inserted_id_query)
            logging.log(f'id Добавленной сессии для телефона {phone}: {result}')
            return result

        except Exception as e:
            logging.error(f"Error adding session for phone {phone}: {e}")
            raise e

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