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
            raise ValueError("❌ لطفا TELEGRAM_BOT_TOKEN را تنظیم کنید")
        
        try:
            self.db = Database()
            # بررسی اینکه اتصال دیتابیس موفق بوده
            if not self.db.connection:
                logging.warning("⚠️ Database connection failed, running in limited mode")
        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
            self.db = None
        
        self.downloader = Downloader()
        
        try:
            self.admin_panel = AdminPanel(self.db)
        except Exception as e:
            logging.error(f"❌ Admin panel initialization failed: {e}")
            self.admin_panel = None
        
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

    def setup_handlers(self):
        # دستورات پایه که بدون دیتابیس هم کار می‌کنند
        self.application.add_handler(CommandHandler("start", self.start))
        
        # فقط اگر دیتابیس فعال است، هندلرهای ادمین را اضافه کن
        if self.db and self.db.connection:
            self.application.add_handler(CommandHandler("admin", self.admin_command))
            self.application.add_handler(CallbackQueryHandler(self.handle_admin_callback, pattern="^admin_"))
        else:
            logging.warning("⚠️ Admin features disabled due to database connection issues")
        
        # هندلرهای اصلی
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # اگر دیتابیس در دسترس است، کاربر را ثبت کن
        if self.db and self.db.connection:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        welcome_text = """
🤖 **به ربات دانلود از یوتیوب و اینستاگرام خوش آمدید!**

📥 **قابلیت‌های ربات:**
• دانلود ویدیو از یوتیوب
• دانلود پست از اینستاگرام

🚀 **طریقه استفاده:**
فقط لینک ویدیو یا پست را برای ربات ارسال کنید.

🛠️ **دستورات:**
/start - نمایش این راهنما
        """
        
        # اگر دیتابیس فعال است، اطلاعات ادمین را اضافه کن
        if self.db and self.db.connection:
            welcome_text += "\n/admin - پنل مدیریت (فقط ادمین)"
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور ادمین فقط اگر دیتابیس فعال است"""
        if not self.admin_panel:
            await update.message.reply_text("❌ پنل مدیریت در حال حاضر در دسترس نیست")
            return
        
        await self.admin_panel.show_admin_panel(update, context)

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت callback های ادمین"""
        if not self.admin_panel:
            await update.callback_query.answer("❌ پنل مدیریت در حال حاضر در دسترس نیست")
            return
        
        await self.admin_panel.handle_admin_callback(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        message_text = update.message.text
        
        # بررسی وضعیت‌های پنل ادمین
        if (self.admin_panel and 
            context.user_data.get('waiting_for_channel')):
            await self.admin_panel.process_channel_input(update, context)
            return
            
        if (self.admin_panel and 
            context.user_data.get('waiting_for_broadcast')):
            await self.admin_panel.process_broadcast_message(update, context)
            return
        
        # بررسی لینک
        if self.is_valid_url(message_text):
            await self.process_download(update, context, message_text, user.id)
        else:
            await update.message.reply_text("❌ لینک معتبر نیست. لطفا لینک یوتیوب یا اینستاگرام ارسال کنید.")

    def is_valid_url(self, text):
        return any(domain in text for domain in ['youtube.com', 'youtu.be', 'instagram.com'])

    async def process_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, user_id: int):
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
            
            # آپدیت آمار اگر دیتابیس فعال است
            if self.db and self.db.connection:
                self.db.increment_download_count(user_id)
            
            # پاکسازی فایل
            self.downloader.cleanup_file(file_path)
            
            await processing_msg.delete()
            
        except Exception as e:
            await processing_msg.edit_text(f"❌ خطا در ارسال فایل: {str(e)}")
            self.downloader.cleanup_file(file_path)

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
    try:
        bot = TelegramDownloaderBot()
        bot.run()
    except Exception as e:
        logging.error(f"❌ Failed to start bot: {e}")
