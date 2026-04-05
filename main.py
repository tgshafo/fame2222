import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode
import re

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "7283183825:AAFwZWypGCdizQ27JvmKWKiw3ZsJhegJRKs"
OWNER_ID = 287265398
CHANNEL_ID = -1003658136195
CHANNEL_LINK = "https://t.me/+hgYBTlhzZOZmNDY0"
CHECK_SUBSCRIPTION = True  # ОТКЛЮЧАЕМ ПРОВЕРКУ ПОДПИСКИ ДЛЯ ТЕСТА
ADMINS = [287265398]
CATEGORIES = ['Медийка', 'Высокий фейм', 'Средний фейм', 'Низкий фейм', 'Кодер']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, db_file="fame_list.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            nickname TEXT,
            avatar_file_id TEXT,
            category TEXT,
            project TEXT,
            chat_link TEXT,
            km_year TEXT,
            participated_before TEXT,
            reason TEXT,
            fame_method TEXT,
            acquaintances TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            admin_note TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            user_id INTEGER,
            username TEXT,
            nickname TEXT,
            category TEXT,
            accepted_by INTEGER,
            accepted_at TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            on_user_id INTEGER,
            on_username TEXT,
            reason TEXT,
            evidence TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_application(self, user_id, username, nickname, avatar_file_id, category, 
                        project, chat_link, km_year, participated_before, 
                        reason, fame_method, acquaintances):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO applications 
            (user_id, username, nickname, avatar_file_id, category, project, chat_link, 
             km_year, participated_before, reason, fame_method, acquaintances)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username, nickname, avatar_file_id, category, project, chat_link,
             km_year, participated_before, reason, fame_method, acquaintances))
        app_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return app_id
    
    def get_pending_applications(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, category, created_at FROM applications WHERE status = "pending" ORDER BY created_at DESC')
        apps = cursor.fetchall()
        conn.close()
        return apps
    
    def get_application_by_id(self, app_id):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        app = cursor.fetchone()
        conn.close()
        return app
    
    def update_application_status(self, app_id, status, admin_id, note=None):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('UPDATE applications SET status = ?, reviewed_by = ?, reviewed_at = ?, admin_note = ? WHERE id = ?',
                      (status, admin_id, datetime.now(), note, app_id))
        if status == 'accepted':
            app = self.get_application_by_id(app_id)
            if app:
                cursor.execute('INSERT INTO history (application_id, user_id, username, nickname, category, accepted_by, accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (app_id, app[1], app[2], app[3], app[5], admin_id, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_history_applications(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, category, accepted_by, accepted_at FROM history ORDER BY accepted_at DESC')
        history = cursor.fetchall()
        conn.close()
        return history

db = Database()

# ==================== КЛАВИАТУРЫ ====================
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Заявки", "📜 История"]
    ], resize_keyboard=True)

def get_owner_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Заявки", "📜 История"]
    ], resize_keyboard=True)

def get_categories_keyboard():
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in CATEGORIES]
    return InlineKeyboardMarkup(keyboard)

def get_app_view_keyboard(app_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{app_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")]
    ])

def get_apps_list_keyboard(apps):
    if not apps:
        return None
    keyboard = [[InlineKeyboardButton(f"👤 {app[3]} (#{app[0]})", callback_data=f"view_{app[0]}")] for app in apps]
    return InlineKeyboardMarkup(keyboard)

# ==================== СОСТОЯНИЯ ====================
APP_AVATAR, APP_NICKNAME, APP_CATEGORY, APP_PROJECT, APP_CHAT, APP_KM_YEAR, APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES = range(10)
COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE = range(10, 13)

# ==================== УТИЛИТЫ ====================
async def check_subscription(bot: Bot, user_id: int) -> bool:
    return True  # ВРЕМЕННО ОТКЛЮЧАЕМ

def format_application(app):
    return f"""
📝 <b>ЗАЯВКА #{app[0]}</b>

👤 <b>Никнейм:</b> {app[3] or 'Не указан'}
🆔 <b>User ID:</b> <code>{app[1]}</code>
📌 <b>Юзернейм:</b> @{app[2] if app[2] else 'нет'}
🏷 <b>Категория:</b> {app[5]}

📁 <b>Проект:</b> {app[6]}
💬 <b>Чат:</b> {app[7] or 'Пропущено'}

📅 <b>Год в КМ:</b> {app[8]}
🎯 <b>Участие в ВК/ДС КМ:</b> {app[9]}

💭 <b>Почему хочет попасть:</b> {app[10] or 'Не указано'}
📈 <b>Как поднимал фейм:</b> {app[11]}
👥 <b>Знакомства:</b> {app[12]}

⏰ <b>Дата:</b> {app[13]}
"""

