import random
import os
from config import config


def load_list_from_file(file_path: str) -> list:
    """Завантажує непорожні рядки з файлу."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не знайдено: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        items = [line.strip() for line in file if line.strip()]

    if not items:
        raise ValueError(f"Файл {file_path} порожній.")

    return items


def generate_random_name() -> tuple[str, str]:
    """Повертає рандомне ім’я та прізвище як кортеж (first_name, last_name)."""
    first_names_file = os.path.join(config.STORAGE_DIR, "first_names.txt")
    last_names_file = os.path.join(config.STORAGE_DIR, "last_names.txt")

    first_names = load_list_from_file(first_names_file)
    last_names = load_list_from_file(last_names_file)

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)

    return first_name, last_name
