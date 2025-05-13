import asyncio
import csv
import os
from random import randint

from telethon.errors import UserPrivacyRestrictedError, FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact, InputUser

from config.config import TEMP_DIR, BATCH_SIZE
from models.checker_model import CheckerModel
from models.session_model import SessionModel
from services.session_service import SessionService
from utils.csv_handler import CSVHandler
from utils.logger import Logger
from utils.name_generator import generate_random_name
from utils.phone_normalizer import normalize_phone_number

logger = Logger()


class CheckerService:
    def __init__(self):
        self.checker_model = CheckerModel()
        self.session_service = SessionService()
        self.session_model = SessionModel()
        self.csv_handler = CSVHandler()

    async def save_csv(self, update, context):
        # Получаем информацию о файле
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name

        try:
            # Скачиваем файл
            file_object = await context.bot.get_file(file_id)
            file_content = await file_object.download_as_bytearray()

            # Сохраняем файл во временную директорию
            temp_path = self.csv_handler.save_temp_file(file_content, file_name)
            logger.info(f"Файл {file_name} сохранен во временную директорию")
            return [temp_path, file_name]
        except Exception as e:
            logger.error("Error while downloading file")
            return None

    async def process_csv_file(self, file_data, user_id, update_progress_callback=None):
        """
        Обрабатывает CSV файл и проверяет все номера

        Args:
            file_data: Данные файла
            user_id: ID пользователя
            update_progress_callback: Функция для обновления прогресса в UI
        """
        # Читаем CSV файл
        csv_data = self.csv_handler.read_csv_file(file_data[0])
        phone_data = self.csv_handler.extract_phone_name(csv_data)

        if not phone_data:
            logger.error("В файле не найдены номера телефонов")
            return None

        batch_id = await self.checker_model.create_batch(user_id, file_data[1], csv_data['total_rows'])

        sessions = await self.session_service.get_active_clients()
        if not sessions:
            raise Exception("Нету доступных сессий Telegram")

        extracted = phone_data
        # Уменьшим размер батча для более частой ротации сессий
        BATCH_SIZE = 30  # Меньший размер батча
        batches = [extracted[i:i + BATCH_SIZE] for i in range(0, len(extracted), BATCH_SIZE)]

        total_numbers = len(extracted)
        processed_count = 0

        # Первичное обновление прогресса
        if update_progress_callback:
            await update_progress_callback(total_numbers, processed_count)

        results = []
        # Ограничиваем количество параллельных запросов
        sem = asyncio.Semaphore(min(5, len(sessions)))  # Уменьшено с 10 до 5 для снижения нагрузки

        async def worker(batch, session_idx):
            nonlocal processed_count

            # Получаем сессию для этого пакета
            session_data = sessions[session_idx % len(sessions)]
            client = session_data['client']

            retries = 0
            max_retries = 3  # Максимальное количество повторных попыток

            for attempt in range(max_retries):
                try:
                    # Проверяем соединение перед обработкой батча
                    if not client.is_connected():
                        logger.info(
                            f"Переподключение клиента для сессии {session_data['phone']} перед обработкой батча")
                        await client.connect()
                        # Проверяем авторизацию после повторного подключения
                        if not await client.is_user_authorized():
                            logger.error(f"Клиент не авторизован после подключения: {session_data['phone']}")
                            return  # Пропускаем этот батч, если авторизация не удалась

                    async with sem:
                        await self._process_batch(batch, session_data, batch_id, user_id, results)
                    break  # Если обработка прошла успешно, выходим из цикла попыток

                except FloodWaitError as e:
                    # Если ошибка FloodWaitError, ждем указанное количество секунд
                    wait_time = e.seconds + 1  # добавляем 1 секунду для надежности
                    logger.warning(
                        f"FloodWaitError: Ждем {wait_time} секунд перед повтором для сессии {session_data['phone']}")
                    await asyncio.sleep(wait_time)

                    # После ожидания проверяем соединение
                    if not client.is_connected():
                        await client.connect()

                except ConnectionError as e:
                    # Обработка ошибок соединения
                    logger.error(f"Ошибка соединения для сессии {session_data['phone']}: {str(e)}")

                    # Пробуем переподключиться
                    try:
                        if client.is_connected():
                            await client.disconnect()
                        await asyncio.sleep(2)  # Небольшая пауза перед переподключением
                        await client.connect()
                    except Exception as reconnect_error:
                        logger.error(f"Не удалось переподключиться: {str(reconnect_error)}")

                    # Если последняя попытка - выходим
                    if attempt == max_retries - 1:
                        logger.error(f"Исчерпаны попытки для батча после ошибки соединения")
                        return

                except Exception as e:
                    logger.error(f"Worker ошибка: {str(e)}")

                    # Проверяем содержит ли ошибка текст о разъединении
                    if "disconnected" in str(e).lower():
                        try:
                            # Пробуем переподключиться
                            if client.is_connected():
                                await client.disconnect()
                            await asyncio.sleep(2)
                            await client.connect()
                            logger.info(f"Успешно переподключились после ошибки: {session_data['phone']}")
                        except Exception as reconnect_error:
                            logger.error(f"Ошибка при переподключении: {str(reconnect_error)}")
                            # Если последняя попытка - выходим
                            if attempt == max_retries - 1:
                                return
                    else:
                        # Для других ошибок просто логируем и продолжаем
                        if attempt == max_retries - 1:
                            logger.error(f"Не удалось обработать батч после {max_retries} попыток: {str(e)}")
                            return

            # Обновляем счетчик обработанных номеров
            processed_count += len(batch)

            # Обновляем прогресс
            if update_progress_callback and (
                    len(batch) >= 10 or processed_count % max(5, total_numbers // 20) == 0):
                await update_progress_callback(total_numbers, processed_count)

        tasks = []
        for idx, batch in enumerate(batches):
            # Используем индекс батча для выбора сессии, обеспечивая ротацию
            tasks.append(asyncio.create_task(worker(batch, idx)))

        try:
            await asyncio.gather(*tasks)
        finally:
            # Корректно закрываем все клиенты
            for s in sessions:
                try:
                    if s['client'].is_connected():
                        await s['client'].disconnect()
                except Exception as e:
                    logger.error(f"Ошибка при отключении клиента: {str(e)}")

        # Финальное обновление прогресса
        if update_progress_callback:
            await update_progress_callback(total_numbers, total_numbers)

        await self.checker_model.bulk_save_check_result([
            (
            r['phone'], r['full_name'], r['telegram_id'], r['username'], r['has_telegram'], r['user_id'], r['batch_id'])
            for r in results
        ])

        return {
            'results': results,
            'batch_id': batch_id,
            'original_data': csv_data
        }

    async def _process_batch(self, batch, session_data, batch_id, user_id, results_list):
        client = session_data['client']

        # Проверяем соединение перед началом обработки батча
        if not client.is_connected():
            logger.info(f"Подключение клиента для сессии {session_data['phone']} перед обработкой батча")
            await client.connect()

        for item in batch:
            # Проверяем соединение перед каждым контактом
            if not client.is_connected():
                logger.info(f"Переподключение для сессии {session_data['phone']} при обработке номера {item['phone']}")
                await client.connect()
                # Проверяем, что переподключение успешно
                if not client.is_connected():
                    logger.error(f"Не удалось переподключиться при обработке номера {item['phone']}")
                    continue

            result = {
                'phone': item['phone'],
                'full_name': item['full_name'],
                'telegram_id': None,
                'username': None,
                'has_telegram': False,
                'user_id': user_id,
                'batch_id': batch_id
            }

            name_parts = item['full_name'].split() if item['full_name'] else []
            first_name = name_parts[0] if len(name_parts) >= 1 else ''
            last_name = name_parts[1] if len(name_parts) >= 2 else ''

            if not first_name:
                first_name, last_name = generate_random_name()

            client_id = randint(1, 2_000_000_000)

            contact = InputPhoneContact(
                client_id=client_id,
                phone=item['phone'],
                first_name=first_name,
                last_name=last_name or ''
            )

            # Применяем случайную задержку между запросами для минимизации рисков блокировки
            delay = randint(5, 15)  # Увеличенная случайная задержка
            await asyncio.sleep(delay)

            try:
                # Если у нас более 20 контактов в батче, делаем дополнительную задержку каждые 20 контактов
                if batch.index(item) > 0 and batch.index(item) % 20 == 0:
                    longer_delay = randint(15, 30)
                    logger.info(f"Делаем дополнительную паузу {longer_delay} сек после 20 контактов")
                    await asyncio.sleep(longer_delay)

                response = await client(ImportContactsRequest([contact]))

                # Логирование ответа от Telegram
                logger.info(f"Response for phone {item['phone']}: {response}")

                if response and response.users:
                    user = response.users[0]
                    result['telegram_id'] = user.id
                    result['username'] = getattr(user, 'username', None)
                    result['has_telegram'] = True

                    try:
                        input_user = InputUser(user_id=user.id, access_hash=user.access_hash)
                        await client(DeleteContactsRequest(id=[input_user]))
                    except UserPrivacyRestrictedError:
                        logger.warning(f"Cannot delete contact due to privacy settings: {item['phone']}")
                    except Exception as delete_error:
                        logger.warning(f"Ошибка при удалении контакта {item['phone']}: {str(delete_error)}")
                else:
                    logger.warning(f"No user found for phone {item['phone']}")

            except FloodWaitError as e:
                # Задержка при ошибке FloodWaitError
                wait_time = e.seconds + 1
                logger.warning(
                    f"FloodWaitError: Ждем {wait_time} секунд перед повтором для сессии {session_data['phone']}")
                await asyncio.sleep(wait_time)
                # После ожидания проверяем/восстанавливаем соединение
                if not client.is_connected():
                    await client.connect()
                continue  # Повторим обработку этого контакта после задержки

            except ConnectionError as conn_error:
                logger.error(f"Ошибка соединения при обработке {item['phone']}: {str(conn_error)}")
                # Пытаемся переподключиться
                try:
                    if client.is_connected():
                        await client.disconnect()
                    await asyncio.sleep(2)
                    await client.connect()
                    logger.info(f"Переподключение выполнено для {session_data['phone']}")
                    continue  # Пробуем еще раз с этим же номером
                except Exception as e:
                    logger.error(f"Не удалось переподключиться после ошибки соединения: {str(e)}")
                    break  # Завершаем обработку батча

            results_list.append(result)
            await self.checker_model.increment_batch_counter(batch_id, result['has_telegram'])

    async def export_results_to_csv(self, batch_id, original_data):
        """Экспортирует результаты проверки в CSV файл"""
        batch = await self.checker_model.get_batch_by_id(batch_id)

        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return None

        results = await self.checker_model.get_batch_results(batch_id)
        if not results:
            logger.warning(f"No results found for batch {batch_id}")
            return None

        # Создаем словарь телефон -> результат для быстрого поиска
        results_dict = {r['phone']: r for r in results}

        # Имя выходного файла
        output_filename = f"result_{batch_id}_{os.path.basename(batch['original_filename'])}"
        output_path = os.path.join(TEMP_DIR, output_filename)

        # Записываем в CSV только строки, где номер есть в результатах
        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)

            # Записываем заголовок, если он есть
            if 'header' in original_data and original_data['header']:
                writer.writerow(original_data['header'])

            # Записываем строки
            for row in original_data['rows']:
                phone = row[0] if row else None
                norm_phone = normalize_phone_number(phone)
                if norm_phone and norm_phone in results_dict:
                    writer.writerow(row)

        # Обновляем запись о пакете
        await self.checker_model.update_batch_status(batch_id, 'completed', output_filename)

        return output_path