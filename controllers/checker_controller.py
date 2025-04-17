from telegram import Update
from telegram.ext import ContextTypes

from services.checker_service import CheckerService
from services.session_service import SessionService
from services.user_service import UserService
from views.telegram_view import TelegramView


class CheckerController:
    def __init__(self):
        self.checker_service = CheckerService()
        self.session_service = SessionService()
        self.user_service    = UserService()
        self.view            = TelegramView()

    async def start_processing_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Сообщаем пользователю, что начинаем обработку
        await self.view.send_start_csv_process(update)
        file_data = await self.checker_service.save_csv(update, context)
        user_in_db = await self.user_service.get_user_by_telegram_id(update.effective_user.id)
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
        result = await self.checker_service.process_csv_file(file_data, user_in_db['message']['id'])
        if result:
            processed_length = len(result['results'])
            found = sum(1 for obj in result['results'] if obj.get('has_telegram') is True)

            #Делаем csv для отправки
            result_csv = await self.checker_service.export_results_to_csv(result['batch_id'], result['original_data'])

            if result_csv is None: # Если не получилось создать csv
                await self.view.send_message(update, f"Произошла ошибка при создании csv файла или ТГ не найдены")
                return

            # Отправляем файл с результатами
            await self.view.send_document(
                update,
                context,
                result_csv,
                caption=f"Найдено {found} номеров с Telegram из {processed_length}"
            )
        else:
            await self.view.send_message(
                update,
                "Не удалось найти номера с Telegram в вашем файле или произошла ошибка при обработке."
            )

