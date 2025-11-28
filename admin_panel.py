from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import logging


class AdminPanel:
    def __init__(self, database):
        self.db = database
        self.admin_ids = [int(id.strip()) for id in os.environ.get('ADMIN_IDS', '').split(',') if id.strip()]

    def is_admin(self, user_id):
        return user_id in self.admin_ids

    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text("❌ شما دسترسی ادمین ندارید")
            return

        keyboard = [
            [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")],
            [InlineKeyboardButton("➕ افزودن کانال اجباری", callback_data="admin_add_channel")],
            [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📋 لیست کانال‌های اجباری", callback_data="admin_list_channels")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🛠️ **پنل مدیریت ربات**\n\nلطفا یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ شما دسترسی ادمین ندارید")
            return

        data = query.data

        if data == "admin_stats":
            await self.show_statistics(query)
        elif data == "admin_add_channel":
            await self.request_channel_info(query)
        elif data == "admin_list_channels":
            await self.list_forced_channels(query)
        elif data == "admin_broadcast":
            await self.request_broadcast_message(query)

    async def show_statistics(self, query):
        stats = self.db.get_statistics()
        channels = self.db.get_forced_channels()

        text = f"""
📊 **آمار ربات**

👥 تعداد کاربران: `{stats['total_users']}`
📥 تعداد دانلودها: `{stats['total_downloads']}`
📋 کانال‌های اجباری: `{len(channels)}`

🆔 ادمین‌ها: `{', '.join(map(str, self.admin_ids))}`
        """

        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def request_channel_info(self, query):
        await query.edit_message_text(
            "📝 لطفا اطلاعات کانال را به فرمت زیر ارسال کنید:\n\n"
            "`@channel_username` یا `-1001234567890`\n\n"
            "برای لغو /cancel را ارسال کنید",
            parse_mode='Markdown'
        )
        # ذخیره وضعیت برای دریافت اطلاعات کانال
        context.user_data['waiting_for_channel'] = True

    async def list_forced_channels(self, query):
        channels = self.db.get_forced_channels()

        if not channels:
            text = "📭 هیچ کانال اجباری تنظیم نشده است"
        else:
            text = "📋 **کانال‌های اجباری:**\n\n"
            for channel in channels:
                text += f"• {channel['channel_title']} (`{channel['channel_username']}`)\n"

        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def request_broadcast_message(self, query):
        await query.edit_message_text(
            "📢 لطفا پیام همگانی خود را ارسال کنید:\n\n"
            "برای لغو /cancel را ارسال کنید"
        )
        # ذخیره وضعیت برای دریافت پیام همگانی
        context.user_data['waiting_for_broadcast'] = True

    async def process_channel_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            return

        channel_input = update.message.text.strip()

        # بررسی فرمت
        if channel_input.startswith('@'):
            channel_username = channel_input
            channel_id = None  # نیاز به دریافت ID از طریق API
        elif channel_input.startswith('-100'):
            channel_id = int(channel_input)
            channel_username = None
        else:
            await update.message.reply_text("❌ فرمت نامعتبر. لطفا از @channel_username یا -1001234567890 استفاده کنید")
            return

        # در اینجا باید با API تلگرام اطلاعات کانال را دریافت کنید
        # برای سادگی، فرض می‌کنیم اطلاعات را داریم

        success = self.db.add_forced_channel(channel_id or 0, channel_username, "کانال تست")

        if success:
            await update.message.reply_text("✅ کانال با موفقیت اضافه شد")
        else:
            await update.message.reply_text("❌ خطا در افزودن کانال")

        context.user_data.pop('waiting_for_channel', None)

    async def process_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            return

        message = update.message
        user_ids = self.db.get_all_users()

        success_count = 0
        fail_count = 0

        await update.message.reply_text(f"🚀 شروع ارسال پیام همگانی به {len(user_ids)} کاربر...")

        for uid in user_ids:
            try:
                if message.text:
                    await context.bot.send_message(chat_id=uid, text=message.text)
                elif message.caption:
                    if message.photo:
                        await context.bot.send_photo(chat_id=uid, photo=message.photo[-1].file_id,
                                                     caption=message.caption)
                    elif message.video:
                        await context.bot.send_video(chat_id=uid, video=message.video.file_id, caption=message.caption)
                success_count += 1
            except Exception as e:
                logging.error(f"Broadcast error for user {uid}: {e}")
                fail_count += 1

        await update.message.reply_text(
            f"📊 نتیجه ارسال همگانی:\n\n"
            f"✅ موفق: {success_count}\n"
            f"❌ ناموفق: {fail_count}"
        )

        context.user_data.pop('waiting_for_broadcast', None)