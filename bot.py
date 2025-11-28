import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from database import Database
from downloader import Downloader
from admin_panel import AdminPanel

# تنظیمات logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class TelegramDownloaderBot:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.token:
            raise ValueError("لطفا TELEGRAM_BOT_TOKEN را تنظیم کنید")

        self.db = Database()
        self.downloader = Downloader()
        self.admin_panel = AdminPanel(self.db)

        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

    def setup_handlers(self):
        # دستورات
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("admin", self.admin_panel.show_admin_panel))

        # هندلرهای پنل ادمین
        self.application.add_handler(CallbackQueryHandler(self.admin_panel.handle_admin_callback, pattern="^admin_"))

        # هندلرهای پیام
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # هندلر رسانه
        self.application.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, self.handle_media))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.add_user(user.id, user.username, user.first_name, user.last_name)

        welcome_text = """
🤖 **به ربات دانلود از یوتیوب و اینستاگرام خوش آمدید!**

📥 **قابلیت‌های ربات:**
• دانلود ویدیو از یوتیوب
• دانلود پست از اینستاگرام
• پنل مدیریت پیشرفته

🚀 **طریقه استفاده:**
فقط لینک ویدیو یا پست را برای ربات ارسال کنید.

🛠️ **دستورات:**
/start - نمایش این راهنما
/admin - پنل مدیریت (فقط ادمین)

⚠️ **نکات:**
• لینک باید مستقیم باشد
• حجم فایل محدود به 50MB است
        """

        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        message_text = update.message.text

        # بررسی وضعیت‌های پنل ادمین
        if context.user_data.get('waiting_for_channel'):
            await self.admin_panel.process_channel_input(update, context)
            return

        if context.user_data.get('waiting_for_broadcast'):
            await self.admin_panel.process_broadcast_message(update, context)
            return

        # بررسی کانال‌های اجباری
        if not await self.check_forced_channels(update, user.id):
            return

        # بررسی لینک
        if self.is_valid_url(message_text):
            await self.process_download(update, context, message_text)
        else:
            await update.message.reply_text("❌ لینک معتبر نیست. لطفا لینک یوتیوب یا اینستاگرام ارسال کنید.")

    def is_valid_url(self, text):
        return any(domain in text for domain in ['youtube.com', 'youtu.be', 'instagram.com'])

    async def check_forced_channels(self, update: Update, user_id: int) -> bool:
        forced_channels = self.db.get_forced_channels()

        if not forced_channels:
            return True

        # در اینجا باید عضویت کاربر در کانال‌ها بررسی شود
        # این بخش نیاز به پیاده‌سازی با API تلگرام دارد

        channel_list = "\n".join([f"• {ch['channel_title']}" for ch in forced_channels])

        await update.message.reply_text(
            f"⚠️ **برای استفاده از ربات باید در کانال‌های زیر عضو شوید:**\n\n{channel_list}\n\n"
            f"پس از عضویت، مجددا لینک را ارسال کنید.",
            parse_mode='Markdown'
        )
        return False

    async def process_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = update.effective_user

        # ارسال پیام در حال پردازش
        processing_msg = await update.message.reply_text("⏳ در حال پردازش لینک...")

        # دانلود مدیا
        file_path, error = self.downloader.download_media(url)

        if error:
            await processing_msg.edit_text(f"❌ {error}")
            return

        # ارسال فایل
        try:
            with open(file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=file,
                    caption="✅ دانلود با موفقیت انجام شد"
                )

            # آپدیت آمار
            self.db.increment_download_count(user.id)

            # پاکسازی فایل
            self.downloader.cleanup_file(file_path)

            await processing_msg.delete()

        except Exception as e:
            await processing_msg.edit_text(f"❌ خطا در ارسال فایل: {str(e)}")
            self.downloader.cleanup_file(file_path)

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # هندلر برای پیام‌های رسانه‌ای در پنل ادمین
        if context.user_data.get('waiting_for_broadcast'):
            await self.admin_panel.process_broadcast_message(update, context)

    def run(self):
        # برای Render - استفاده از Webhook
        port = int(os.environ.get('PORT', 8443))
        webhook_url = os.environ.get('WEBHOOK_URL')

        if webhook_url:
            # استفاده از Webhook در تولید
            self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=self.token,
                webhook_url=f"{webhook_url}/{self.token}"
            )
        else:
            # استفاده از Polling در توسعه
            self.application.run_polling()


if __name__ == '__main__':
    bot = TelegramDownloaderBot()
    bot.run()