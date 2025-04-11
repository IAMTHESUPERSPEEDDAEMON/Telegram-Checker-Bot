import asyncio
from telethon.sync import TelegramClient
from models.session_model import SessionModel
from models.proxy_model import ProxyModel
from utils.logger import Logger

logger = Logger()
class SessionService:
    def __init__(self):
        self.session_model = SessionModel()
        self.proxy_model = ProxyModel()

    async def delete_session(self, session_id):
        """Удаляет сессию из базы данных"""
        find_session = await self.session_model.get_session_by_id(session_id)
        if find_session:
            deleted_session = await self.session_model.delete_session(session_id)
            if deleted_session:
                return {'status': 'success', 'message': f'Сессия {session_id} успешно удалена.'}
            else:
                return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}
        else:
            return {'status': 'error', 'message': f'Сессия {session_id} не найдена в базе данных.'}


    async def add_session(self, phone, api_id, api_hash, code_callback=None, password_callback=None):
        """Создаёт новую сессию и добавляет её в бд"""
        duplicate_session = await self.session_model.get_session_by_phone(phone)
        if duplicate_session is not None:
            return {'status': 'error', 'message': f'Сессия для телефона {phone} уже существует.'}
        else:
            session_data = await self.session_model.create_session(
                phone, api_id, api_hash,
                code_callback=code_callback,
                password_callback=password_callback
            )

            session_id = await self.session_model.add_session_to_db(session_data)
            session_id = session_id.get('id')

            if session_id is not None and isinstance(session_id, int) and session_id > 0:
                return {'status': 'success', 'message': f'Сессия {phone} успешно добавлена.'}
            else:
                return {'status': 'error',
                        'message': f'Ошибка добавления сессии для телефона {phone}.\n{session_id}'}