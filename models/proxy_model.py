import logging
import socks
from telethon.sessions import StringSession
from telethon import TelegramClient
from dao.database import DatabaseManager


class ProxyModel:
    def __init__(self):
        self.db = DatabaseManager()

    def update_proxy(self, proxy_id, proxy_type=None, host=None, port=None, username=None, password=None):
        """Обновляет детали прокси"""
        query = """
        UPDATE proxies
        SET type = COALESCE(%s, type),
            host = COALESCE(%s, host),
            port = COALESCE(%s, port),
            username = COALESCE(%s, username),
            password = COALESCE(%s, password)
        WHERE id = %s
        """
        params = (proxy_type, host, port, username, password, proxy_id)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Proxy {proxy_id} данные обновлены")
        except Exception as e:
            logging.error(f"Ошибка при обновлении прокси {proxy_id} детали: {e}")
            raise

    def delete_proxy(self, proxy_id):
        """Удаляет прокси из базы данных"""
        query = """
        DELETE FROM proxies
        WHERE id = %s
        """
        params = (proxy_id,)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Proxy {proxy_id} удалён")
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении прокси {proxy_id}: {e}")
            raise

    def add_proxy(self, proxy_type, host, port, username, password):
        """Добавляет новый прокси в базу данных"""
        query = """
        INSERT INTO proxies 
        (type, host, port, username, password) 
        VALUES (%s, %s, %s, %s, %s)
        """
        params = (proxy_type, host, port, username, password)

        try:
            proxy_id = self.db.execute_query(query, params)
            logging.info(f"Added new {proxy_type} proxy {host}:{port}")
            return proxy_id
        except Exception as e:
            logging.error(f"Ошибка добавления прокси {host}:{port}: {e}")
            return None

    def get_proxy_by_id(self, proxy_id):
        """Получает прокси по его id"""
        query = """
        SELECT * FROM proxies
        WHERE id = %s
        """
        params = (proxy_id,)
        try:
            proxy = self.db.execute_query(query, params)
            return proxy
        except Exception as e:
            logging.error(f"Прокси с id {proxy_id} не найден: {e}")
            return None

    def get_all_proxies(self):
        """Получает все прокси"""
        query = "SELECT * FROM proxies"
        try:
            proxies = self.db.execute_query(query)
            return proxies
        except Exception as e:
            logging.error(f"Ошибка получения всех прокси: {e}")
            raise

    def get_available_proxies(self, limit=10):
        """Получает доступные активные прокси в указанном количестве"""
        query = """
        SELECT p.* FROM proxies p
        LEFT JOIN telegram_sessions s ON p.id = s.proxy_id
        WHERE s.id IS NULL AND p.is_active = TRUE
        ORDER BY AGE(p.created_at) DESC LIMIT %s
        """

        try:
            proxies = self.db.execute_query(query, (limit,))
            logging.info(f"Получено {len(proxies)} доступных прокси")
            return proxies
        except Exception as e:
            logging.error(f"Ошибка получения доступных прокси: {e}")
            return []


    def update_proxy_status(self, proxy_id, is_active):
        """Обновляет статус прокси"""
        query = """
        UPDATE proxies
        SET is_active = %s, last_checked = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = (is_active, proxy_id)

        try:
            self.db.execute_query(query, params)
            status = "активен" if is_active else "неактивен"
            logging.info(f"Статус прокси {proxy_id} обновлен на {status}")
            return True
        except Exception as e:
            logging.error(f"Ошибка обновления статуса прокси {proxy_id} status: {e}")
            return False

    async def check_proxy(self, proxy):
        """Проверяет работоспособность прокси"""
        proxy_dict = self.format_proxy_for_telethon(proxy)

        if not proxy_dict:
            logging.error(f"Неверный тип прокси: {proxy['type']}")
            return False

        try:
            # Создаем временный клиент для проверки прокси
            client = TelegramClient(
                StringSession(),
                api_id=123456,  # Фиктивные значения для проверки
                api_hash='abcdef1234567890',
                proxy=proxy_dict
            )

            # Пытаемся подключиться
            await client.connect()
            if client.is_connected():
                is_connected = True
                await client.disconnect()

            if is_connected:
                logging.info(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) работает")
                return True
            else:
                logging.warning(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) ошибка подключения")
                return False

        except Exception as e:
            logging.error(f"Ошибка проверки proxy {proxy['id']} ({proxy['host']}:{proxy['port']}): {e}")
            return False

    def format_proxy_for_telethon(self, proxy):
        """Форматирует прокси для использования в Telethon"""
        proxy_dict = None

        if proxy['type'] == 'http':
            proxy_dict = {
                'proxy_type': proxy['type'],
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }
        elif proxy['type'] == 'socks5':
            proxy_type = socks.SOCKS5
            proxy_dict = {
                'proxy_type': proxy_type,
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }

        return proxy_dict
