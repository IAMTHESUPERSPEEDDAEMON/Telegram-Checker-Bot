import csv
import os
import chardet

from config.config import TEMP_DIR
from utils.logger import Logger
from utils.phone_normalizer import normalize_phone_number

logger=Logger()

class CSVHandler:
    @staticmethod
    def save_temp_file(file_content, filename):
        """Сохраняет временный CSV файл"""
        file_path = os.path.join(TEMP_DIR, filename)

        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            logger.info(f"Saved temporary file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving temporary file: {e}")
            raise

    @staticmethod
    def read_csv_file(file_path):
        """Читает CSV файл и возвращает данные с автоопределением кодировки"""
        try:
            # Определяем кодировку файла
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'  # если не удалось определить — используем utf-8

            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                rows = list(reader)

            logger.info(f"Read CSV file {file_path} using encoding: {encoding}")
            return {
                'header': header,
                'rows': rows,
                'total_rows': len(rows)
            }
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            raise

    @staticmethod
    def extract_phone_name(csv_data):
        """Извлекает номера телефонов и ФИО из данных CSV"""
        result = []

        for row in csv_data['rows']:
            if not row or len(row) < 2:
                continue

            # Предполагаем, что первая колонка - номер телефона, вторая - ФИО
            phone = row[0].strip() if row[0] else None
            full_name = row[1].strip() if len(row) > 1 and row[1] else None

            if phone:
                normalized_phone = normalize_phone_number(phone)

                result.append({
                    'phone': normalized_phone,
                    'full_name': full_name,
                    'original_row': row
                })

        return result

    @staticmethod
    def create_result_csv(output_path, results, original_data):
        """Создает CSV файл с результатами проверки"""
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Записываем заголовок, если он есть
                if 'header' in original_data and original_data['header']:
                    writer.writerow(original_data['header'])

                # Создаем словарь телефон -> результат для быстрого поиска
                results_dict = {r['phone']: r for r in results}

                # Записываем строки, где номер есть в результатах
                for row in original_data['rows']:
                    phone = row[0] if row else None
                    if phone and phone in results_dict:
                        writer.writerow(row)

            logger.info(f"Created result CSV file: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error creating result CSV file: {e}")
            raise