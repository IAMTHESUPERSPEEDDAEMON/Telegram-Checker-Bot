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
        proxy_id = self.proxy_model.add_proxy(proxy_type, host, port, username, password)
        if proxy_id is not None:
            return {'status': 'success', 'message': f'Прокси {host}:{port} успешно добавлен.', 'proxy_id': proxy_id}
        else:
            return {'status': 'error', 'message': f'Прокси {host}:{port} не удалось добавить.'}

    def delete_proxy(self, proxy_id):
        """Удаляет прокси из базы данных"""
        if self.proxy_model.get_proxy_by_id(proxy_id) is not None:
            result = self.proxy_model.delete_proxy(proxy_id)
            if result:
                return {'status': 'success', 'message': f'Прокси с ID {proxy_id} успешно удален.'}
            else:
                return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не удалось удалить.'}
        else:
            return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не существует.'}

    def update_proxy(self, proxy_id, new_host=None, new_port=None, new_username=None, new_password=None):
        """Обновляет данные прокси в базе данных"""
        result = self.proxy_model.update_proxy(proxy_id, new_host, new_port, new_username, new_password)
        if result:
            return {'status': 'success', 'message': f'Прокси с ID {proxy_id} успешно обновлен.'}
        else:
            return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не удалось обновить.'}

    async def check_all_proxies(self):
        """Проверяет все прокси в базе данных"""
        proxies = await self.proxy_model.get_all_proxies()

        try:
            for proxy in proxies:
                is_working = await self.proxy_model.check_proxy(proxy)
                self.proxy_model.update_proxy_status(proxy['id'], is_working)
                return {'status': 'success', 'message': f'Проверка проксей завершена'}
        except Exception as e:
            logging.error(f"Ошибка при проверке всех прокси: {e}")
            return {'status': 'error', 'message': "Произошла ошибка при проверке всех проксей"}