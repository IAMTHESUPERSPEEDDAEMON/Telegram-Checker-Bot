from dao.database import DatabaseManager
from utils.logger import Logger

logger = Logger()
class ProxyModel:
    def __init__(self):
        self.db = DatabaseManager()

    async def delete_proxy_by_id(self, proxy_id):
        """Удаляет прокси из базы данных"""
        query = """
        DELETE FROM proxies
        WHERE id = %s
        """
        params = (proxy_id,)

        try:
            self.db.execute_query(query, params)
            logger.info(f"Proxy {proxy_id} удалён")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении прокси {proxy_id}: {e}")
            return False


    async def update_proxy(self, proxy_id, proxy_type=None, host=None, port=None, username=None, password=None):
        """Обновляет детали прокси"""
        fields = []
        params = []

        if proxy_type is not None:
            fields.append("proxy_type = %s")
            params.append(proxy_type)
        if host is not None:
            fields.append("host = %s")
            params.append(host)
        if port is not None:
            fields.append("port = %s")
            params.append(port)
        if username is not None:
            fields.append("username = %s")
            params.append(username)
        if password is not None:
            fields.append("password = %s")
            params.append(password)

        query = f"""
                    UPDATE proxys 
                    SET {', '.join(fields)}
                    WHERE id = %s
                    """
        params.append(proxy_id)

        try:
            self.db.execute_query(query, params)
            logger.info(f"Proxy {proxy_id} данные обновлены")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении прокси {proxy_id} детали: {e}")
            return False


    async def add_proxy(self, proxy_type, host, port, username, password):
        """Добавляет новый прокси в базу данных"""
        query = """
        INSERT INTO proxies 
        (type, host, port, username, password) 
        VALUES (%s, %s, %s, %s, %s)
        """
        params = (proxy_type, host, port, username, password)

        try:
            proxy_id = self.db.execute_query(query, params)
            logger.info(f"Added new {proxy_type} proxy {host}:{port}")
            return proxy_id
        except Exception as e:
            logger.error(f"Ошибка добавления прокси {host}:{port}: {e}")
            return None


    async def get_proxy_by_id(self, proxy_id):
        """Получает прокси по его id"""
        query = """
        SELECT * FROM proxies
        WHERE id = %s
        """
        params = (proxy_id,)
        try:
            proxy = self.db.execute_query(query, params)
            return proxy[0]
        except Exception as e:
            logger.error(f"Прокси с id {proxy_id} не найден: {e}")
            return None


    async def get_all_proxies(self):
        """Получает все прокси"""
        query = "SELECT * FROM proxies"
        try:
            proxies = self.db.execute_query(query)
            return proxies
        except Exception as e:
            logger.error(f"Ошибка получения всех прокси: {e}")
            return None


    async def get_available_proxies(self, limit=10):
        """Получает доступные активные прокси в указанном количестве"""
        query = """
        SELECT p.* FROM proxies p
        LEFT JOIN telegram_sessions s ON p.id = s.proxy_id
        WHERE s.id IS NULL AND p.is_active = TRUE
        ORDER BY p.last_checked DESC
        LIMIT %s
        """

        try:
            proxies = self.db.execute_query(query, (limit,))
            logger.info(f"Получено {len(proxies)} доступных прокси")
            return proxies
        except Exception as e:
            logger.error(f"Ошибка получения доступных прокси: {e}")
            return None


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
            logger.info(f"Статус прокси {proxy_id} обновлен на {status}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса прокси {proxy_id} status: {e}")
            return False


    async def bulk_update_proxy_statuses(self, proxy_statuses):
        """Обновляет статусы для нескольких прокси одним запросом"""
        if not proxy_statuses:
            return True

        query = """
        UPDATE proxies
        SET is_active = %s, last_checked = CURRENT_TIMESTAMP
        WHERE id = %s
        """

        try:
            affected_rows = self.db.execute_batch_query(query, proxy_statuses)
            return affected_rows > 0
        except Exception as e:
            return False


    async def format_proxy_for_telethon(self, proxy):
        """Форматирует прокси для использования в Telethon"""
        proxy_dict = None
        if proxy['type'] == 'http':
            proxy_dict = {
                'proxy_type': 'HTTP',
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }
        elif proxy['type'] == 'socks5':
            proxy_dict = {
                'proxy_type': 'SOCKS5',
                'addr': proxy['host'],
                'port': proxy['port'],
                'username': proxy['username'],
                'password': proxy['password']
            }
        return proxy_dict

    async def get_proxies_stats(self):
        """Получает статистику по прокси-серверам"""
        try:
            query = """
               SELECT
                   COUNT(*) as total,
                   SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN is_active = FALSE THEN 1 ELSE 0 END) as inactive
               FROM proxies
               """
            result = self.db.execute_query(query)[0]
            return {
                'total': result['total'],
                'active': result['active'],
                'inactive': result['inactive']
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики по прокси-серверам: {e}")
            return None