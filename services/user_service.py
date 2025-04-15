from models.user_model import UserModel


class UserService:
    def __init__(self):
        self.user_model = UserModel()

    async def add_user(self, telegram_id, username=None):
        """Проверить и добавить пользователя в базу данных"""
        is_exists = await self.user_model.get_user_by_telegram_id(telegram_id)
        if is_exists is None:
            user_id = await self.user_model.add_user(telegram_id, username)
            return {'status': 'success', 'message': f'Юзер tgId: {telegram_id} был добавлен c ID: {user_id}'}
        else:
            if is_exists['username'] != username:
                await self.user_model.update_user(telegram_id, username)
                return {'status': 'success', 'message': f'Пользователь с tgId: {telegram_id} был обновлен username'}
            else:
                return {'status': 'error', 'message': f'Пользователь с tgId: {telegram_id} уже существует'}


    async def delete_user(self, telegram_id):
        """Удалить пользователя из базы данных"""
        is_exists = await self.user_model.get_user_by_telegram_id(telegram_id)
        if is_exists is not None :
            await self.user_model.delete_user(telegram_id)
            return {'status': 'success', 'message': f'Пользователь с tgId: {telegram_id} был удален'}
        else:
            return {'status': 'error', 'message': f'Пользователь с tgId: {telegram_id} не существует'}


    async def get_user_by_telegram_id(self, telegram_id):
        """Получить пользователя по его tgId"""
        user = await self.user_model.get_user_by_telegram_id(telegram_id)
        return {'status': 'success', 'message': f'Пользователь с tgId: {telegram_id} - {user}'}

# TODO: добавить формирование CSV файла с данными о пользователях
    async def get_all_users(self):
        """Получить всех пользователей"""
        users = await self.user_model.get_all_users()
        return {'status': 'success', 'users': users}