# ==================== ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await check_subscription(context.bot, user_id):
        await update.message.reply_text(f"❌ <b>Подпишись на канал!</b>\n\n👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>", parse_mode=ParseMode.HTML)
        return
    
    # ВСЕМ ПОЛЬЗОВАТЕЛЯМ - ОДИНАКОВЫЕ КНОПКИ
    kb = get_user_keyboard()
    await update.message.reply_text(
        "✨ <b>Добро пожаловать в Fame List Bot!</b> ✨\n\n"
        "📝 <b>Отправить заявку</b> - заполнить анкету\n"
        "📋 <b>Правила</b> - ознакомиться с правилами\n"
        "⚠️ <b>Пожаловаться</b> - сообщить о нарушителе\n"
        "👥 <b>Модерация</b> - информация о модераторах\n\n"
        "Нажми на кнопку ниже чтобы начать 👇",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 <b>ПРАВИЛА ФЕЙМ-ЛИСТА</b>\n\n"
        "1️⃣ Заполняй анкету честно и полностью\n"
        "2️⃣ Без оскорблений и токсичности\n"
        "3️⃣ Без спама и рекламы\n"
        "4️⃣ За скам - моментальный бан\n"
        "5️⃣ Решение модераторов окончательное\n\n"
        "⚠️ Нарушение = блокировка!",
        parse_mode=ParseMode.HTML
    )

async def moderation_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👥 <b>МОДЕРАЦИЯ</b>\n\n"
        "Модераторы проверяют заявки в течение 24-48 часов.\n\n"
        "Стать модератором можно после 3 месяцев активного участия.\n\n"
        "По вопросам: @ваш_чат",
        parse_mode=ParseMode.HTML
    )

# ==================== ПОДАЧА ЗАЯВКИ (ВСЕ ПОЛЬЗОВАТЕЛИ) ====================
async def start_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверка на активную заявку
    for app in db.get_pending_applications():
        if app[1] == user_id:
            await update.message.reply_text("❌ У вас уже есть активная заявка! Дождитесь решения модерации.")
            return
    
    await update.message.reply_text(
        "📝 <b>Начинаем оформление заявки!</b>\n\n"
        "Шаг 1 из 9: Отправьте ваше <b>ФОТО</b> (аватарку):",
        parse_mode=ParseMode.HTML
    )
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото!")
        return APP_AVATAR
    context.user_data['avatar'] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Шаг 2 из 9: Введите ваш <b>НИКНЕЙМ</b>:", parse_mode=ParseMode.HTML)
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nickname'] = update.message.text
    await update.message.reply_text("✅ Шаг 3 из 9: Выберите <b>КАТЕГОРИЮ</b>:", parse_mode=ParseMode.HTML, reply_markup=get_categories_keyboard())
    return APP_CATEGORY

async def app_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['category'] = query.data.replace("cat_", "")
    await query.edit_message_text(f"✅ Шаг 4 из 9: Введите название вашего <b>ПРОЕКТА</b>:", parse_mode=ParseMode.HTML)
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("✅ Шаг 5 из 9: Ссылка на <b>ЧАТ</b> (или '-' для пропуска):", parse_mode=ParseMode.HTML)
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['chat'] = None if text == '-' else text
    await update.message.reply_text("✅ Шаг 6 из 9: <b>С какого года в КМ?</b> (например: 2020):", parse_mode=ParseMode.HTML)
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("✅ Шаг 7 из 9: <b>Участвовали в ВК или ДС КМ?</b>:", parse_mode=ParseMode.HTML)
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("✅ Шаг 8 из 9: <b>Почему хотите попасть?</b> (или '-'):", parse_mode=ParseMode.HTML)
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['reason'] = None if text == '-' else text
    await update.message.reply_text("✅ Шаг 9 из 9: <b>Как поднимали фейм?</b>:", parse_mode=ParseMode.HTML)
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("✅ <b>Финальный вопрос:</b> С кем знакомы и кто подтвердит?", parse_mode=ParseMode.HTML)
    return APP_ACQUAINTANCES

