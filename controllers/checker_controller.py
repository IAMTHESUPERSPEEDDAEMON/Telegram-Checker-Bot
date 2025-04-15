import asyncio
import logging
import re
import os
from telethon.sync import TelegramClient
from telethon import functions, types
import random
import string
from models.session_model import SessionModel
from models.proxy_model import ProxyModel
from models.checker_model import CheckerModel
from utils.csv_handler import CSVHandler
from config.config import CHECK_DELAY, MAX_SESSIONS_PER_USER, MAX_RETRIES, SESSIONS_DIR


class CheckerController:
    def __init__(self):
        self.session_model = SessionModel()
        self.proxy_model = ProxyModel()
        self.result_model = CheckerModel()
        self.csv_handler = CSVHandler()
        self.active_clients = {}

    @staticmethod
    def generate_random_name():
        """Генерирует случайное имя для контакта"""
        return ''.join(random.choices(string.ascii_letters, k=8))

    async def _check_telegram_with_client(self, client, phone, full_name):
        """Проверяет наличие аккаунта Telegram для номера с помощью клиента"""
        result = {
            'phone': phone,
            'full_name': full_name,
            'has_telegram': False,
            'telegram_id': None,
            'username': None
        }

        try:
            random_name = self.generate_random_name()
            logging.info(f"Проверяем номер: {phone} (Имя: {random_name})")

            # Импортируем контакт
            import_result = await client(functions.contacts.ImportContactsRequest([
                types.InputPhoneContact(client_id=0, phone=phone, first_name=random_name, last_name="")
            ]))

            if import_result.users:
                user = import_result.users[0]
                result['has_telegram'] = True
                result['telegram_id'] = user.id
                result['username'] = user.username or None
            elif import_result.chats:

                logging.info(f"{phone} зарегистрирован в Telegram (ID: {user.id}, Username: {user.username})")

                # Удаляем контакт
                await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
                logging.info(f"{phone} удален из контактов")
            else:
                logging.info(f"{phone} НЕ зарегистрирован в Telegram")

            return result

        except Exception as e:
            match = re.search(r'A wait of (\d+) seconds is required', str(e))
            if match:
                wait_time = int(match.group(1))
                logging.warning(f"Требуется ожидание {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                # Рекурсивно пробуем снова после ожидания
                return await self._check_telegram_with_client(client, phone, full_name)
            else:
                logging.error(f"Ошибка при проверке {phone}: {e}")
                self.notify_error("check_error", f"Ошибка при проверке номера {phone}", str(e))
                raise

    async def init_client(self, session_data):
        """Инициализирует клиент Telegram"""
        session_file = os.path.join(SESSIONS_DIR, f"session_{session_data['phone']}")
        proxy = None

        # Если есть данные прокси, форматируем их для Telethon
        if 'proxy_type' in session_data and session_data['proxy_type']:
            proxy = self.proxy_model.format_proxy_for_telethon({
                'type': session_data['proxy_type'],
                'host': session_data['host'],
                'port': session_data['port'],
                'username': session_data['proxy_username'],
                'password': session_data['proxy_password']
            })

        # Создаем клиента
        client = TelegramClient(
            session_file,
            session_data['api_id'],
            session_data['api_hash'],
            proxy=proxy,
            system_version="4.16.30-vxCUSTOM",
            device_model="Desktop",
            lang_code="en"
        )

        return client

    async def check_session_auth(self, client, session_id, phone):
        """Проверяет авторизацию сессии"""
        try:
            await client.connect()

            if not await client.is_user_authorized():
                logging.error(f"Сессия для {phone} не авторизована")
                self.session_model.update_session_status(session_id, False)
                self.notify_error("session_error", f"Сессия для номера {phone} не авторизована",
                                  "Требуется авторизация")
                return False

            return True

        except Exception as e:
            logging.error(f"Ошибка при подключении сессии {phone}: {e}")
            self.session_model.update_session_status(session_id, False)
            self.notify_error("session_error", f"Ошибка подключения сессии для номера {phone}", str(e))
            return False

    async def check_number(self, session_data, phone_data, batch_id=None, user_id=None):
        """Проверяет один номер с использованием указанной сессии"""
        client = await self.init_client(session_data)
        session_id = session_data['id']
        phone = phone_data['phone']
        full_name = phone_data['full_name']

        try:
            # Проверяем авторизацию
            if not await self.check_session_auth(client, session_id, session_data['phone']):
                return None

            # Проверяем номер
            result = await self._check_telegram_with_client(client, phone, full_name)

            # Обновляем время последнего использования сессии
            self.session_model.update_last_used(session_id)

            # Сохраняем результат в БД
            if result['has_telegram']:
                self.result_model.bulk_save_check_result(results=batch_id)

            return result

        except Exception as e:
            logging.error(f"Ошибка при проверке номера {phone}: {e}")
            self.notify_error("check_error", f"Ошибка при проверке номера {phone}", str(e))
            return None
        finally:
            # Закрываем соединение
            if client:
                await client.disconnect()

    async def check_numbers_batch(self, numbers_data, user_id):
        """Проверяет пакет номеров с использованием доступных сессий"""
        if not numbers_data:
            return []

        # Получаем доступные сессии (не более MAX_SESSIONS_PER_USER)
        sessions = self.ses.get_available_sessions(MAX_SESSIONS_PER_USER)
        if not sessions:
            error_msg = "Нет доступных сессий для проверки"
            logging.error(error_msg)
            self.notify_error("session_error", error_msg, "Все сессии неактивны или используются")
            return []

        # Создаем запись о пакете проверок
        batch_id = self.result_model.create_batch(
            user_id=user_id,
            original_filename=numbers_data.get('filename', 'unknown'),
            total_numbers=len(numbers_data.get('data', []))
        )

        # Обновляем статус пакета
        self.result_model.update_batch_status(batch_id, 'processing')

        # Распределяем номера между сессиями
        total_sessions = len(sessions)
        results = []

        # Создаем очередь задач
        tasks = []
        for i, phone_data in enumerate(numbers_data.get('data', [])):
            # Определяем, какая сессия будет проверять номер
            session_index = i % total_sessions
            session = sessions[session_index]

            # Создаем задачу для проверки
            task = asyncio.create_task(
                self.check_number(session, phone_data, batch_id, user_id)
            )
            tasks.append(task)

            # Делаем паузу между проверками
            await asyncio.sleep(CHECK_DELAY)

        # Ждем завершения всех задач
        for task in asyncio.as_completed(tasks):
            result = await task
            if result and result['has_telegram']:
                results.append(result)

        # Обновляем статус пакета
        status = 'completed' if results else 'failed'
        self.result_model.update_batch_status(batch_id, status)

        return {'batch_id': batch_id, 'results': results}

    async def process_csv_file(self, file_path, user_id):
        """Обрабатывает CSV файл и проверяет все номера"""
        try:
            # Читаем CSV файл
            csv_data = self.csv_handler.read_csv_file(file_path)

            # Извлекаем номера и имена
            phone_data = self.csv_handler.extract_phone_name(csv_data)

            if not phone_data:
                error_msg = "В файле не найдены номера телефонов"
                logging.error(error_msg)
                self.notify_error("csv_error", error_msg, file_path)
                return None

            # Проверяем номера
            results = await self.check_numbers_batch(
                {'data': phone_data, 'filename': os.path.basename(file_path)},
                user_id
            )

            if not results or not results['results']:
                return None

            # Экспортируем результаты в CSV
            output_path = self.result_model.export_results_to_csv(
                results['batch_id'],
                csv_data
            )

            return {
                'batch_id': results['batch_id'],
                'file_path': output_path,
                'total_checked': len(phone_data),
                'telegram_found': len(results['results'])
            }

        except Exception as e:
            logging.error(f"Ошибка при обработке файла {file_path}: {e}")
            self.notify_error("file_error", f"Ошибка при обработке файла", str(e))
            return None