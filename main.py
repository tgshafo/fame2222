import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode
import asyncio

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "7283183825:AAFwZWypGCdizQ27JvmKWKiw3ZsJhegJRKs"
OWNER_ID = 287265398

# ВАЖНО! Для проверки подписки нужно:
# 1. Добавить бота в канал как АДМИНИСТРАТОРА
# 2. Получить ID канала через @getidsbot (переслать сообщение из канала)
# 3. Вставить ID сюда (например -1002128511681)
CHANNEL_ID = -1003658136195
CHANNEL_LINK = "https://t.me/+hgYBTlhzZOZmNDY0"

# Пока отключаем проверку подписки для теста
CHECK_SUBSCRIPTION = True  # ВРЕМЕННО ОТКЛЮЧЕНО - потом включи

# Админы
ADMINS = [287265398]

# Категории
CATEGORIES = ['Медийка', 'Высокий фейм', 'Средний фейм', 'Низкий фейм', 'Кодер']

# Логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, db_file="fame_list.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
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
            accepted_at TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications (id)
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
        conn = sqlite3.connect(self.db_file)
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
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, category, created_at FROM applications WHERE status = "pending" ORDER BY created_at DESC')
        apps = cursor.fetchall()
        conn.close()
        return apps
    
    def get_application_by_id(self, app_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        app = cursor.fetchone()
        conn.close()
        return app
    
    def update_application_status(self, app_id, status, admin_id, note=None):
        conn = sqlite3.connect(self.db_file)
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
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''SELECT h.id, h.user_id, h.username, h.nickname, h.category, h.accepted_by, h.accepted_at, a.admin_note 
                         FROM history h JOIN applications a ON h.application_id = a.id ORDER BY h.accepted_at DESC''')
        history = cursor.fetchall()
        conn.close()
        return history
    
    def get_complaints(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE status = "pending" ORDER BY created_at DESC')
        complaints = cursor.fetchall()
        conn.close()
        return complaints
    
    def add_complaint(self, from_user_id, on_user_id, on_username, reason, evidence):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO complaints (from_user_id, on_user_id, on_username, reason, evidence) VALUES (?, ?, ?, ?, ?)',
                      (from_user_id, on_user_id, on_username, reason, evidence))
        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return complaint_id

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
        ["📊 Заявки", "📜 История"],
        ["👑 Управление админами"]
    ], resize_keyboard=True)

def get_categories_keyboard():
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in CATEGORIES]
    return InlineKeyboardMarkup(keyboard)

def get_app_view_keyboard(app_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{app_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")],
        [InlineKeyboardButton("📝 Дополнить", callback_data=f"note_{app_id}")]
    ])

def get_apps_list_keyboard(apps):
    keyboard = [[InlineKeyboardButton(f"👤 {app[3]}", callback_data=f"view_{app[0]}")] for app in apps]
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# ==================== СОСТОЯНИЯ ====================
APP_AVATAR, APP_NICKNAME, APP_CATEGORY, APP_PROJECT, APP_CHAT, APP_KM_YEAR, APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES = range(10)
COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE = range(10, 13)

# ==================== УТИЛИТЫ ====================
async def check_subscription(bot: Bot, user_id: int) -> bool:
    if not CHECK_SUBSCRIPTION or CHANNEL_ID is None:
        return True  # Временно пропускаем проверку
    
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Check subscription error: {e}")
        return True  # Если ошибка - пропускаем

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
    logger.info(f"Start command from user {update.effective_user.id}")
    user_id = update.effective_user.id
    
    if not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Подпишись на канал!</b>\n\n👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>\n\nПосле подписки нажми /start",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return
    
    if user_id == OWNER_ID:
        kb = get_owner_keyboard()
        await update.message.reply_text(
            "👑 <b>Добро пожаловать, Владелец!</b>\n\nИспользуй кнопки ниже 👇",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
    elif user_id in ADMINS:
        kb = get_admin_keyboard()
        await update.message.reply_text(
            "🛡️ <b>Добро пожаловать, Админ!</b>\n\nИспользуй кнопки ниже 👇",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
    else:
        kb = get_user_keyboard()
        await update.message.reply_text(
            "✨ <b>Добро пожаловать в Fame List Bot!</b> ✨\n\nИспользуй кнопки ниже 👇",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 <b>ПРАВИЛА ФЕЙМ-ЛИСТА</b>\n\n"
        "1️⃣ Заполняй анкету честно\n"
        "2️⃣ Без оскорблений и токсичности\n"
        "3️⃣ Без спама и рекламы\n"
        "4️⃣ За скам - моментальный бан\n"
        "5️⃣ Решение модераторов окончательное\n\n"
        "⚠️ Нарушение правил = блокировка без предупреждения!",
        parse_mode=ParseMode.HTML
    )

async def moderation_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👥 <b>МОДЕРАЦИЯ ФЕЙМ-ЛИСТА</b>\n\n"
        "Модераторы проверяют заявки в течение 24-48 часов.\n\n"
        "По всем вопросам в чат: https://t.me/+fvkCt3uNSc84NTE0\n\n"
        "📌 <b>Кто может стать модератором?</b>\n"
        "• Активные участники\n"
        "• Без нарушений\n"
        "• По рекомендации админов\n\n"
        "<i>Модераторы имеют право блокировать нарушителей без предупреждения</i>",
        parse_mode=ParseMode.HTML
    )

# Подача заявки
async def start_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for app in db.get_pending_applications():
        if app[1] == user_id:
            await update.message.reply_text("❌ У вас уже есть активная заявка! Дождитесь решения модерации.")
            return
    await update.message.reply_text("📝 <b>Начинаем оформление заявки!</b>\n\nОтправьте ваше <b>ФОТО (JPG)</b>:", parse_mode=ParseMode.HTML)
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Пожалуйста, отправьте фото в формате JPG!")
        return APP_AVATAR
    context.user_data['avatar'] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Фото принято!\n\nТеперь введите ваш <b>НИКНЕЙМ</b>:", parse_mode=ParseMode.HTML)
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nickname'] = update.message.text
    await update.message.reply_text("✅ Никнейм сохранен!\n\nВыберите <b>КАТЕГОРИЮ</b>:", parse_mode=ParseMode.HTML, reply_markup=get_categories_keyboard())
    return APP_CATEGORY

async def app_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['category'] = query.data.replace("cat_", "")
    await query.edit_message_text(f"✅ Выбрана категория: <b>{context.user_data['category']}</b>\n\nВведите ссылку вашего <b>ПРОЕКТА</b> (обязательно):", parse_mode=ParseMode.HTML)
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("✅ Проект сохранен!\n\nСсылка на <b>ЧАТ</b> (или отправьте '-' для пропуска):", parse_mode=ParseMode.HTML)
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['chat'] = None if text == '-' else text
    await update.message.reply_text("✅ Готово!\n\n<b>С какого года вы в КМ?</b> (например: 2020):", parse_mode=ParseMode.HTML)
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("✅ Запомнил!\n\n<b>Участвовали ли вы в ВК или ДС КМ?</b> (расскажите кратко):", parse_mode=ParseMode.HTML)
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("✅ Понял!\n\n<b>Почему вы хотите попасть в фейм-лист?</b> (или отправьте '-' для пропуска):", parse_mode=ParseMode.HTML)
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['reason'] = None if text == '-' else text
    await update.message.reply_text("✅ Ок!\n\n<b>Как вы поднимали фейм?</b> (расскажите подробно):", parse_mode=ParseMode.HTML)
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("✅ Отлично!\n\n<b>С какими личностями вы знакомы и кто может подтвердить ваше знакомство?</b>", parse_mode=ParseMode.HTML)
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
        f"✅ <b>Заявка #{app_id} успешно отправлена!</b>\n\nОжидайте решения модерации. Мы свяжемся с вами в ближайшее время.",
        parse_mode=ParseMode.HTML, reply_markup=get_user_keyboard()
    )
    
    # Уведомление админам
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(
                admin_id, 
                f"🔔 <b>Новая заявка #{app_id}</b>\n\nОт: {data['nickname']}\nКатегория: {data['category']}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END

# Просмотр заявок
async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("⛔ У вас нет прав для этого действия!")
        return
    
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    
    text = "📊 <b>ТЕКУЩИЕ ЗАЯВКИ</b>\n\n" + "\n".join([f"👤 {app[3]} | #{app[0]}" for app in apps])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    kb = get_apps_list_keyboard(apps)
    if kb:
        await update.message.reply_text("Выберите заявку для просмотра:", reply_markup=kb)

async def view_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    text = format_application(app)
    
    if app[4]:  # avatar_file_id
        await query.message.reply_photo(
            photo=app[4], 
            caption=text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=get_app_view_keyboard(app_id)
        )
        await query.delete_message()
    else:
        await query.edit_message_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=get_app_view_keyboard(app_id)
        )

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("⛔ У вас нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if app and app[14] != 'pending':
        await query.edit_message_text("❌ Эта заявка уже обработана!")
        return
    
    db.update_application_status(app_id, 'accepted', query.from_user.id)
    
    try:
        await context.bot.send_message(
            app[1], 
            f"✅ <b>Поздравляем! Ваша заявка #{app_id} ПРИНЯТА!</b>\n\nДобро пожаловать в фейм-лист!",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(f"✅ Заявка #{app_id} ПРИНЯТА!")

async def reject_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("⛔ У вас нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if app and app[14] != 'pending':
        await query.edit_message_text("❌ Эта заявка уже обработана!")
        return
    
    db.update_application_status(app_id, 'rejected', query.from_user.id)
    
    try:
        await context.bot.send_message(
            app[1], 
            f"❌ <b>Ваша заявка #{app_id} ОТКЛОНЕНА</b>\n\nВы можете подать новую заявку через 14 дней.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(f"❌ Заявка #{app_id} ОТКЛОНЕНА!")

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может просматривать историю!")
        return
    
    history = db.get_history_applications()
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    
    text = "📜 <b>ИСТОРИЯ ЗАЯВОК</b>\n\n"
    for h in history[:20]:  # Показываем последние 20
        text += f"👤 {h[3]} | #{h[0]} | Принял: {h[5]}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено.", reply_markup=get_user_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id == OWNER_ID:
        kb = get_owner_keyboard()
    elif user_id in ADMINS:
        kb = get_admin_keyboard()
    else:
        kb = get_user_keyboard()
    
    await query.edit_message_text("🔙 Главное меню:", reply_markup=kb)

async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ <b>Жалоба на скамера</b>\n\n"
        "Опишите ситуацию и укажите на кого жалуетесь (username или ID):",
        parse_mode=ParseMode.HTML
    )
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Напишите причину жалобы:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("🔗 Пришлите доказательства (скриншоты/ссылки) или '-' если нет:")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text
    if evidence == '-':
        evidence = None
    
    db.add_complaint(
        update.effective_user.id,
        0,  # on_user_id - можно потом добавить парсинг
        context.user_data['complaint_on'],
        context.user_data['complaint_reason'],
        evidence
    )
    
    await update.message.reply_text(
        "✅ Жалоба отправлена модераторам!\n\nМы рассмотрим её в ближайшее время.",
        reply_markup=get_user_keyboard()
    )
    
    # Уведомить админов
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(
                admin_id,
                f"⚠️ <b>Новая жалоба</b>\n\nНа: {context.user_data['complaint_on']}\nПричина: {context.user_data['complaint_reason']}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== MAIN ====================
def main():
    print("🚀 ЗАПУСК БОТА...")
    print("Проверьте:")
    print("1. Токен правильный?")
    print("2. Интернет есть?")
    print("3. Библиотека установлена? (pip install python-telegram-bot==20.7)")
    print()
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        print("✅ Приложение создано")
        
        # Команды
        app.add_handler(CommandHandler("start", start))
        print("✅ Handler /start добавлен")
        
        # Текстовые кнопки
        app.add_handler(MessageHandler(filters.Text("📋 Правила"), rules))
        app.add_handler(MessageHandler(filters.Text("👥 Модерация"), moderation_info))
        app.add_handler(MessageHandler(filters.Text("📊 Заявки"), show_applications))
        app.add_handler(MessageHandler(filters.Text("📜 История"), show_history))
        app.add_handler(MessageHandler(filters.Text("⚠️ Пожаловаться"), handle_complaint))
        
        # Conversation подачи заявки
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
        
        # Conversation жалобы
        app.add_handler(ConversationHandler(
            entry_points=[MessageHandler(filters.Text("⚠️ Пожаловаться"), handle_complaint)],
            states={
                COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
                COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
                COMPLAINT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        ))
        
        # Callback handlers
        app.add_handler(CallbackQueryHandler(view_application, pattern="^view_"))
        app.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
        app.add_handler(CallbackQueryHandler(reject_app, pattern="^reject_"))
        app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
        
        print("✅ Все handlers добавлены")
        print("🚀 Бот запущен и ждет сообщения!")
        print()
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print("\nВозможные решения:")
        print("- Проверьте токен бота")
        print("- pip install python-telegram-bot==20.7")
        print("- Проверьте интернет соединение")

if __name__ == "__main__":
    main()
