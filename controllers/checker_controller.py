from telegram import Update
from telegram.ext import ContextTypes

from services.checker_service import CheckerService
from services.session_service import SessionService
from services.user_service import UserService
from utils.logger import Logger

logger = Logger()

# TODO: переделать под меню как прочие классы и проверить
class CheckerController:
    def __init__(self, view):
        self.checker_service = CheckerService()
        self.session_service = SessionService()
        self.user_service    = UserService()
        self.view            = view
        # Для отслеживания контекста обновления
        self.processing_context = {}

    async def start_processing_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает обработку CSV файла"""
        user_id = update.effective_user.id

        # Сохраняем данные для обновления прогресса
        self.processing_context[user_id] = {
            'update': update,
            'context': context
        }

        # Сохраняем файл
        file_data = await self.checker_service.save_csv(update, context)
        if file_data is None:
            await self.view.show_start_process_menu(update, context, 0)
            return

        # Удаляем меню, которое было до этого
        last_menu_id = context.user_data.get("last_menu_message_id")
        if last_menu_id:
            try:
                await update.effective_chat.delete_message(last_menu_id)
            except Exception as e:
                print(f"Ошибка при удалении старого меню: {e}")

        # Показываем начальное меню
        await self.view.show_start_process_menu(update, context, 1)

        # Получаем данные пользователя
        user_in_db = await self.user_service.get_user_by_telegram_id(user_id)

        # Запускаем процесс проверки
        try:
            # Запускаем обработку с функцией обновления прогресса
            result = await self.checker_service.process_csv_file(
                file_data,
                user_in_db['message']['id'],
                self._update_progress_menu
            )

            if result:
                processed_length = len(result['results'])
                found = sum(1 for obj in result['results'] if obj.get('has_telegram') is True)

                # Экспортируем результаты в CSV
                result_csv = await self.checker_service.export_results_to_csv(
                    result['batch_id'],
                    result['original_data']
                )

                if result_csv is None:
                    await self.view.send_message(update, "Произошла ошибка при создании CSV файла или ТГ не найдены")
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

            # Очищаем контекст обработки
            if user_id in self.processing_context:
                del self.processing_context[user_id]

        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            await self.view.send_message(
                update,
                f"Произошла ошибка при обработке файла: {str(e)}"
            )
            if user_id in self.processing_context:
                del self.processing_context[user_id]

    async def _update_progress_menu(self, total, current):
        """Обновляет меню прогресса обработки для всех активных пользователей"""
        for user_id, ctx in self.processing_context.items():
            try:
                await self.view.show_csv_checker_processing_menu(
                    ctx['update'],
                    ctx['context'],
                    total,
                    current
                )
            except Exception as e:
                logger.error(f"Error updating progress menu: {str(e)}")