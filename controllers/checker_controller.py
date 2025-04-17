import asyncio
import logging
import re
import os
import random
import string

from telegram import Update
from telegram.ext import ContextTypes
from telethon.sync import TelegramClient
from telethon import functions, types

from config.config import CHECK_DELAY, MAX_SESSIONS_PER_USER, SESSIONS_DIR
from services.checker_service import CheckerService
from services.session_service import SessionService
from views.telegram_view import TelegramView


class CheckerController:
    def __init__(self):
        self.checker_service = CheckerService()
        self.session_service = SessionService()
        self.view = TelegramView()

    async def start_processing_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Сообщаем пользователю, что начинаем обработку
        await self.view.send_start_csv_process(update)
        file_data = await self.checker_service.save_csv(update, context)
        if file_data is None:
            await self.view.send_message(
                update,
                f"Произошла ошибка при обработке файла"
            )
            return
        else:
            # Обрабатываем файл и проверяем номера
            processing_message = await self.view.send_message(
                update,
                "Проверяю номера из файла на наличие в Telegram..."
            )

        # Запускаем процесс проверки
        result = await self.checker_service.process_csv_file(file_data, update.effective_user.id)
        if result:
            # Отправляем результаты пользователю
            await self.view.send_check_results(update, result)

            # Отправляем файл с результатами
            await self.view.send_document(
                update,
                context,
                result['file_path'],
                caption=f"Найдено {result['telegram_found']} номеров с Telegram из {result['total_checked']}"
            )
        else:
            await self.view.send_message(
                update,
                "Не удалось найти номера с Telegram в вашем файле или произошла ошибка при обработке."
            )

