import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройки базы данных
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Настройки Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]

# Настройки проверки
MAX_SESSIONS_PER_USER = 10  # Максимальное количество сессий для одного пользователя
CHECK_DELAY = 0.5  # Задержка между проверками (в секундах)
MAX_RETRIES = 3  # Максимальное количество попыток при ошибке
BATCH_SIZE = 30  # Размер пакета номеров для проверки

# Пути к файлам
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage')
SESSIONS_DIR = os.path.join(STORAGE_DIR, 'sessions')
TEMP_DIR = os.path.join(STORAGE_DIR, 'temp')

# Создание директорий, если они не существуют
for directory in [STORAGE_DIR, SESSIONS_DIR, TEMP_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)