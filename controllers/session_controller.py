import asyncio
import json
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config.config import WAITING_FOR_CODE, WAITING_FOR_PASSWORD
from services.session_service import SessionService
from utils.logger import Logger
from views.telegram_view import TelegramView
from utils.admin_checker import is_admin

logger = Logger()
# Словарь для хранения данных сессии во время создания
session_data = {}


class SessionController:
    def __init__(self):
        self.session_service = SessionService()
        self.view = TelegramView()

    async def delete_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет сессию из базы данных"""
        if not await is_admin(update):
            return

        if not context.args or len(context.args) < 1:
            await self.view.send_message(update, "Не указан ID сессии для удаления.")
            return

        session_id = int(context.args[0])
        await self.view.send_result_message(update, await self.session_service.delete_session_by_id(session_id))

    async def start_add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления сессии"""
        if not await is_admin(update):
            return

        # Проверяем аргументы команды
        if not context.args or len(context.args) < 3:
            await self.view.send_message(
                update,
                "Использование: /add_session <телефон> <api_id> <api_hash> [proxy_id]"
            )
            return ConversationHandler.END

        user_id = update.effective_user.id
        phone = context.args[0]
        api_id = context.args[1]
        api_hash = context.args[2]

        # Сохраняем данные в словаре сессий
        session_data[user_id] = {
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'chat_id': update.effective_chat.id,
            'phone_code_hash': None  # Будет заполнено позже
        }

        # Запускаем процесс создания сессии в отдельной задаче
        asyncio.create_task(self.create_session_async(user_id, update, context))

        # Сообщаем пользователю, что процесс начат
        await self.view.send_message(
            update,
            f"Начинаем создание сессии для номера {phone}. Ожидайте запрос кода..."
        )

        return WAITING_FOR_CODE

    async def create_session_async(self, user_id, update, context):
        """Запускает процесс создания сессии асинхронно"""
        data = session_data[user_id]

        async def code_callback(phone, phone_code_hash):
            """Колбэк для получения кода подтверждения через Telegram"""
            # Сохраняем phone_code_hash для использования при входе
            session_data[user_id]['phone_code_hash'] = phone_code_hash

            # Отправляем запрос кода пользователю
            await self.view.send_code_request(data['chat_id'], context, phone)

            # Ждем, пока код будет введен (это будет сделано в process_code)
            # Создаем и ждем будущее значение
            session_data[user_id]['code_future'] = asyncio.Future()
            return await session_data[user_id]['code_future']

        async def password_callback(phone):
            """Колбэк для получения пароля через Telegram"""
            # Отправляем запрос пароля пользователю
            await self.view.send_password_request(data['chat_id'], context, phone)

            # Ждем, пока пароль будет введен
            session_data[user_id]['password_future'] = asyncio.Future()
            return await session_data[user_id]['password_future']

        # Запускаем создание сессии с нашими колбэками
        result = await self.session_service.add_session(
            data['phone'],
            data['api_id'],
            data['api_hash'],
            code_callback=code_callback,
            password_callback=password_callback
        )

        # Отправляем результат пользователю
        await self.view.send_result_message(update, result)

        # Завершаем диалог
        return ConversationHandler.END

    async def process_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный код подтверждения"""
        user_id = update.effective_user.id
        code = update.message.text.strip()

        if user_id in session_data and 'code_future' in session_data[user_id]:
            # Устанавливаем результат будущего значения
            if not session_data[user_id]['code_future'].done():
                session_data[user_id]['code_future'].set_result(code)

            await self.view.send_message(
                update,
                f"✅ Код получен: {code}. Выполняется вход..."
            )

            # Проверяем, требуется ли двухфакторная аутентификация с паролем
            if not session_data[user_id].get('is_2fa_required', False):
                await self.view.send_message(
                    update,
                    "🔑 Двухфакторная аутентификация не требуется. Вход выполнен."
                )
                return ConversationHandler.END
            # Иначе будет запрошен пароль через password_callback
            return WAITING_FOR_PASSWORD
        else:
            await self.view.send_message(
                update,
                "❌ Что-то пошло не так. Пожалуйста, начните процесс заново с команды /add_session"
            )
            return ConversationHandler.END

    async def process_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает полученный пароль двухфакторной аутентификации"""
        user_id = update.effective_user.id
        password = update.message.text.strip()

        # Для безопасности, удаляем сообщение с паролем
        await update.message.delete()

        if user_id in session_data and 'password_future' in session_data[user_id]:
            # Устанавливаем результат будущего значения
            if not session_data[user_id]['password_future'].done():
                session_data[user_id]['password_future'].set_result(password)

            await self.view.send_message(
                update,
                "✅ Пароль получен. Выполняется вход..."
            )

            # Процесс завершится автоматически после проверки пароля
            return ConversationHandler.END
        else:
            await self.view.send_message(
                update,
                "❌ Что-то пошло не так. Пожалуйста, начните процесс заново с команды /add_session"
            )
            return ConversationHandler.END

    async def cancel_add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменяет процесс добавления сессии"""
        user_id = update.effective_user.id

        if user_id in session_data:
            # Если есть активные futures, отменяем их
            if 'code_future' in session_data[user_id] and not session_data[user_id]['code_future'].done():
                session_data[user_id]['code_future'].cancel()

            if 'password_future' in session_data[user_id] and not session_data[user_id]['password_future'].done():
                session_data[user_id]['password_future'].cancel()

            # Удаляем данные сессии
            del session_data[user_id]

        await self.view.send_message(
            update,
            "🚫 Процесс добавления сессии отменен."
        )

        return ConversationHandler.END

    async def check_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /check_sessions - проверяет работоспособность сессий"""
        # Проверяем, является ли пользователь администратором
        if not await is_admin(update):
            return

        await self.view.send_message(update, "Начинаем проверку сессий...")
        await self.view.send_result_message(update, await self.session_service.check_all_sessions())

    #TODO: подумать над применением
    async def update_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные сессии."""
        if not await is_admin(update):
            return

        if not context.args or len(context.args) < 2:
            await self.view.send_message(
                update,
                "Использование: /update_session <session_id> <новые параметры в формате JSON>"
            )
            return

        session_id = int(context.args[0])
        result = await self.session_service.update_session(session_id, json.loads(''.join(context.args[1:])))
        await self.view.send_result_message(update, result)

    async def assign_proxies_to_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Присваивает прокси к сессиям."""
        if not await is_admin(update):
            return
        await self.view.send_result_message(update, await self.session_service.assign_proxies_to_sessions())

    async def get_sessions_stats(self):
        """Получить статистику по сессиям"""
        return await self.session_service.get_sessions_stats()
