import logging
import os
from logging.handlers import RotatingFileHandler
import inspect
from config import config


class Logger:
    """
    Custom singleton logger class that handles both console and file logging with rotation.
    Console logging shows all messages, while file logging only records warnings and above.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_file_name='app.log', max_file_size=5 * 1024 * 1024, backup_count=5):
        """
        Initialize the logger with custom configuration.

        Args:
            log_file_name (str): Path to the log file
            max_file_size (int): Maximum size of log file before rotation in bytes (default: 5MB)
            backup_count (int): Number of backup files to keep (default: 5)
        """
        # Skip initialization if already initialized
        if self._initialized:
            return

        log_file_path = os.path.join(config.LOG_DIR, log_file_name)
        if not os.path.exists(os.path.dirname(log_file_path)):
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        self.logger = logging.getLogger('app_logger')
        self.logger.setLevel(logging.DEBUG)  # Base logger captures everything

        # 🔥 Убиваємо всі попередні хендлери, щоб уникнути дублювання
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Create console handler that shows all messages (DEBUG and above)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)  # Show all messages in console

        # Create file handler with rotation that only records WARNING and above
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.WARNING)  # Only WARNING and above go to file

        # Create a custom formatter
        formatter = logging.Formatter('[%(asctime)s](%(name)s) %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')

        # Set formatter for both handlers
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # Add handlers to logger
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

        self._initialized = True

    def _log(self, level, message, caller_class=None):
        """
        Internal method to log messages with caller information.

        Args:
            level: The logging level (DEBUG, INFO, etc.)
            message: The message to log
            caller_class: The class that called the logging method (optional)
        """
        if caller_class is None:
            # Try to automatically determine the caller class
            frame = inspect.currentframe().f_back.f_back
            try:
                if 'self' in frame.f_locals:
                    caller_class = frame.f_locals['self'].__class__.__name__
                else:
                    caller_class = frame.f_globals['__name__']
            except:
                caller_class = "Unknown"

        # Set logger name to the caller class
        self.logger.name = caller_class

        # Log the message with the appropriate level
        if level == 'DEBUG':
            self.logger.debug(message)
        elif level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message)
        elif level == 'CRITICAL':
            self.logger.critical(message)

    def debug(self, message, caller_class=None):
        """Log a debug message (console only)."""
        self._log('DEBUG', message, caller_class)

    def info(self, message, caller_class=None):
        """Log an info message (console only)."""
        self._log('INFO', message, caller_class)

    def warning(self, message, caller_class=None):
        """Log a warning message (console and file)."""
        self._log('WARNING', message, caller_class)

    def error(self, message, caller_class=None):
        """Log an error message (console and file)."""
        self._log('ERROR', message, caller_class)

    def critical(self, message, caller_class=None):
        """Log a critical message (console and file)."""
        self._log('CRITICAL', message, caller_class)

# Example usage:
# logger = Logger()  # Creates the singleton instance
#
# # Later in the code, even in different modules:
# logger = Logger()  # Returns the same instance
# logger.info("This will use the same logger instance")