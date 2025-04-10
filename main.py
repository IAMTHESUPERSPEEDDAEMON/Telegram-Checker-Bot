from controllers.bot_controller import BotController
from utils.logger import Logger

logger = Logger()
class Main:
    def __init__(self):
        self.bot_controller = BotController()

    def run(self):
        """Запускает приложение"""
        self.bot_controller.run()

if __name__ == "__main__":
    app = Main()
    app.run()