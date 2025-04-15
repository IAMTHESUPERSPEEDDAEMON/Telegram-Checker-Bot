import csv
import os

from config.config import TEMP_DIR
from models.checker_model import CheckerModel
from utils.logger import Logger

logger = Logger()


class CheckerService:
    def __init__(self):
        self.checker_model = CheckerModel()
#TODO: доработать обработку csv
#TODO: реализовать логику работы проверки и экспортирования результатов в CSV файл
    async def export_results_to_csv(self, batch_id, original_data):
        """Экспортирует результаты проверки в CSV файл"""
        batch = self.checker_model.get_batch_by_id(batch_id)
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return None

        results = self.checker_model.get_batch_results(batch_id)
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
                if phone and phone in results_dict:
                    writer.writerow(row)

        # Обновляем запись о пакете
        await self.checker_model.update_batch_status(batch_id, 'completed', output_filename)

        return output_path
