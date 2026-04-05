import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode
import re
import asyncio

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "7283183825:AAFwZWypGCdizQ27JvmKWKiw3ZsJhegJRKs"
OWNER_ID = 287265398
CHANNEL_ID = -1003658136195
CHANNEL_LINK = "https://t.me/+hgYBTlhzZOZmNDY0"
CHECK_SUBSCRIPTION = True
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
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
    
    def update_application_note(self, app_id, note):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('UPDATE applications SET admin_note = ? WHERE id = ?', (note, app_id))
        conn.commit()
        conn.close()
    
    def get_history_applications(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''SELECT h.id, h.user_id, h.username, h.nickname, h.category, h.accepted_by, h.accepted_at, a.admin_note 
                         FROM history h JOIN applications a ON h.application_id = a.id ORDER BY h.accepted_at DESC''')
        history = cursor.fetchall()
        conn.close()
        return history
    
    def get_complaints(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE status = "pending" ORDER BY created_at DESC')
        complaints = cursor.fetchall()
        conn.close()
        return complaints
    
    def add_complaint(self, from_user_id, on_user_id, on_username, reason, evidence):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO complaints (from_user_id, on_user_id, on_username, reason, evidence) VALUES (?, ?, ?, ?, ?)',
                      (from_user_id, on_user_id, on_username, reason, evidence))
        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return complaint_id
    
    def add_admin(self, admin_id):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO admins VALUES (?)', (admin_id,))
        conn.commit()
        conn.close()
    
    def remove_admin(self, admin_id):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
        conn.close()
    
    def get_all_admins(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM admins')
        admins = [row[0] for row in cursor.fetchall()]
        conn.close()
        return admins

db = Database()

# ==================== КЛАВИАТУРЫ ====================
def get_user_keyboard():
    keyboard = ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"]
    ], resize_keyboard=True)
    return keyboard

def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Текущие заявки", "📜 История заявок"]
    ], resize_keyboard=True)
    return keyboard

def get_owner_keyboard():
    keyboard = ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Текущие заявки", "📜 История заявок"],
        ["👑 Управление админами"]
    ], resize_keyboard=True)
    return keyboard

def get_categories_keyboard():
    keyboard = []
    for cat in CATEGORIES:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
    return InlineKeyboardMarkup(keyboard)

def get_app_view_keyboard(app_id):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{app_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")],
        [InlineKeyboardButton("📝 Дополнить информацию", callback_data=f"add_note_{app_id}")]
    ])
    return keyboard

def get_apps_list_keyboard(apps):
    if not apps:
        return None
    keyboard = []
    for app in apps:
        nickname = app[3] if app[3] else f"user_{app[1]}"
        keyboard.append([InlineKeyboardButton(f"👤 {nickname} | #{app[0]}", callback_data=f"view_{app[0]}")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_list_keyboard(admins):
    if not admins:
        return None
    keyboard = []
    for admin in admins:
        keyboard.append([InlineKeyboardButton(f"❌ Удалить {admin}", callback_data=f"del_admin_{admin}")])
    return InlineKeyboardMarkup(keyboard)

# ==================== СОСТОЯНИЯ ====================
APP_AVATAR, APP_NICKNAME, APP_CATEGORY, APP_PROJECT, APP_CHAT, APP_KM_YEAR, APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES = range(10)
COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE = range(10, 13)
ADD_NOTE_STATE = range(13, 14)
ADD_ADMIN_STATE = range(14, 15)

# ==================== УТИЛИТЫ ====================
async def check_subscription(bot: Bot, user_id: int) -> bool:
    if not CHECK_SUBSCRIPTION or CHANNEL_ID is None:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Check subscription error: {e}")
        return False

def format_application(app):
    text = f"""
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

📝 <b>Заметка админа:</b> {app[16] or 'Нет'}

⏰ <b>Дата подачи:</b> {app[13]}
"""
    return text

# ==================== ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command from user {update.effective_user.id}")
    user_id = update.effective_user.id
    
    if str(user_id) in context.user_data:
        context.user_data.clear()
    
    if not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Для использования бота необходимо подписаться на канал!</b>\n\n"
            f"👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>\n\n"
            f"После подписки нажмите /start снова.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    if user_id == OWNER_ID:
        await update.message.reply_text(
            "👑 <b>Добро пожаловать, Владелец!</b>\n\n"
            "Используй кнопки ниже для управления ботом 👇",
            parse_mode=ParseMode.HTML,
            reply_markup=get_owner_keyboard()
        )
    elif user_id in ADMINS:
        await update.message.reply_text(
            "🛡️ <b>Добро пожаловать, Админ!</b>\n\n"
            "Используй кнопки ниже для модерации 👇",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text(
            "✨ <b>Добро пожаловать в Fame List Bot!</b> ✨\n\n"
            "📌 Здесь ты можешь подать заявку на вступление в фейм-лист\n\n"
            "Используй кнопки ниже для навигации 👇",
            parse_mode=ParseMode.HTML,
            reply_markup=get_user_keyboard()
        )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📜 <b>ПРАВИЛА ФЕЙМ-ЛИСТА</b> 📜

1️⃣ <b>Заполнение анкеты</b>
   • Все поля должны быть заполнены корректно
   • Аватарка должна быть настоящей
   • Указывайте реальные проекты

2️⃣ <b>Поведение</b>
   • Без оскорблений и токсичности
   • Без спама и рекламы
   • Без флуда в чатах

3️⃣ <b>Фейм</b>
   • Не накручивайте фейм искусственно
   • Не создавайте фейковые аккаунты

4️⃣ <b>Скамеры</b>
   • За скам - моментальный бан
   • О скамерах можно сообщить через кнопку "Пожаловаться"

5️⃣ <b>Модерация</b>
   • Решение модераторов окончательное
   • Апелляции принимаются в ЛС владельца

⚠️ <b>Нарушение правил = блокировка без предупреждения!</b>
"""
    await update.message.reply_text(rules_text, parse_mode=ParseMode.HTML)

async def moderation_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
👥 <b>МОДЕРАЦИЯ ФЕЙМ-ЛИСТА</b>

<b>Кто может стать модератором?</b>
• Активные участники фейм-листа
• Стаж от 3 месяцев
• Без нарушений
• По рекомендации текущих админов

<b>Обязанности модераторов:</b>
• Проверка заявок (24-48 часов)
• Решение споров
• Отслеживание скамеров
• Помощь новым участникам

<b>Связь с модерацией:</b>
• По вопросам: @ваш_чат
• Жалобы через кнопку "Пожаловаться"

<i>Модераторы имеют право блокировать нарушителей без предупреждения</i>
"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== ПОДАЧА ЗАЯВКИ ====================
async def start_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Очищаем предыдущие данные
    context.user_data.clear()
    
    # Проверка на активную заявку
    pending_apps = db.get_pending_applications()
    for app in pending_apps:
        if app[1] == user_id:
            await update.message.reply_text("❌ У вас уже есть активная заявка! Дождитесь решения модерации.")
            return
    
    await update.message.reply_text(
        "📝 <b>Начинаем оформление заявки!</b>\n\n"
        "Отправьте ваше <b>ФОТО (JPG)</b>:\n"
        "<i>(Отправьте одно фото, не нажимайте другие кнопки)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте фото!\n\n"
            "Отправьте <b>ОДНО ФОТО</b> в формате JPG или PNG:",
            parse_mode=ParseMode.HTML
        )
        return APP_AVATAR
    
    photo = update.message.photo[-1]
    context.user_data['avatar'] = photo.file_id
    
    await update.message.reply_text(
        "✅ Фото принято!\n\n"
        "Теперь введите ваш <b>НИКНЕЙМ</b>:\n"
        "<i>(Ваше имя, которое будет отображаться)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 2:
        await update.message.reply_text("❌ Никнейм слишком короткий! Введите минимум 2 символа:")
        return APP_NICKNAME
    
    context.user_data['nickname'] = text
    
    await update.message.reply_text(
        f"✅ Никнейм <b>{text}</b> сохранен!\n\n"
        "Выберите <b>КАТЕГОРИЮ</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_categories_keyboard()
    )
    return APP_CATEGORY

async def app_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat_", "")
    context.user_data['category'] = category
    
    await query.edit_message_text(
        f"✅ Выбрана категория: <b>{category}</b>\n\n"
        "Введите название вашего <b>ПРОЕКТА</b> (обязательно):\n"
        "<i>(Например: @project или ссылка)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 2:
        await update.message.reply_text("❌ Введите корректное название проекта!")
        return APP_PROJECT
    
    context.user_data['project'] = text
    
    await update.message.reply_text(
        "✅ Проект сохранен!\n\n"
        "Ссылка на <b>ЧАТ</b> (или отправьте '-' для пропуска):\n"
        "<i>(Можете пропустить, если нет чата)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['chat'] = None if text == '-' else text
    
    await update.message.reply_text(
        "✅ Готово!\n\n"
        "<b>С какого года вы в КМ?</b>\n"
        "<i>(Например: 2020)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r'^\d{4}$', text):
        await update.message.reply_text("❌ Введите корректный год (например: 2020):")
        return APP_KM_YEAR
    
    context.user_data['km_year'] = text
    
    await update.message.reply_text(
        "✅ Запомнил!\n\n"
        "<b>Участвовали ли вы в ВК или ДС КМ?</b>\n"
        "<i>(Расскажите кратко, если участвовали, или напишите 'нет')</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['participated'] = text
    
    await update.message.reply_text(
        "✅ Понял!\n\n"
        "<b>Почему вы хотите попасть в фейм-лист?</b>\n"
        "<i>(Можно пропустить, отправьте '-' если не хотите отвечать)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['reason'] = None if text == '-' else text
    
    await update.message.reply_text(
        "✅ Ок!\n\n"
        "<b>Как вы поднимали фейм?</b>\n"
        "<i>(Расскажите подробно о своем опыте)</i>",
        parse_mode=ParseMode.HTML
    )
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 5:
        await update.message.reply_text("❌ Расскажите подробнее (минимум 5 символов):")
        return APP_FAME_METHOD
    
    context.user_data['fame_method'] = text
    
    await update.message.reply_text(
        "✅ Отлично!\n\n"
        "<b>С какими личностями вы знакомы и кто может подтвердить ваше знакомство?</b>\n"
        "<i>(Укажите имена или ссылки на профили)</i>",
        parse_mode=ParseMode.HTML
    )
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
        f"Ожидайте решения модерации. Мы свяжемся с вами в ближайшее время.\n\n"
        f"📌 Статус заявки можно узнать у модераторов.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_keyboard()
    )
    
    # Уведомление админам
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🔔 <b>Новая заявка #{app_id}</b>\n\n"
                f"От: {data['nickname']}\n"
                f"Категория: {data['category']}\n"
                f"Проект: {data['project']}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ПРОСМОТР ЗАЯВОК (АДМИНЫ) ====================
async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await update.message.reply_text("⛔ У вас нет прав для этого действия!")
        return
    
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    
    text = "📊 <b>ТЕКУЩИЕ ЗАЯВКИ</b>\n\n"
    for app in apps:
        text += f"👤 {app[3]} | #{app[0]}\n"
    
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
    
    if app[4]:
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

# ==================== ПРИНЯТИЕ/ОТКЛОНЕНИЕ ЗАЯВОК ====================
async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.edit_message_text("⛔ У вас нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    if app[14] != 'pending':
        await query.edit_message_text("❌ Эта заявка уже обработана другим админом!")
        return
    
    if app[1] == user_id:
        await query.edit_message_text("❌ Вы не можете принять свою собственную заявку!")
        return
    
    db.update_application_status(app_id, 'accepted', user_id)
    
    try:
        await context.bot.send_message(
            app[1],
            f"✅ <b>Поздравляем! Ваша заявка #{app_id} ПРИНЯТА!</b>\n\n"
            f"Добро пожаловать в фейм-лист! 🎉",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(f"✅ Заявка #{app_id} ПРИНЯТА!")

async def reject_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.edit_message_text("⛔ У вас нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    if app[14] != 'pending':
        await query.edit_message_text("❌ Эта заявка уже обработана другим админом!")
        return
    
    db.update_application_status(app_id, 'rejected', user_id)
    
    try:
        await context.bot.send_message(
            app[1],
            f"❌ <b>Ваша заявка #{app_id} ОТКЛОНЕНА</b>\n\n"
            f"Вы можете подать новую заявку через 14 дней.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(f"❌ Заявка #{app_id} ОТКЛОНЕНА!")

# ==================== ДОПОЛНИТЬ ИНФОРМАЦИЮ ====================
async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.edit_message_text("⛔ У вас нет прав!")
        return
    
    app_id = int(query.data.split("_")[2])
    context.user_data['note_app_id'] = app_id
    
    await query.edit_message_text(
        f"📝 Введите дополнительную информацию для заявки #{app_id}:\n\n"
        f"<i>(Эту информацию увидят другие админы)</i>",
        parse_mode=ParseMode.HTML
    )
    return ADD_NOTE_STATE

async def add_note_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    app_id = context.user_data.get('note_app_id')
    
    if not app_id:
        await update.message.reply_text("❌ Ошибка! Попробуйте снова.")
        return ConversationHandler.END
    
    db.update_application_note(app_id, note)
    
    await update.message.reply_text(
        f"✅ Дополнительная информация для заявки #{app_id} сохранена!",
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ИСТОРИЯ ЗАЯВОК (ТОЛЬКО ВЛАДЕЛЕЦ) ====================
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
    for h in history[:20]:
        text += f"👤 {h[3]} | #{h[0]} | Принял: {h[5]}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== УПРАВЛЕНИЕ АДМИНАМИ (ТОЛЬКО ВЛАДЕЛЕЦ) ====================
async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может управлять админами!")
        return
    
    admins = db.get_all_admins()
    
    text = "👑 <b>Управление админами</b>\n\n"
    text += "<b>Текущие админы:</b>\n"
    for admin in admins:
        text += f"• `{admin}`\n"
    text += "\nОтправьте ID пользователя, чтобы добавить админа:"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return ADD_ADMIN_STATE

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может добавлять админов!")
        return ConversationHandler.END
    
    try:
        new_admin_id = int(update.message.text.strip())
        db.add_admin(new_admin_id)
        ADMINS.append(new_admin_id)
        await update.message.reply_text(
            f"✅ Админ {new_admin_id} успешно добавлен!",
            reply_markup=get_owner_keyboard()
        )
    except ValueError:
        await update.message.reply_text("❌ Неверный ID! Отправьте число.")
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ЖАЛОБЫ НА СКАМЕРОВ ====================
async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ <b>Жалоба на скамера</b>\n\n"
        "Укажите username или ID пользователя, на кого жалуетесь:",
        parse_mode=ParseMode.HTML
    )
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Напишите причину жалобы подробно:")
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
        0,
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
                f"⚠️ <b>Новая жалоба</b>\n\n"
                f"На: {context.user_data['complaint_on']}\n"
                f"Причина: {context.user_data['complaint_reason']}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        kb = get_owner_keyboard()
    elif user_id in ADMINS:
        kb = get_admin_keyboard()
    else:
        kb = get_user_keyboard()
    
    await update.message.reply_text(
        "❌ Действие отменено.",
        reply_markup=kb
    )
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

# ==================== MAIN ====================
def main():
    print("🚀 ЗАПУСК БОТА...")
    print("=" * 50)
    print(f"👑 Владелец: {OWNER_ID}")
    print(f"🛡️ Админы: {ADMINS}")
    print(f"📢 Проверка подписки: {'ВКЛ' if CHECK_SUBSCRIPTION else 'ВЫКЛ'}")
    print("=" * 50)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        print("✅ Приложение создано")
        
        # Команды
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cancel", cancel))
        print("✅ Handler /start добавлен")
        
        # Текстовые кнопки
        app.add_handler(MessageHandler(filters.Text("📋 Правила"), rules))
        app.add_handler(MessageHandler(filters.Text("👥 Модерация"), moderation_info))
        app.add_handler(MessageHandler(filters.Text("📊 Текущие заявки"), show_applications))
        app.add_handler(MessageHandler(filters.Text("📜 История заявок"), show_history))
        app.add_handler(MessageHandler(filters.Text("👑 Управление админами"), manage_admins))
        print("✅ Текстовые handlers добавлены")
        
        # Conversation подачи заявки
        app_conv = ConversationHandler(
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
            allow_reentry=False
        )
        app.add_handler(app_conv)
        print("✅ Conversation заявки добавлен")
        
        # Conversation жалобы
        complaint_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Text("⚠️ Пожаловаться"), handle_complaint)],
            states={
                COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
                COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
                COMPLAINT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=False
        )
        app.add_handler(complaint_conv)
        print("✅ Conversation жалобы добавлен")
        
        # Conversation дополнения информации
        note_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(add_note_start, pattern="^add_note_")],
            states={
                ADD_NOTE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_save)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=False
        )
        app.add_handler(note_conv)
        print("✅ Conversation заметок добавлен")
        
        # Conversation управления админами
        admin_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Text("👑 Управление админами"), manage_admins)],
            states={
                ADD_ADMIN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=False
        )
        app.add_handler(admin_conv)
        print("✅ Conversation админов добавлен")
        
        # Callback handlers
        app.add_handler(CallbackQueryHandler(view_application, pattern="^view_"))
        app.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
        app.add_handler(CallbackQueryHandler(reject_app, pattern="^reject_"))
        app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
        print("✅ Callback handlers добавлены")
        
        print("=" * 50)
        print("🚀 Бот успешно запущен и готов к работе!")
        print("=" * 50)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print("\nВозможные решения:")
        print("- Проверьте токен бота")
        print("- pip install python-telegram-bot==20.7")
        print("- Проверьте интернет соединение")

if __name__ == "__main__":
    main()
