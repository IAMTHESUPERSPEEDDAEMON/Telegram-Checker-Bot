import csv
import os
import chardet
import codecs

from config.config import TEMP_DIR
from utils.logger import Logger
from utils.phone_normalizer import normalize_phone_number

logger = Logger()


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
                encoding = result['encoding'] or 'utf-8'

            logger.info(f"Detected encoding: {encoding}, confidence: {result.get('confidence', 0)}")

            # Список возможных кодировок для проверки
            encodings_to_try = ['utf-8', 'cp1251', 'latin1', 'ascii', 'iso-8859-1']

            # Добавляем определенную кодировку в начало списка, если она не там
            if encoding and encoding not in encodings_to_try:
                encodings_to_try.insert(0, encoding)

            # Делаем encoding первым в списке, если он уже есть в списке
            if encoding in encodings_to_try and encodings_to_try.index(encoding) != 0:
                encodings_to_try.remove(encoding)
                encodings_to_try.insert(0, encoding)

            # Пробуем прочитать файл с разными кодировками
            for enc in encodings_to_try:
                try:
                    logger.info(f"Trying to read file with encoding: {enc}")
                    with codecs.open(file_path, 'r', encoding=enc, errors='replace') as f:
                        reader = csv.reader(f)
                        header = next(reader, None)  # Пытаемся прочитать заголовок
                        rows = list(reader)

                        if rows:  # Если удалось прочитать строки
                            logger.info(f"Successfully read CSV with encoding: {enc}")
                            logger.info(f"Total rows read: {len(rows)}")
                            if len(rows) > 0:
                                logger.info(f"First row example: {rows[0]}")

                            return {
                                'header': header,
                                'rows': rows,
                                'total_rows': len(rows)
                            }
                except Exception as e:
                    logger.warning(f"Failed to read with encoding {enc}: {e}")
                    continue

            # Если ни одна кодировка не сработала, пробуем последний вариант
            logger.warning("All standard encodings failed, trying binary read and manual splitting")
            try:
                with open(file_path, 'rb') as f:
                    binary_content = f.read().decode('utf-8', errors='replace')
                    lines = binary_content.splitlines()

                    # Определяем разделитель (пробуем запятую, точку с запятой и табуляцию)
                    for delimiter in [',', ';', '\t']:
                        if any(delimiter in line for line in lines[:min(5, len(lines))]):
                            rows = [line.split(delimiter) for line in lines if line.strip()]
                            header = rows[0] if rows else None
                            data_rows = rows[1:] if header and len(rows) > 1 else rows

                            return {
                                'header': header,
                                'rows': data_rows,
                                'total_rows': len(data_rows)
                            }

                # Если разделитель не найден, считаем каждую строку как одну колонку
                rows = [[line.strip()] for line in lines if line.strip()]
                logger.info(f"No delimiter found, treating each line as single column. Found {len(rows)} rows")

                return {
                    'header': None,
                    'rows': rows,
                    'total_rows': len(rows)
                }

            except Exception as e:
                logger.error(f"Error in last-resort parsing: {e}")
                raise


        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            raise

    @staticmethod
    def extract_phone_name(csv_data):
        """Извлекает номера телефонов и ФИО из данных CSV"""
        result = []
        found_phones = 0

        logger.info(f"Extracting phone numbers from {csv_data['total_rows']} rows")

        for row_idx, row in enumerate(csv_data['rows']):
            if not row:
                continue

            # Предполагаем, что первая колонка - номер телефона, вторая - ФИО
            phone = row[0].strip() if row and len(row) > 0 and row[0] else None
            full_name = row[1].strip() if len(row) > 1 and row[1] else None

            if phone:
                normalized_phone = normalize_phone_number(phone)

                if normalized_phone:
                    found_phones += 1
                    result.append({
                        'phone': normalized_phone,
                        'full_name': full_name,
                        'original_row': row
                    })
                else:
                    logger.warning(f"Failed to normalize phone: '{phone}'")

        logger.info(f"Extracted {found_phones} valid phone numbers")

        if found_phones == 0:
            logger.warning("В файле не найдены номера телефонов")

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
                rows_written = 0
                for row in original_data['rows']:
                    phone = row[0] if row and len(row) > 0 else None
                    if phone:
                        normalized_phone = normalize_phone_number(phone)
                        if normalized_phone and normalized_phone in results_dict:
                            writer.writerow(row)
                            rows_written += 1

            logger.info(f"Created result CSV file: {output_path} with {rows_written} rows")
            return output_path
        except Exception as e:
            logger.error(f"Error creating result CSV file: {e}")
            raise