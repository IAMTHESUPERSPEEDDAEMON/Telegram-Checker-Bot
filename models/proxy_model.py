import logging
import socks
from telethon.sessions import StringSession
from telethon import TelegramClient
from dao.database import DatabaseManager


class ProxyModel:
    def __init__(self):
        self.db = DatabaseManager()

    def add_proxy(self, proxy_type, host, port, username=None, password=None):
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
            logging.error(f"Error adding proxy {host}:{port}: {e}")
            raise

    def get_available_proxies(self, limit=10):
        """Получает доступные активные прокси"""
        query = """
        SELECT * FROM proxies
        WHERE is_active = TRUE
        ORDER BY last_checked ASC
        LIMIT %s
        """

        try:
            proxies = self.db.execute_query(query, (limit,))
            return proxies
        except Exception as e:
            logging.error(f"Error getting available proxies: {e}")
            raise

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
            logging.info(f"Proxy {proxy_id} status updated to {status}")
        except Exception as e:
            logging.error(f"Error updating proxy {proxy_id} status: {e}")
            raise

    def get_unused_proxies(self):
        """Получает прокси, которые еще не привязаны к сессиям"""
        query = """
        SELECT p.* FROM proxies p
        LEFT JOIN telegram_sessions s ON p.id = s.proxy_id
        WHERE s.id IS NULL AND p.is_active = TRUE
        """

        try:
            proxies = self.db.execute_query(query)
            return proxies
        except Exception as e:
            logging.error(f"Error getting unused proxies: {e}")
            raise

    def format_proxy_for_telethon(self, proxy):
        """Форматирует прокси для использования в Telethon"""
        proxy_dict = None

        if proxy['type'] == 'http':
            proxy_dict = {
                'proxy_type': 'http',
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }
        elif proxy['type'] in ('socks4', 'socks5'):
            proxy_type = socks.SOCKS4 if proxy['type'] == 'socks4' else socks.SOCKS5
            proxy_dict = {
                'proxy_type': proxy_type,
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }

        return proxy_dict

    async def check_proxy(self, proxy):
        """Проверяет работоспособность прокси"""
        proxy_dict = self.format_proxy_for_telethon(proxy)

        if not proxy_dict:
            logging.error(f"Invalid proxy type: {proxy['type']}")
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
            is_connected = await client.is_connected()
            await client.disconnect()

            if is_connected:
                logging.info(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) is working")
                return True
            else:
                logging.warning(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) connection failed")
                return False

        except Exception as e:
            logging.error(f"Error checking proxy {proxy['id']} ({proxy['host']}:{proxy['port']}): {e}")
            return False

    async def check_all_proxies(self):
        """Проверяет все прокси в базе данных"""
        query = "SELECT * FROM proxies"

        try:
            proxies = self.db.execute_query(query)
            for proxy in proxies:
                is_working = await self.check_proxy(proxy)
                self.update_proxy_status(proxy['id'], is_working)

            logging.info("Completed checking all proxies")
        except Exception as e:
            logging.error(f"Error checking all proxies: {e}")
            raise