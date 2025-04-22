import os
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Загрузка переменных окружения из app_config.env файла
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app_config.env')
load_dotenv(dotenv_path)

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
MAX_SESSIONS_PER_USER = int(os.getenv('MAX_SESSIONS_PER_USER'))  # Максимальное количество сессий для одного пользователя
CHECK_DELAY = float(os.getenv('CHECK_DELAY'))  # Задержка между проверками (в секундах)
BATCH_SIZE = int(os.getenv('BATCH_SIZE'))  # Размер пакета номеров для проверки

# Пути к файлам
LOG_DIR = os.path.join(BASE_DIR, os.getenv('LOG_DIR'))
STORAGE_DIR = os.path.join(BASE_DIR, os.getenv('STORAGE_DIR'))
SESSIONS_DIR = os.path.join(STORAGE_DIR, 'sessions')
TEMP_DIR = os.path.join(STORAGE_DIR, 'temp')

# Создание директорий, если они не существуют
for directory in [LOG_DIR, STORAGE_DIR, SESSIONS_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)

# Состояния для ConversationHandler
WAITING_FOR_CODE = 1
WAITING_FOR_PASSWORD = 2

