import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from urllib.parse import urlparse

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        if self.connection:  # فقط اگر اتصال موفق بود init_db را صدا بزن
            self.init_db()

    def connect(self):
        try:
            # در Render از DATABASE_URL استفاده کن
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                # پارس کردن URL برای تنظیمات صحیح
                parsed_url = urlparse(database_url)
                
                self.connection = psycopg2.connect(
                    database=parsed_url.path[1:],  # حذف اولین / از مسیر
                    user=parsed_url.username,
                    password=parsed_url.password,
                    host=parsed_url.hostname,
                    port=parsed_url.port,
                    sslmode='require'  # ضروری برای Render
                )
            else:
                # برای توسعه محلی
                self.connection = psycopg2.connect(
                    dbname=os.environ.get('DB_NAME', 'telegram_bot'),
                    user=os.environ.get('DB_USER', 'postgres'),
                    password=os.environ.get('DB_PASSWORD', ''),
                    host=os.environ.get('DB_HOST', 'localhost'),
                    port=os.environ.get('DB_PORT', '5432')
                )
            
            logging.info("✅ Connected to database successfully")
            
        except Exception as e:
            logging.error(f"❌ Database connection error: {e}")
            self.connection = None  # مطمئن شو connection None است اگر خطا دارد

    def init_db(self):
        try:
            with self.connection.cursor() as cursor:
                # جدول کاربران
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        download_count INTEGER DEFAULT 0
                    )
                """)
                
                # جدول کانال‌های اجباری
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS forced_channels (
                        channel_id BIGINT PRIMARY KEY,
                        channel_username VARCHAR(255),
                        channel_title VARCHAR(255),
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                self.connection.commit()
                logging.info("✅ Database tables created successfully")
                
        except Exception as e:
            logging.error(f"❌ Database initialization error: {e}")

    def execute_query(self, query, params=None):
        """متد عمومی برای اجرای کوئری‌ها"""
        if not self.connection:
            logging.error("❌ No database connection")
            return None
            
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
            logging.error(f"❌ Query execution error: {e}")
            if self.connection:
                self.connection.rollback()
            return None

    # متدهای دیگر با استفاده از execute_query
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

    def increment_download_count(self, user_id):
        query = """
            UPDATE users SET download_count = download_count + 1
            WHERE user_id = %s
        """
        return self.execute_query(query, (user_id,))

    def add_forced_channel(self, channel_id, channel_username, channel_title):
        query = """
            INSERT INTO forced_channels (channel_id, channel_username, channel_title)
            VALUES (%s, %s, %s)
            ON CONFLICT (channel_id) DO UPDATE SET
            channel_username = EXCLUDED.channel_username,
            channel_title = EXCLUDED.channel_title
        """
        return self.execute_query(query, (channel_id, channel_username, channel_title))

    def get_forced_channels(self):
        query = "SELECT * FROM forced_channels"
        result = self.execute_query(query)
        return result if result else []

    def get_all_users(self):
        query = "SELECT user_id FROM users"
        result = self.execute_query(query)
        return [row[0] for row in result] if result else []

    def get_statistics(self):
        query = """
            SELECT 
                COUNT(*) as total_users,
                COALESCE(SUM(download_count), 0) as total_downloads
            FROM users
        """
        result = self.execute_query(query)
        if result and len(result) > 0:
            return {'total_users': result[0][0], 'total_downloads': result[0][1]}
        return {'total_users': 0, 'total_downloads': 0}
