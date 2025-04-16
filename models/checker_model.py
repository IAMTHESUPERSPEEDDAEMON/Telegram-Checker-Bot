from utils.logger import Logger
from dao.database import DatabaseManager

logger = Logger()


class CheckerModel:
    def __init__(self):
        self.db = DatabaseManager()

    async def bulk_save_check_result(self, check_results):
        """Сохраняет результат проверки в базу данных"""
        if not check_results:
            return True

        query = """
        INSERT INTO check_results 
        (phone, full_name, telegram_id, username, has_telegram, user_id, batch_id) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        try:
            affected_rows = self.db.execute_batch_query(query, check_results)
            logger.info(f"Кол-во строк записано в таблицу check_results: {affected_rows}")
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Была получена ошибка при выполнении batch-запроса в бд: {e}")
            return False

    async def get_results_by_user_paginated(self, user_id, batch_id, offset=0, limit=1000):
        """Получает результаты проверки для конкретного пользователя"""
        query = """
        SELECT * FROM check_results 
        WHERE user_id = %s AND has_telegram = TRUE AND batch_id = %s
        ORDER BY checked_at DESC
        LIMIT %s OFFSET %s
        """

        try:
            results = self.db.execute_query(query, (user_id, batch_id, limit, offset))
            return results
        except Exception as e:
            logger.error(f"Error getting results for user {user_id}: {e}")
            return None

    async def create_batch(self, user_id, original_filename, total_numbers):
        """Создает новую запись о пакете проверок"""
        query = """
        INSERT INTO check_batches 
        (user_id, original_filename, total_numbers, status) 
        VALUES (%s, %s, %s, 'pending')
        """
        params = (user_id, original_filename, total_numbers)

        try:
            batch_id = self.db.execute_query(query, params)
            logger.info(f"Created new batch {batch_id} for user {user_id}")
            return batch_id
        except Exception as e:
            logger.error(f"Error creating batch for user {user_id}: {e}")
            return None

    async def update_batch_status(self, batch_id, status, result_filename=None):
        """Обновляет статус пакета проверок"""
        try:
            fields = ['status = %s']
            params = [status]

            if result_filename is not None:
                fields.append('result_filename = %s')
                params.append(result_filename)

            # Если статус завершённый — добавляем дату
            if status in ('completed', 'failed'):
                fields.append('completed_at = CURRENT_TIMESTAMP')

            # Собираем финальный запрос
            set_clause = ', '.join(fields)
            query = f"UPDATE check_batches SET {set_clause} WHERE id = %s"
            params.append(batch_id)

            self.db.execute_query(query, params)
            logger.info(f"Updated batch {batch_id} status to {status}")
        except Exception as e:
            logger.error(f"Error updating batch {batch_id} status: {e}")
            raise

    async def increment_batch_counter(self, batch_id, has_telegram=False):
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
            logger.info(f"Incremented counters for batch {batch_id}")
        except Exception as e:
            logger.error(f"Error incrementing counters for batch {batch_id}: {e}")
            raise

    async def get_batch_by_id(self, batch_id):
        """Получает информацию о пакете проверок по ID"""
        query = "SELECT * FROM check_batches WHERE id = %s"

        try:
            batches = self.db.execute_query(query, (batch_id,))
            return batches[0] if batches else None
        except Exception as e:
            logger.error(f"Error getting batch {batch_id}: {e}")
            raise

    async def get_batch_results(self, batch_id):
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
            logger.error(f"Error getting results for batch {batch_id}: {e}")
            raise

