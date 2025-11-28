import os
import logging
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    try:
        import pg8000
        PSYCOPG2_AVAILABLE = False
    except ImportError:
        raise ImportError("Neither psycopg2 nor pg8000 is available")

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.init_db()

    def connect(self):
        try:
            database_url = os.environ.get('DATABASE_URL')
            
            if PSYCOPG2_AVAILABLE:
                # استفاده از psycopg2
                if database_url:
                    self.connection = psycopg2.connect(database_url, sslmode='require')
                else:
                    self.connection = psycopg2.connect(
                        dbname=os.environ.get('DB_NAME', 'telegram_bot'),
                        user=os.environ.get('DB_USER', 'postgres'),
                        password=os.environ.get('DB_PASSWORD', ''),
                        host=os.environ.get('DB_HOST', 'localhost'),
                        port=os.environ.get('DB_PORT', '5432')
                    )
            else:
                # استفاده از pg8000
                if database_url:
                    url = urlparse(database_url)
                    self.connection = pg8000.connect(
                        host=url.hostname,
                        port=url.port,
                        user=url.username,
                        password=url.password,
                        database=url.path[1:],  # حذف اولین اسلش
                        ssl=True
                    )
                else:
                    self.connection = pg8000.connect(
                        host=os.environ.get('DB_HOST', 'localhost'),
                        port=int(os.environ.get('DB_PORT', 5432)),
                        user=os.environ.get('DB_USER', 'postgres'),
                        password=os.environ.get('DB_PASSWORD', ''),
                        database=os.environ.get('DB_NAME', 'telegram_bot')
                    )
            
            logging.info("Connected to database successfully")
        except Exception as e:
            logging.error(f"Database connection error: {e}")

    def execute_query(self, query, params=None):
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                cursor.close()
                return result
            else:
                self.connection.commit()
                cursor.close()
                return True
                
        except Exception as e:
            logging.error(f"Query execution error: {e}")
            self.connection.rollback()
            return False

    def init_db(self):
        # ایجاد جداول
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                download_count INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS forced_channels (
                channel_id BIGINT PRIMARY KEY,
                channel_username VARCHAR(255),
                channel_title VARCHAR(255),
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS statistics (
                id SERIAL PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                last_broadcast TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for query in queries:
            self.execute_query(query)

    def add_user(self, user_id, username, first_name, last_name):
        query = """
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name
        """
        return self.execute_query(query, (user_id, username, first_name, last_name))

    # سایر متدها را نیز به همین صورت با self.execute_query به‌روزرسانی کنید...
