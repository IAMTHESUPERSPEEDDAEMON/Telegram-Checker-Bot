import asyncio
from telethon.sync import TelegramClient
from telegram import Update
from telegram.ext import ContextTypes
from models.proxy_model import ProxyModel
from services.session_service import SessionService
from utils.logger import Logger
from views.telegram_view import TelegramView
import utils

logger = Logger()
class SessionController:
    def __init__(self):
        self.session_service = SessionService()
        self.proxy_model = ProxyModel()
        self.view = TelegramView()
        self.is_admin = utils.admin_checker.is_admin

    async def delete_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет сессию из базы данных"""
        if not await self.is_admin(update, context):
            await self.view.send_access_denied(update, context)
            return

        if not context.args or len(context.args) < 1:
            await self.view.send_message(update, context, "Не указан ID сессии для удаления.")
            return

        session_id = int(context.args[0])
        result = self.session_service.delete_session(session_id)
        await self.view.send_result_message(update, context, result)


    async def start_add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления сессии"""
        if update.effective_user.id not in ADMIN_IDS:
            await self.view.send_access_denied(update, context)
            return

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                context,
                "Использование: /add_session <телефон> <api_id> <api_hash> [proxy_id]"
            )
            return ConversationHandler.END

        phone = context.args[0]
        api_id = context.args[1]
        api_hash = context.args[2]

        # Сохраняем данные в словаре сессий
        session_data[user_id] = {
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'chat_id': update.effective_chat.id,
            'phone_code_hash': None  # Будет заполнено позже
        }

        # Запускаем процесс создания сессии в отдельной задаче
        asyncio.create_task(self.create_session_async(user_id, update, context))

        # Сообщаем пользователю, что процесс начат
        await self.view.send_message(
            update,
            context,
            f"Начинаем создание сессии для номера {phone}. Ожидайте запрос кода..."
        )

        return WAITING_FOR_CODE



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


    async def check_session(self, session_phone):
        """Проверяет работоспособность одной сессии"""
        # получаем сессию по номеру
        session = await self.session_model.get_session_by_phone(session_phone)
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
                update_result = self.session_model.batch_update_sessions_status(session_updates)
            updated_session_info = self.session_model.get_available_sessions(limit=1000)
            non_active = int(len(processed_results)) - int(len(updated_session_info))

            return {'status': 'success',
                    'message': f'Проверенно {int(len(processed_results))} сессий, активных = {int(len(updated_session_info))}, не активных = {non_active}'}


        except Exception as e:
            logger.error(f"Ошибка при проверке сессий: {e}")
            return {'status': 'error', 'message': f"Ошибка при проверке сессий: {e}"}

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
                logger.warning("Нет доступных прокси для назначения.")
                return {'status': 'warning', 'message': f'Нет доступных прокси для назначения.'}

            assigned_count = 0
            for i, session in enumerate(sessions_without_proxy):
                proxy = available_proxies[i % len(available_proxies)]  # Назначаем прокси по кругу
                self.session_model.assign_proxy_to_session(session['id'], proxy['id'])
                assigned_count += 1

            logger.info(f"Назначено прокси для {assigned_count} сессий.")
            return {'status': 'success', 'message': f'ВСе свободные прокси привязаны, кол-во обработанных строк: {assigned_count}.'}

        except Exception as e:
            logger.error(f"Ошибка при назначении прокси: {e}")
            raise

    async def get_sessions_stats(self):
        """Получаем статистику по сессиям"""
        stats = await self.session_model.get_sessions_stats()
        if stats is not None:
            return {'status': 'success', 'message': stats}
        else:
            return {'status': 'warning', 'message': "Нет данных для статистики."}