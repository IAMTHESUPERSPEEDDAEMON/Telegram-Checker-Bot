import mysql.connector
from mysql.connector import pooling
import logging
from config.config import DB_CONFIG


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._create_pool()
            cls._instance._initialize_tables()
        return cls._instance

    def _create_pool(self):
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="telegram_checker_pool",
                pool_size=10,
                **DB_CONFIG
            )
            logging.info("Database connection pool created successfully")
        except mysql.connector.Error as err:
            logging.error(f"Error creating connection pool: {err}")
            raise

    def _initialize_tables(self):
        """Создает необходимые таблицы в базе данных если их нет"""
        create_tables_queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS telegram_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phone VARCHAR(20) UNIQUE NOT NULL,
                api_id VARCHAR(20) NOT NULL,
                api_hash VARCHAR(100) NOT NULL,
                session_file VARCHAR(255) NOT NULL,
                proxy_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS proxies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type ENUM('http', 'socks4', 'socks5') NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INT NOT NULL,
                username VARCHAR(255),
                password VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS check_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phone VARCHAR(20) NOT NULL,
                full_name VARCHAR(255),
                telegram_id BIGINT,
                username VARCHAR(255),
                has_telegram BOOLEAN DEFAULT TRUE,
                user_id INT NOT NULL,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS check_batches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                result_filename VARCHAR(255),
                total_numbers INT NOT NULL,
                processed_numbers INT DEFAULT 0,
                telegram_found INT DEFAULT 0,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        ]

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            # Сначала создаем таблицу proxies, так как на нее ссылается telegram_sessions
            cursor.execute(create_tables_queries[2])

            # Затем создаем остальные таблицы
            for query in [create_tables_queries[0], create_tables_queries[1], create_tables_queries[3],
                          create_tables_queries[4]]:
                cursor.execute(query)

            connection.commit()
            logging.info("Database tables initialized successfully")
        except mysql.connector.Error as err:
            logging.error(f"Error initializing database tables: {err}")
            raise
        finally:
            cursor.close()
            connection.close()

    def get_connection(self):
        """Получает соединение из пула"""
        try:
            return self.pool.get_connection()
        except mysql.connector.Error as err:
            logging.error(f"Error getting connection from pool: {err}")
            raise

    def execute_query(self, query, params=None, fetch=False):
        """Выполняет SQL-запрос и возвращает результат"""
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=True)
        result = None

        try:
            cursor.execute(query, params or ())

            if query.strip().upper().startswith('SELECT') or fetch:
                result = cursor.fetchall()
            else:
                connection.commit()
                result = cursor.lastrowid if cursor.lastrowid else cursor.rowcount

            return result
        except mysql.connector.Error as err:
            logging.error(f"Error executing query: {err}")
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()