import os
import yt_dlp
import requests
import logging
from urllib.parse import urlparse


class Downloader:
    def __init__(self):
        self.download_path = "downloads"
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def is_youtube_url(self, url):
        return any(domain in url for domain in ['youtube.com', 'youtu.be'])

    def is_instagram_url(self, url):
        return 'instagram.com' in url

    def download_media(self, url):
        try:
            if self.is_youtube_url(url):
                return self.download_youtube(url)
            elif self.is_instagram_url(url):
                return self.download_instagram(url)
            else:
                return None, "لینک ارائه شده پشتیبانی نمی‌شود"
        except Exception as e:
            logging.error(f"Download error: {e}")
            return None, f"خطا در دانلود: {str(e)}"

    def download_youtube(self, url):
        try:
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                return filename, None

        except Exception as e:
            return None, f"خطا در دانلود از یوتیوب: {str(e)}"

    def download_instagram(self, url):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                return filename, None

        except Exception as e:
            return None, f"خطا در دانلود از اینستاگرام: {str(e)}"

    def cleanup_file(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logging.error(f"Cleanup error: {e}")