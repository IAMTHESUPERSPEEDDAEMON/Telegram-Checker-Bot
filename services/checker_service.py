import asyncio
import csv
import os

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

    async def process_csv_file(self, file_data, user_id):
        """Обрабатывает CSV файл и проверяет все номера"""
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
        batches = [extracted[i:i + BATCH_SIZE] for i in range(0, len(extracted), BATCH_SIZE)]

        results = []
        sem = asyncio.Semaphore(min(10, len(sessions)))  # max 10 параллельных

        async def worker(batch, session_data):
            async with sem:
                await self._process_batch(batch, session_data, batch_id, user_id, results)

        tasks = []
        for idx, batch in enumerate(batches):
            session_data = sessions[idx % len(sessions)]
            tasks.append(asyncio.create_task(worker(batch, session_data)))

        await asyncio.gather(*tasks)

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
        user = ''

        async with client:
            for item in batch:
                try:
                    # Розбиваємо ПІБ
                    name_parts = item['full_name'].split() if item['full_name'] else []
                    first_name = name_parts[0] if len(name_parts) >= 1 else ''
                    last_name = name_parts[1] if len(name_parts) >= 2 else ''

                    # Якщо не вказано — генеруємо
                    if not first_name:
                        first_name, last_name = generate_random_name()

                    # Стабільний client_id
                    client_id = int(''.join(filter(str.isdigit, item['phone']))[-9:])

                    contact = InputPhoneContact(
                        client_id=client_id,
                        phone=item['phone'],
                        first_name=first_name,
                        last_name=last_name or ''
                    )

                    await asyncio.sleep(2)
                    response = await client(ImportContactsRequest([contact]))
                    user = response.users[0] if response.users else None
                    result = {
                        'phone': item['phone'],
                        'full_name': item['full_name'],
                        'telegram_id': user.id if user else None,
                        'username': user.username if hasattr(user, 'username') else None,
                        'has_telegram': bool(user),
                        'user_id': user_id,
                        'batch_id': batch_id
                    }
                except Exception:
                    result = {
                        'phone': item['phone'],
                        'full_name': item['full_name'],
                        'telegram_id': None,
                        'username': None,
                        'has_telegram': False,
                        'user_id': user_id,
                        'batch_id': batch_id
                    }
                if user:
                    input_user = InputUser(user_id=user.id, access_hash=user.access_hash)
                    await client(DeleteContactsRequest(id=[input_user]))
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
