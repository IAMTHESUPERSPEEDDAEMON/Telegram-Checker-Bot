import csv
import os
import logging
from config.config import TEMP_DIR


class CSVHandler:
    @staticmethod
    def save_temp_file(file_content, filename):
        """Сохраняет временный CSV файл"""
        file_path = os.path.join(TEMP_DIR, filename)

        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            logging.info(f"Saved temporary file: {file_path}")
            return file_path
        except Exception as e:
            logging.error(f"Error saving temporary file: {e}")
            raise

    @staticmethod
    def read_csv_file(file_path):
        """Читает CSV файл и возвращает данные"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Пытаемся прочитать заголовок
                rows = list(reader)

            return {
                'header': header,
                'rows': rows,
                'total_rows': len(rows)
            }
        except Exception as e:
            logging.error(f"Error reading CSV file {file_path}: {e}")
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
                # Нормализуем формат номера (удаляем все нецифровые символы)
                normalized_phone = ''.join(filter(str.isdigit, phone))

                # Добавляем + в начало, если его нет и номер не начинается с 8
                if normalized_phone and not normalized_phone.startswith('+'):
                    if normalized_phone.startswith('8') and len(normalized_phone) == 11:
                        # Заменяем 8 на 7 для российских номеров
                        normalized_phone = '+7' + normalized_phone[1:]
                    else:
                        normalized_phone = '+' + normalized_phone

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

            logging.info(f"Created result CSV file: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Error creating result CSV file: {e}")
            raise