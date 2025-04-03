import logging
import os
import csv
import time

from dao.database import DatabaseManager
from config.config import TEMP_DIR


class ResultModel:
    def __init__(self):
        self.db = DatabaseManager()

    def save_check_result(self, phone, full_name, telegram_id=None, username=None, user_id=None, batch_id=None, retries=3, delay=2):
        """Сохраняет результат проверки в базу данных"""
        query = """
        INSERT INTO check_results 
        (phone, full_name, telegram_id, username, has_telegram, user_id) 
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        has_telegram = telegram_id is not None or username is not None
        params = (phone, full_name, telegram_id, username, has_telegram, user_id)

        for attempt in range(1, retries + 1):
            try:
                result_id = self.db.execute_query(query, params)

                # Обновляем счетчик в batch если указан batch_id
                if batch_id and has_telegram:
                    self.increment_batch_counter(batch_id, has_telegram)

                return result_id
            except Exception as e:
                logging.error(f"[Попытка {attempt}] Ошибка сохранения check_result для {phone}: {e}")
                if attempt < retries:
                    logging.info(f"Повтор через {delay} сек...")
                    time.sleep(delay)  # Ждем перед новой попыткой
                else:
                    logging.error("Достигнуто максимальное число попыток. Операция не выполнена.")
                    return None  # Возвращаем None вместо остановки программы

    def get_results_by_user(self, user_id, limit=100):
        """Получает результаты проверки для конкретного пользователя"""
        query = """
        SELECT * FROM check_results 
        WHERE user_id = %s AND has_telegram = TRUE
        ORDER BY checked_at DESC
        LIMIT %s
        """

        try:
            results = self.db.execute_query(query, (user_id, limit))
            return results
        except Exception as e:
            logging.error(f"Error getting results for user {user_id}: {e}")

    def create_batch(self, user_id, original_filename, total_numbers):
        """Создает новую запись о пакете проверок"""
        query = """
        INSERT INTO check_batches 
        (user_id, original_filename, total_numbers, status) 
        VALUES (%s, %s, %s, 'pending')
        """
        params = (user_id, original_filename, total_numbers)

        try:
            batch_id = self.db.execute_query(query, params)
            logging.info(f"Created new batch {batch_id} for user {user_id}")
            return batch_id
        except Exception as e:
            logging.error(f"Error creating batch for user {user_id}: {e}")
            raise

    def update_batch_status(self, batch_id, status, result_filename=None):
        """Обновляет статус пакета проверок"""
        query = """
        UPDATE check_batches
        SET status = %s, 
            result_filename = COALESCE(%s, result_filename),
            completed_at = CASE WHEN %s IN ('completed', 'failed') THEN CURRENT_TIMESTAMP ELSE NULL END
        WHERE id = %s
        """
        params = (status, result_filename, status, batch_id)

        try:
            self.db.execute_query(query, params)
            logging.info(f"Updated batch {batch_id} status to {status}")
        except Exception as e:
            logging.error(f"Error updating batch {batch_id} status: {e}")
            raise

    def increment_batch_counter(self, batch_id, has_telegram=False):
        """Увеличивает счетчик обработанных номеров и найденных номеров с Telegram"""
        query = """
        UPDATE check_batches
        SET processed_numbers = processed_numbers + 1,
            telegram_found = telegram_found + %s
        WHERE id = %s
        """
        telegram_found = 1 if has_telegram else 0
        params = (telegram_found, batch_id)

        try:
            self.db.execute_query(query, params)
        except Exception as e:
            logging.error(f"Error incrementing counters for batch {batch_id}: {e}")
            raise

    def get_batch_by_id(self, batch_id):
        """Получает информацию о пакете проверок по ID"""
        query = "SELECT * FROM check_batches WHERE id = %s"

        try:
            batches = self.db.execute_query(query, (batch_id,))
            return batches[0] if batches else None
        except Exception as e:
            logging.error(f"Error getting batch {batch_id}: {e}")
            raise

    def get_batch_results(self, batch_id):
        """Получает все результаты для конкретного пакета проверок"""
        query = """
        SELECT r.* FROM check_results r
        JOIN check_batches b ON r.user_id = b.user_id
        WHERE b.id = %s AND r.checked_at BETWEEN b.created_at AND COALESCE(b.completed_at, NOW())
        AND r.has_telegram = TRUE
        """

        try:
            results = self.db.execute_query(query, (batch_id,))
            return results
        except Exception as e:
            logging.error(f"Error getting results for batch {batch_id}: {e}")
            raise

    def export_results_to_csv(self, batch_id, original_data):
        """Экспортирует результаты проверки в CSV файл"""
        batch = self.get_batch_by_id(batch_id)
        if not batch:
            logging.error(f"Batch {batch_id} not found")
            return None

        results = self.get_batch_results(batch_id)
        if not results:
            logging.warning(f"No results found for batch {batch_id}")
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
        self.update_batch_status(batch_id, 'completed', output_filename)

        return output_path