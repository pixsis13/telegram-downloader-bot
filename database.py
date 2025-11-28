import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging


class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.init_db()

    def connect(self):
        try:
            # استفاده از PostgreSQL در Render
            database_url = os.environ.get('DATABASE_URL')
            if database_url:
                self.connection = psycopg2.connect(database_url, sslmode='require')
            else:
                # برای توسعه محلی
                self.connection = psycopg2.connect(
                    dbname=os.environ.get('DB_NAME', 'telegram_bot'),
                    user=os.environ.get('DB_USER', 'postgres'),
                    password=os.environ.get('DB_PASSWORD', ''),
                    host=os.environ.get('DB_HOST', 'localhost'),
                    port=os.environ.get('DB_PORT', '5432')
                )
            logging.info("Connected to database successfully")
        except Exception as e:
            logging.error(f"Database connection error: {e}")

    def init_db(self):
        try:
            with self.connection.cursor() as cursor:
                # جدول کاربران
                cursor.execute("""
                               CREATE TABLE IF NOT EXISTS users
                               (
                                   user_id
                                   BIGINT
                                   PRIMARY
                                   KEY,
                                   username
                                   VARCHAR
                               (
                                   255
                               ),
                                   first_name VARCHAR
                               (
                                   255
                               ),
                                   last_name VARCHAR
                               (
                                   255
                               ),
                                   join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                   download_count INTEGER DEFAULT 0
                                   )
                               """)

                # جدول کانال‌های اجباری
                cursor.execute("""
                               CREATE TABLE IF NOT EXISTS forced_channels
                               (
                                   channel_id
                                   BIGINT
                                   PRIMARY
                                   KEY,
                                   channel_username
                                   VARCHAR
                               (
                                   255
                               ),
                                   channel_title VARCHAR
                               (
                                   255
                               ),
                                   added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                   )
                               """)

                # جدول آمار
                cursor.execute("""
                               CREATE TABLE IF NOT EXISTS statistics
                               (
                                   id
                                   SERIAL
                                   PRIMARY
                                   KEY,
                                   total_users
                                   INTEGER
                                   DEFAULT
                                   0,
                                   total_downloads
                                   INTEGER
                                   DEFAULT
                                   0,
                                   last_broadcast
                                   TIMESTAMP,
                                   updated_date
                                   TIMESTAMP
                                   DEFAULT
                                   CURRENT_TIMESTAMP
                               )
                               """)

                self.connection.commit()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")

    def add_user(self, user_id, username, first_name, last_name):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                               INSERT INTO users (user_id, username, first_name, last_name)
                               VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO
                               UPDATE SET
                                   username = EXCLUDED.username,
                                   first_name = EXCLUDED.first_name,
                                   last_name = EXCLUDED.last_name
                               """, (user_id, username, first_name, last_name))
                self.connection.commit()
        except Exception as e:
            logging.error(f"Error adding user: {e}")

    def increment_download_count(self, user_id):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                               UPDATE users
                               SET download_count = download_count + 1
                               WHERE user_id = %s
                               """, (user_id,))
                self.connection.commit()
        except Exception as e:
            logging.error(f"Error incrementing download count: {e}")

    def add_forced_channel(self, channel_id, channel_username, channel_title):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                               INSERT INTO forced_channels (channel_id, channel_username, channel_title)
                               VALUES (%s, %s, %s) ON CONFLICT (channel_id) DO
                               UPDATE SET
                                   channel_username = EXCLUDED.channel_username,
                                   channel_title = EXCLUDED.channel_title
                               """, (channel_id, channel_username, channel_title))
                self.connection.commit()
                return True
        except Exception as e:
            logging.error(f"Error adding forced channel: {e}")
            return False

    def get_forced_channels(self):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM forced_channels")
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting forced channels: {e}")
            return []

    def get_all_users(self):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT user_id FROM users")
                return [row['user_id'] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return []

    def get_statistics(self):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                               SELECT COUNT(*)                         as total_users,
                                      COALESCE(SUM(download_count), 0) as total_downloads
                               FROM users
                               """)
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error getting statistics: {e}")
            return {'total_users': 0, 'total_downloads': 0}