import asyncio
import requests

from concurrent.futures import ThreadPoolExecutor
from models.proxy_model import ProxyModel

class ProxyService:
    def __init__(self):
        self.test_url = 'https://google.com'
        self.model = ProxyModel()
        self.executor = ThreadPoolExecutor(max_workers=10)  # Пул потоков для синхронных операций

    async def delete_by_id(self, proxy_id):
        """Удаляет прокси по его ID"""
        is_exists = await self.model.get_proxy_by_id(proxy_id)
        if is_exists is not None:
            delete_proxy = await self.model.delete_proxy_by_id(proxy_id)
            if delete_proxy:
                return {'status': 'success', 'message': f'Прокси с ID {proxy_id} был удалён'}
            else:
                return {'status': 'error', 'message': f'Ошибка  удаления прокси {proxy_id}'}
        else:
            return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не найден'}


    async def add_proxy(self, proxy_type, host, port, username=None, password=None):
        """Добавляет прокси в базу данных"""
        proxy_id = await self.model.add_proxy(proxy_type, host, port, username, password)
        if proxy_id is not None and isinstance(proxy_id, int) and proxy_id > 0:
            return {'status': 'success', 'message': f'Прокси {proxy_id} был добавлен'}
        else:
            return {'status': 'error', 'message': f'Ошибка добавления прокси {proxy_id}'}


    async def update_proxy(self, proxy_id, new_data):
        """Обновляет данные прокси в базе данных"""
        is_exists = await self.model.get_proxy_by_id(proxy_id)
        if is_exists is not None:
            login_password, host_port = new_data.split("@")
            username, password = login_password.split(":")
            host, port = host_port.split(":")

            if await self.model.update_proxy(proxy_id, proxy_type=None, host=host, port=port, username=username, password=password):
                return {'status': 'success', 'message': f'Прокси с ID {proxy_id} был обновлен'}
            else:
                return {'status': 'error', 'message': f'Ошибка обновления прокси {proxy_id}'}
        else:
            return {'status': 'error', 'message': f'Прокси с ID {proxy_id} не найден'}


    async def check_all_proxies(self, batch_size=10):
        """Проверяет работоспособность всех прокси параллельно"""
        # Получаем все прокси из базы
        proxies = await self.model.get_all_proxies()

        if proxies is None:
            return {'status': 'error', 'message': 'Не найдено прокси для проверки'}

        results = {'working': 0, 'failed': 0, 'total': len(proxies)}
        batch_update_data = []

        # Разбиваем проверку на батчи для снижения нагрузки
        for i in range(0, len(proxies), batch_size):
            batch = proxies[i:i + batch_size]

            # Создаем задачи для параллельной проверки прокси
            tasks = []
            for proxy in batch:
                task = self._test_proxy_connection(
                    proxy_type=proxy['type'],
                    host=proxy['host'],
                    port=proxy['port'],
                    username=proxy['username'],
                    password=proxy['password']
                )
                tasks.append(task)

            # Выполняем проверки параллельно
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Обрабатываем результаты
            for j, result in enumerate(batch_results):
                proxy_id = batch[j]['id']

                if isinstance(result, Exception):
                    results["failed"] += 1
                    batch_update_data.append((False, proxy_id))
                else:
                    if result:
                        results["working"] += 1
                        batch_update_data.append((True, proxy_id))
                    else:
                        results["failed"] += 1
                        batch_update_data.append((False, proxy_id))

            # Обновляем статусы партии прокси в базе (пакетно)
            if batch_update_data:
                await self.model.bulk_update_proxy_statuses(batch_update_data)
                batch_update_data = []

        return {'status': 'success', 'message': f"Проверка прокси завершена.\nВсего проверенно: {results['total']},\nрабочих: {results['working']},\nне рабочих: {results['failed']}"}


    async def _test_proxy_connection(self, proxy_type, host, port, username, password):
        """Проверяет соединение с прокси через requests"""
        if proxy_type == 'http' or proxy_type == 'https':
            proxy_url = f"http://{username}:{password}@{host}:{port}"
        elif proxy_type == 'socks5':
            proxy_url = f"socks5://{username}:{password}@{host}:{port}"
        else:
            return False

        # Вызов синхронной функции в асинхронном контексте через run_in_executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self._sync_test_proxy_connection, proxy_url)
        return result

    def _sync_test_proxy_connection(self, proxy_url):
        """Синхронно проверяет соединение с прокси через requests"""
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
            'socks5': proxy_url
        }

        try:
            print(f"Connecting to proxy {proxy_url}...")  # Логирование перед запросом
            response = requests.get(self.test_url, proxies=proxies, timeout=10)
            print(f"Response status code: {response.status_code}")  # Логируем статус код
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"Ошибка при подключении к прокси {proxy_url}: {e}")
            return False


    async def get_proxies_stats(self):
        """Получает статистику по прокси"""
        stats = await self.model.get_proxies_stats()
        if stats is not None:
            return {'status': 'success', 'message': stats}
        else:
            return {'status': 'error', 'message': "Нет данных для статистики."}
