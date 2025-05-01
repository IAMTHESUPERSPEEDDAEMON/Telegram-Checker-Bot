import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from config.config import MAX_SESSIONS_PER_USER
from models.session_model import SessionModel
from models.proxy_model import ProxyModel
from utils.logger import Logger

logger = Logger()
class SessionService:
    def __init__(self):
        self.session_model = SessionModel()
        self.proxy_model = ProxyModel()

    async def delete_session_by_id(self, session_id):
        """Удаляет сессию из базы данных"""
        find_session = await self.session_model.get_session_by_id(session_id)
        if find_session is not None:
            deleted_session = await self.session_model.delete_session(session_id)
            if deleted_session:
                return {'status': 'success', 'message': f'Сессия {session_id} успешно удалена.'}
            else:
                return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}
        else:
            return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}


    async def add_session(self, phone, api_id, api_hash, code_callback=None, password_callback=None):
        """Создаёт новую сессию и добавляет её в бд"""
        duplicate_session = await self.session_model.get_session_by_phone(phone)
        if duplicate_session is not None:
            return {'status': 'error', 'message': f'Сессия для телефона {phone} уже существует.'}
        else:
            session_data = await self.session_model.create_session(
                phone, api_id, api_hash,
                code_callback=code_callback,
                password_callback=password_callback
            )

            session_id = await self.session_model.add_session_to_db(session_data)

            if session_id is not None and isinstance(session_id, int) and session_id > 0:
                return {'status': 'success', 'message': f'Сессия {phone} успешно добавлена. ID: {session_id}.'}
            else:
                return {'status': 'error',
                        'message': f'Ошибка добавления сессии для телефона {phone}.\n{session_id}'}


    async def update_session(self, session_id, phone, api_id, api_hash):
        """Обновляет детали сессии"""
        is_exists = await self.session_model.get_session_by_id(session_id)
        if is_exists is None:
            return {'status': 'error', 'message': f'Сессия {session_id} не была найдена'}
        else:
            updated_session = await self.session_model.update_session(session_id, phone, api_id, api_hash, None)

            if updated_session:
                return {'status': 'success', 'message': f'Сессия {session_id} успешно обновлена.'}
            else:
                return {'status': 'error', 'message': f'Ошибка при обновлении сессии {session_id}.'}


    async def check_session(self, session_id):
        """Проверяет работоспособность одной сессии"""
        # получаем сессию по id
        session = await self.session_model.get_session_by_id(session_id)
        if session:
            result = {
                'id': session['id'],
                'phone': session['phone'],
                'is_working': False,
                'error': None
            }
        else:
            return {'status': 'error', 'message': f'Сессия {session_id} не найдена'}
        # Форматируем прокси для Telethon
        proxy = None
        if session['proxy_id'] and session['proxy_id'] != 0:
            proxy = await self.proxy_model.format_proxy_for_telethon(await self.proxy_model.get_proxy_by_id(session['proxy_id']))

        try:
            # Создаем клиента с использованием StringSession
            string_session = StringSession(session['session_file'])
            client = TelegramClient(
                string_session,
                session['api_id'],
                session['api_hash'],
                proxy=proxy,
                connection_retries=2,
                timeout=20  # seconds
            )
            # Подключаемся
            await client.connect()
            # Проверяем авторизацию
            if await client.is_user_authorized():
                result['is_working'] = True
                # Обновляем статус сессии
                await self.session_model.update_session_status(session['id'], True)
            else:
                result['error'] = "Сессия не авторизована"
                # Обновляем статус сессии
                await self.session_model.update_session_status(session['id'], False)

            # Отключаемся
            await client.disconnect()

        except Exception as e:
            result['error'] = str(e)

            # Обновляем статус сессии
            await self.session_model.update_session_status(session['id'], False)

        return result

    async def check_all_sessions(self):
        """Проверяет работоспособность всех сессий"""
        try:
            # получаем все сессии
            sessions = await self.session_model.get_all_sessions()

            # Создаем задачи для проверки каждой сессии
            tasks = [self.check_session(session['id']) for session in sessions]

            # Запускаем все задачи параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Обрабатываем результаты
            processed_results = []
            session_updates = []  # Список обновлений для пакетной записи в БД

            for i, result in enumerate(results):
                session_id = sessions[i]['id']
                phone = sessions[i]['phone']

                if isinstance(result, Exception):
                    # Обрабатываем исключение
                    is_working = False
                    error_msg = str(result)
                    processed_results.append({
                        'id': session_id,
                        'phone': phone,
                        'is_working': is_working,
                        'error': error_msg
                    })
                else:
                    # Успешная проверка
                    is_working = True  # По умолчанию считаем работающей
                    if isinstance(result, dict) and 'is_working' in result:
                        is_working = result['is_working']
                    processed_results.append(result)

                # Добавляем в список для пакетного обновления
                session_updates.append((session_id, is_working))

            # Выполняем одно пакетное обновление вместо множества отдельных запросов
            if session_updates:
                await self.session_model.batch_update_sessions_status(session_updates)
            updated_session_info = await self.session_model.get_available_sessions(limit=1000)
            non_active = int(len(processed_results)) - int(len(updated_session_info))

            return {'status': 'success',
                    'message': f'Проверенно {int(len(processed_results))} сессий, активных = {int(len(updated_session_info))}, не активных = {non_active}'}

        except Exception as e:
            logger.error(f"Ошибка при проверке сессий: {e}")
            return {'status': 'error', 'message': f"Ошибка при проверке сессий: {e}"}

    async def assign_proxies_to_sessions(self):
        """Назначает прокси для сессий без прокси"""
        # Получаем сессии без прокси
        sessions_without_proxy = await self.session_model.get_available_sessions_without_proxy()

        if not sessions_without_proxy:
            return {'status': 'error', 'message': f'Все сессии уже имеют прокси'}

        # Получаем доступные прокси
        available_proxies = await self.proxy_model.get_available_proxies()

        if not available_proxies:
            return {'status': 'error', 'message': f'Нет доступных прокси для назначения.'}

        params_list = []
        for i, session in enumerate(sessions_without_proxy):
            proxy = available_proxies[i % len(available_proxies)]  # Назначаем прокси по кругу
            params_list.append((proxy['id'], session.get('id')))  # (proxy_id, session_id)

        assigned_count = await self.session_model.assign_proxies_to_sessions(params_list)
        if isinstance(assigned_count, int) and assigned_count > 0:
            return {'status': 'success', 'message': f'ВСе свободные прокси привязаны, кол-во обработанных строк: {assigned_count}.'}
        else:
            return {'status': 'error', 'message': f'Ошибка при назначении прокси: {assigned_count}'}

    async def get_sessions_stats(self):
        """Получаем статистику по сессиям"""
        stats = await self.session_model.get_sessions_stats()
        if stats is not None:
            return {'status': 'success', 'message': stats}
        else:
            return {'status': 'error', 'message': "Нет данных для статистики."}

    async def get_active_clients(self):
        """Ініціалізує до max_sessions клієнтів Telegram із активних сесій"""
        clients = []
        sessions = await self.session_model.get_available_sessions(MAX_SESSIONS_PER_USER)

        for session in sessions:
            try:
                proxy = None
                if session['proxy_id']:
                    proxy = await self.proxy_model.format_proxy_for_telethon(
                        await self.proxy_model.get_proxy_by_id(session['proxy_id'])
                    )

                string_session = StringSession(session['session_file'])
                client = TelegramClient(
                    string_session,
                    session['api_id'],
                    session['api_hash'],
                    proxy=proxy,
                    connection_retries=2,
                    timeout=20  # seconds
                )

                await client.connect()

                if not await client.is_user_authorized():
                    logger.warning(f"Сессія {session['id']} не авторизована")
                    await client.disconnect()
                    await self.session_model.update_session_status(session['id'], False)
                    continue

                # Можна додати оновлення last_used або is_active при потребі
                clients.append({
                    'client': client,
                    'session_id': session['id'],
                    'phone': session['phone']
                })

            except Exception as e:
                logger.error(f"Помилка при ініціалізації сесії {session['id']}: {e}")
                # Можна оновити статус сесії до неактивного
                await self.session_model.update_session_status(session['id'], False)

        return clients
