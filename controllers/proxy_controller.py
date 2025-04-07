import logging
from models.proxy_model import ProxyModel

class ProxyController:
    def __init__(self):
        self.proxy_model = ProxyModel()

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
            result = self.proxy_model.db.execute_query(query)[0]
            return {
                'total': result['total'],
                'active': result['active'],
                'inactive': result['inactive']
            }
        except Exception as e:
            logging.error(f"Ошибка при получении статистики по прокси-серверам: {e}")
            raise

    def add_proxy(self, proxy_type, host, port, username=None, password=None):
        """Добавляет новый прокси в базу данных"""
        try:
            proxy_id = self.proxy_model.add_proxy(proxy_type, host, port, username, password)
            logging.info(f"Прокси {host}:{port} успешно добавлен с ID: {proxy_id}")
            return {'status': 'success', 'message': f'Прокси {host}:{port} успешно добавлен.', 'proxy_id': proxy_id}
        except Exception as e:
            logging.error(f"Ошибка при добавлении прокси {host}:{port}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_available_proxies(self, limit=10):
        """Получает доступные активные прокси"""
        try:
            proxies = self.proxy_model.get_available_proxies(limit)
            logging.info(f"Получено {len(proxies)} доступных прокси")
            return {'status': 'success', 'proxies': proxies}
        except Exception as e:
            logging.error(f"Ошибка при получении доступных прокси: {e}")
            return {'status': 'error', 'message': str(e)}

    def update_proxy_status(self, proxy_id, is_active):
        """Обновляет статус прокси"""
        try:
            self.proxy_model.update_proxy_status(proxy_id, is_active)
            status = "активен" if is_active else "неактивен"
            logging.info(f"Статус прокси {proxy_id} обновлен на {status}")
            return {'status': 'success', 'message': f'Статус прокси {proxy_id} обновлен на {status}'}
        except Exception as e:
            logging.error(f"Ошибка при обновлении статуса прокси {proxy_id}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_unused_proxies(self):
        """Получает прокси, которые еще не привязаны к сессиям"""
        try:
            proxies = self.proxy_model.get_unused_proxies()
            logging.info(f"Получено {len(proxies)} непривязанных прокси")
            return {'status': 'success', 'proxies': proxies}
        except Exception as e:
            logging.error(f"Ошибка при получении непривязанных прокси: {e}")
            return {'status': 'error', 'message': str(e)}

    async def check_proxy(self, proxy_id):
        """Проверяет работоспособность конкретного прокси"""
        try:
            # Получаем данные прокси по ID
            query = "SELECT * FROM proxies WHERE id = %s"
            proxy = self.proxy_model.db.execute_query(query, (proxy_id,))
            if not proxy:
                logging.error(f"Прокси с ID {proxy_id} не найден")
                return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не найден'}

            # Проверяем прокси
            is_working = await self.proxy_model.check_proxy(proxy[0])
            if is_working:
                logging.info(f"Прокси {proxy_id} работает корректно")
                return {'status': 'success', 'message': f'Прокси {proxy_id} работает корректно'}
            else:
                logging.warning(f"Прокси {proxy_id} не работает")
                return {'status': 'error', 'message': f'Прокси {proxy_id} не работает'}

        except Exception as e:
            logging.error(f"Ошибка при проверке прокси {proxy_id}: {e}")
            return {'status': 'error', 'message': str(e)}

    async def check_all_proxies(self):
        """Проверяет все прокси в базе данных"""
        try:
            await self.proxy_model.check_all_proxies()
            logging.info("Все прокси проверены")
            return {'status': 'success', 'message': 'Все прокси проверены'}
        except Exception as e:
            logging.error(f"Ошибка при проверке всех прокси: {e}")
            return {'status': 'error', 'message': str(e)}