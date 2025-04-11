telegram_checker_bot/
├── config/
│   └── config.py           # Конфигурационные параметры (доступ к БД, настройки)
├── models/
│   ├── session_model.py    # Модель для работы с сессиями Telegram
│   ├── proxy_model.py      # Модель для работы с прокси
│   └── result_model.py     # Модель для хранения результатов проверки
├── dao/
│   ├── database.py         # Взаимодействие с MySQL
├── controllers/
│   ├── bot_controller.py   # Контроллер для обработки команд бота
│   ├── session_controller.py # Контроллер для управления сессиями
│   ├── proxy_controller.py # Контроллер для управления прокси
│   └── checker_controller.py # Контроллер для проверки номеров
├── views/
│   └── telegram_view.py    # Отправка сообщений пользователям
├── utils/
│   ├── logger.py           # Логирование
├── main.py                 # Точка входа в приложение
└── requirements.txt        # Зависимости проекта