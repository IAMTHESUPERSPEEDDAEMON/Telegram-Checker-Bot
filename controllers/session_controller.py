import logging
import asyncio
from telethon.sync import TelegramClient
from models.session_model import SessionModel
from models.proxy_model import ProxyModel


class SessionController:
    def __init__(self):
        self.session_model = SessionModel()
        self.proxy_model = ProxyModel()

    def add_session(self, phone, api_id, api_hash, proxy_id=None):
        """Добавляет новую сессию в базу данных"""
        try:
            session_id = self.session_model.add_session(phone, api_id, api_hash, proxy_id)
            logging.info(f"Добавлена новая сессия для номера {phone}")
            return session_id
        except Exception as e:
            logging.error(f"Ошибка при добавлении сессии для номера {phone}: {e}")

    def get_sessions_stats(self):
        """Получает статистику по сессиям"""
        try:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN proxy_id IS NOT NULL THEN 1 ELSE 0 END) as with_proxy
            FROM telegram_sessions
            """
            result = self.session_model.db.execute_query(query)[0]

            return {
                'total': result['total'],
                'active': result['active'],
                'inactive': result['total'] - result['active'],
                'with_proxy': result['with_proxy'],
                'without_proxy': result['total'] - result['with_proxy']
            }
        except Exception as e:
            logging.error(f"Ошибка при получении статистики по сессиям: {e}")
            raise

    async def check_session(self, session):
        """Проверяет работоспособность одной сессии"""
        result = {
            'id': session['id'],
            'phone': session['phone'],
            'is_working': False,
            'error': None
        }

        # Форматируем прокси для Telethon
        proxy = None
        if 'proxy_type' in session and session['proxy_type']:
            proxy = self.proxy_model.format_proxy_for_telethon({
                'type': session['proxy_type'],
                'host': session['host'],
                'port': session['port'],
                'username': session['proxy_username'],
                'password': session['proxy_password']
            })

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
        # Получаем все сессии
        query = """
        SELECT s.*, p.type as proxy_type, p.host, p.port, p.username as proxy_username, 
               p.password as proxy_password 
        FROM telegram_sessions s
        LEFT JOIN proxies p ON s.proxy_id = p.id
        """

        try:
            sessions = self.session_model.db.execute_query(query)

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

    def assign_proxies_to_sessions(self):
        """Назначает прокси для сессий без прокси"""
        try:
            # Получаем сессии без прокси
            query = "SELECT * FROM telegram_sessions WHERE proxy_id IS NULL"
            sessions_without_proxy = self.session_model.db.execute_query(query)

            if not sessions_without_proxy:
                logging.info("Все сессии уже имеют прокси.")
                return 0

            # Получаем доступные прокси
            available_proxies = self.proxy_model.get_all_proxies()

            if not available_proxies:
                logging.warning("Нет доступных прокси для назначения.")
                return 0

            assigned_count = 0
            for i, session in enumerate(sessions_without_proxy):
                proxy = available_proxies[i % len(available_proxies)]  # Назначаем прокси по кругу
                self.session_model.update_session_proxy(session['id'], proxy['id'])
                assigned_count += 1

            logging.info(f"Назначено прокси для {assigned_count} сессий.")
            return assigned_count

        except Exception as e:
            logging.error(f"Ошибка при назначении прокси: {e}")
            raise

    def update_session(self, session_id: int, new_params: list) -> bool:
        """Обновляет параметры существующей сессии."""
        try:
            session = self.session_model.get_session_by_id(session_id)
            if not session:
                logging.warning(f"Сессия {session_id} не найдена.")
                return False

            # Обновляем данные сессии
            updated = self.session_model.update_session_from_list(session_id, new_params)
            if updated:
                logging.info(f"Сессия {session_id} успешно обновлена.")
                return True
            else:
                logging.warning(f"Не удалось обновить сессию {session_id}.")
                return False

        except Exception as e:
            logging.error(f"Ошибка при обновлении сессии {session_id}: {e}")
            return False

    def remove_session(self, session_id: int) -> bool:
        """Удаляет сессию из базы данных."""
        try:
            removed = self.session_model.delete_session(session_id)
            if removed:
                logging.info(f"Сессия {session_id} успешно удалена.")
                return True
            else:
                logging.warning(f"Сессия {session_id} не найдена или не удалена.")
                return False

        except Exception as e:
            logging.error(f"Ошибка при удалении сессии {session_id}: {e}")
            return False