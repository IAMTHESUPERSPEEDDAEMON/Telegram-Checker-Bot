import logging
import asyncio
from telethon.sync import TelegramClient
from models.session_model import SessionModel
from models.proxy_model import ProxyModel


class SessionController:
    def __init__(self):
        self.session_model = SessionModel()
        self.proxy_model = ProxyModel()

    def delete_session(self, session_id):
        """Удаляет сессию из базы данных"""
        find_session = self.session_model.get_session_by_id(session_id)
        if find_session:
            deleted_session = self.session_model.delete_session(session_id)
            if deleted_session:
                return {'status': 'success', 'message': f'Сессия {session_id} успешно удалена.'}
            else:
                return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}
        else:
            return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}

    def update_session(self, session_id, new_params):
        """Обновляет детали сессии"""
        is_exists = self.session_model.get_session_by_id(session_id)
        if is_exists is None:
            return {'status': 'error', 'message': f'Сессия {session_id} не была найдена'}
        else:
            updated_session = self.session_model.update_session(session_id, None, new_params['api_id'], new_params['api_hash'], None)

            if updated_session:
                return {'status': 'success', 'message': f'Сессия {session_id} успешно обновлена.'}
            else:
                return {'status': 'error', 'message': f'Ошибка при обновлении сессии {session_id}.'}

    async def add_session(self, phone, api_id, api_hash):
        """Создаёт новую сессию и добавляет её в бд"""
        duplicate_session = await self.session_model.get_session_by_phone(phone)
        if duplicate_session is not None:
            return {'status': 'error', 'message': f'Сессия для телефона {phone} уже существует.'}
        else:
            session_data = await self.session_model.create_session(phone, api_id, api_hash)
            session_id = await self.session_model.add_session_to_db(session_data)

            if isinstance(session_id, int) and session_id is not None:
                return {'status': 'success', 'message': f'Session {phone} added successfully.'}
            else:
                return {'status': 'error', 'message': f'Error while adding session for phone {phone}.\n{session_id}'}

    async def check_session(self, session_phone):
        """Проверяет работоспособность одной сессии"""
        # получаем сессию по номеру
        session = self.session_model.get_session_by_phone(session_phone)
        if session:
            result = {
                'id': session['id'],
                'phone': session['phone'],
                'is_working': False,
                'error': None
            }
        else:
            return {'status': 'error', 'message': f'Сессия {session_phone} не найдена'}

        # Форматируем прокси для Telethon
        proxy = None
        if 'proxy_id' in session and session['proxy_id']:
            proxy = self.proxy_model.format_proxy_for_telethon(self.proxy_model.get_proxy_by_id(session['proxy_id']))

        try:
            # Создаем клиента
            client = TelegramClient(
                session['session_file'],
                session['api_id'],
                session['api_hash'],
                proxy=proxy
            )

            # Подключаемся
            await client.connect()

            # Проверяем авторизацию
            if await client.is_user_authorized():
                result['is_working'] = True

                # Обновляем статус сессии
                self.session_model.update_session_status(session['id'], True)
            else:
                result['error'] = "Сессия не авторизована"

                # Обновляем статус сессии
                self.session_model.update_session_status(session['id'], False)

            # Отключаемся
            await client.disconnect()

        except Exception as e:
            result['error'] = str(e)

            # Обновляем статус сессии
            self.session_model.update_session_status(session['id'], False)

        return result

    async def check_all_sessions(self):
        """Проверяет работоспособность всех сессий"""
        try:
            # получаем все сессии
            sessions = self.session_model.get_all_sessions()

            # Создаем задачи для проверки каждой сессии
            tasks = [self.check_session(session) for session in sessions]

            # Запускаем все задачи параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Обрабатываем результаты
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Обрабатываем исключение
                    processed_results.append({
                        'id': sessions[i]['id'],
                        'phone': sessions[i]['phone'],
                        'is_working': False,
                        'error': str(result)
                    })

                    # Обновляем статус сессии
                    self.session_model.update_session_status(sessions[i]['id'], False)
                else:
                    processed_results.append(result)

            return processed_results

        except Exception as e:
            logging.error(f"Ошибка при проверке сессий: {e}")
            raise

    async def assign_proxies_to_sessions(self):
        """Назначает прокси для сессий без прокси"""
        try:
            # Получаем сессии без прокси
            sessions_without_proxy = self.session_model.get_available_sessions_without_proxy()

            if not sessions_without_proxy:
                return {'status': 'error', 'message': f'Все сессии уже имеют прокси'}

            # Получаем доступные прокси
            available_proxies = self.proxy_model.get_available_proxies()

            if not available_proxies:
                logging.warning("Нет доступных прокси для назначения.")
                return {'status': 'warning', 'message': f'Нет доступных прокси для назначения.'}

            assigned_count = 0
            for i, session in enumerate(sessions_without_proxy):
                proxy = available_proxies[i % len(available_proxies)]  # Назначаем прокси по кругу
                self.session_model.assign_proxy_to_session(session['id'], proxy['id'])
                assigned_count += 1

            logging.info(f"Назначено прокси для {assigned_count} сессий.")
            return {'status': 'success', 'message': f'ВСе свободные прокси привязаны, кол-во обработанных строк: {assigned_count}.'}

        except Exception as e:
            logging.error(f"Ошибка при назначении прокси: {e}")
            raise

    async def get_sessions_stats(self):
        """Получаем статистику по сессиям"""
        stats = await self.session_model.get_sessions_stats()
        if stats is not None:
            return {'status': 'success', 'message': stats}
        else:
            return {'status': 'warning', 'message': "Нет данных для статистики."}