async def app_acquaintances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = context.user_data
    
    app_id = db.add_application(
        user.id, user.username, data['nickname'], data['avatar'], data['category'],
        data['project'], data.get('chat'), data['km_year'], data['participated'],
        data.get('reason'), data['fame_method'], update.message.text
    )
    
    await update.message.reply_text(
        f"✅ <b>Заявка #{app_id} успешно отправлена!</b>\n\n"
        f"Модераторы рассмотрят её в ближайшее время.\n"
        f"О результате уведомим в личные сообщения.\n\n"
        f"Спасибо за интерес к фейм-листу! 🎉",
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_keyboard()
    )
    
    # Уведомление админам
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(
                admin_id, 
                f"🔔 <b>НОВАЯ ЗАЯВКА #{app_id}</b>\n\n"
                f"От: {data['nickname']}\n"
                f"Категория: {data['category']}\n"
                f"Проект: {data['project']}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== АДМИН-ФУНКЦИИ ====================
async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await update.message.reply_text("⛔ Нет прав!")
        return
    
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    
    text = "📊 <b>ТЕКУЩИЕ ЗАЯВКИ</b>\n\n" + "\n".join([f"👤 {app[3]} | #{app[0]}" for app in apps])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    kb = get_apps_list_keyboard(apps)
    if kb:
        await update.message.reply_text("Выберите заявку:", reply_markup=kb)

async def view_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    text = format_application(app)
    
    if app[4]:
        await query.message.reply_photo(photo=app[4], caption=text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))
        await query.delete_message()
    else:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.edit_message_text("⛔ Нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    if app[14] != 'pending':
        await query.edit_message_text("❌ Заявка уже обработана!")
        return
    
    if app[1] == user_id:
        await query.edit_message_text("❌ Нельзя принять свою заявку!")
        return
    
    db.update_application_status(app_id, 'accepted', user_id)
    
    try:
        await context.bot.send_message(
            app[1], 
            f"✅ <b>Поздравляем! Заявка #{app_id} ПРИНЯТА!</b>\n\n"
            f"Добро пожаловать в фейм-лист! 🎉",
            parse_mode=ParseMode.HTML
        )
    except:
        pass
    
    await query.edit_message_text(f"✅ Заявка #{app_id} ПРИНЯТА!")

async def reject_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.edit_message_text("⛔ Нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    if app[14] != 'pending':
        await query.edit_message_text("❌ Заявка уже обработана!")
        return
    
    db.update_application_status(app_id, 'rejected', user_id)
    
    try:
        await context.bot.send_message(
            app[1], 
            f"❌ <b>Заявка #{app_id} ОТКЛОНЕНА</b>\n\n"
            f"Вы можете подать новую заявку через 14 дней.",
            parse_mode=ParseMode.HTML
        )
    except:
        pass
    
    await query.edit_message_text(f"❌ Заявка #{app_id} ОТКЛОНЕНА!")

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только для владельца!")
        return
    
    history = db.get_history_applications()
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    
    text = "📜 <b>ИСТОРИЯ ЗАЯВОК</b>\n\n"
    for h in history[:20]:
        text += f"👤 {h[3]} | #{h[0]} | Принял: {h[5]}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== ЖАЛОБЫ ====================
async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ <b>Жалоба на скамера</b>\n\n"
        "Укажите username или ID нарушителя:",
        parse_mode=ParseMode.HTML
    )
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Напишите причину жалобы:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("🔗 Доказательства (или '-'):")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text if update.message.text != '-' else None
    db.add_complaint(update.effective_user.id, 0, context.user_data['complaint_on'], context.user_data['complaint_reason'], evidence)
    await update.message.reply_text("✅ Жалоба отправлена модераторам!", reply_markup=get_user_keyboard())
    
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, f"⚠️ Новая жалоба\nНа: {context.user_data['complaint_on']}\nПричина: {context.user_data['complaint_reason']}")
        except:
            pass
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=get_user_keyboard())
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Главное меню:", reply_markup=get_user_keyboard())

# ==================== MAIN ====================
def main():
    print("🚀 ЗАПУСК БОТА...")
    print("✅ Бот доступен для ВСЕХ пользователей")
    print("✅ Кнопка 'Отправить заявку' видна всем")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Кнопки меню
    app.add_handler(MessageHandler(filters.Text("📋 Правила"), rules))
    app.add_handler(MessageHandler(filters.Text("👥 Модерация"), moderation_info))
    app.add_handler(MessageHandler(filters.Text("📊 Заявки"), show_applications))
    app.add_handler(MessageHandler(filters.Text("📜 История"), show_history))
    
    # Подача заявки (ДЛЯ ВСЕХ)
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text("📝 Отправить заявку"), start_app)],
        states={
            APP_AVATAR: [MessageHandler(filters.PHOTO, app_avatar)],
            APP_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_nickname)],
            APP_CATEGORY: [CallbackQueryHandler(app_category, pattern="^cat_")],
            APP_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_project)],
            APP_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_chat)],
            APP_KM_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_km_year)],
            APP_PARTICIPATED: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_participated)],
            APP_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_reason)],
            APP_FAME_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_fame_method)],
            APP_ACQUAINTANCES: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_acquaintances)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Жалоба
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text("⚠️ Пожаловаться"), handle_complaint)],
        states={
            COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
            COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
            COMPLAINT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(view_application, pattern="^view_"))
    app.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
    app.add_handler(CallbackQueryHandler(reject_app, pattern="^reject_"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    
    print("✅ Бот успешно запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
