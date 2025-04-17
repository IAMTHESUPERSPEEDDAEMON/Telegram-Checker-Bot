telegram_checker_bot/
├── config/
│   └── config.py           # Конфигурационные параметры (доступ к БД, настройки)
├── models/
│   ├── session_model.py      # Модель для работы с сессиями Telegram
│   ├── proxy_model.py        # Модель для работы с прокси
│   ├── user_model.py         # Модель для работы с юзером
│   └── result_model.py       # Модель для хранения результатов проверки
├── services/
│   ├── session_service.py    # Сервис для обработки логики работы с сессиями
│   ├── proxy_service.py      # Сервис для обработки логики работы с прокси
│   └── user_service.py        # Сервис для обработки логики работы сс юзером
├── dao/
│   └── database.py           # Взаимодействие с MySQL
├── controllers/
│   ├── bot_controller.py     # Контроллер для распределения команд бота
│   ├── session_controller.py # Контроллер для обработки команд сессий
│   ├── proxy_controller.py   # Контроллер для обработки команд прокси
│   └── checker_controller.py # Контроллер для проверки номеров
├── views/
│   └── telegram_view.py      # Отправка сообщений пользователям
├── utils/
│   ├── logger.py             # Логирование
├── main.py                   # Точка входа в приложение
└── requirements.txt          # Зависимости проекта