import logging
import random
import string
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sqlite3
import os
import json
import ast
from contextlib import contextmanager
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    InputFile,
    ChatMember
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ConversationHandler
)
from telegram.error import TelegramError, BadRequest, Conflict

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8022964832:AAGqdrBdQyaCH3E39PTY5gW5rroOL5kir6E")

admin_ids_str = os.getenv("ADMIN_IDS", "[7993354757, 8414580330]")
try:
    ADMIN_IDS = ast.literal_eval(admin_ids_str)
except Exception as e:
    ADMIN_IDS = [5217335439]
    logger.error(f"Ошибка парсинга ADMIN_IDS: {e}, использую по умолчанию")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "bot_database.db")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
CHANNELS_DIR = os.path.join(BASE_DIR, "channels")
WELCOME_IMAGE_PATH = os.path.join(BASE_DIR, "dobro.jpg")

# Новые состояния для рассылки
(BROADCAST_SELECT_TYPE, BROADCAST_INPUT_TEXT, BROADCAST_INPUT_PHOTO, 
 BROADCAST_CONFIRM, BROADCAST_IN_PROGRESS) = range(5)

def create_directories():
    dirs_to_create = [
        SCRIPTS_DIR,
        CHANNELS_DIR
    ]
    
    for directory in dirs_to_create:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Создана директория: {directory}")

create_directories()

(ADD_SCRIPT, ADD_CHANNEL_ID, ADD_CHANNEL_LINK, ADD_ADMIN, SET_ADMIN_RIGHTS, 
 DELETE_SCRIPT_INPUT, VIEW_CHANNEL_STATS, VIEW_SCRIPT_STATS) = range(8)

PERMISSIONS = {
    'add_script': '➕ Добавить скрипт',
    'delete_script': '➖ Удалить скрипт', 
    'add_channel': '➕ Добавить ОП',
    'remove_channel': '✔ Удалить ОП',
    'list_channels': '🗒 Список ОП',
    'add_admin': '➕ Добавить Админа',
    'remove_admin': '➖ Снять Админа', 
    'list_admins': '📋 Список Админов',
    'view_stats': '📊 Статистика',
    'broadcast': '📢 Рассылка'
}

script_cache = {}
channel_cache = {}
admin_cache = {}
users_cache = {}

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def save_script_to_file(token: str, script_content: str, created_by: int):
    script_data = {
        'token': token,
        'script_content': script_content,
        'created_by': created_by,
        'created_date': datetime.now().isoformat(),
        'views': 0
    }
    
    file_path = os.path.join(SCRIPTS_DIR, f"{token}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
    
    script_cache[token] = script_data

def load_script_from_file(token: str) -> Optional[dict]:
    if token in script_cache:
        return script_cache[token]
    
    file_path = os.path.join(SCRIPTS_DIR, f"{token}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
                script_cache[token] = script_data
                return script_data
        except Exception as e:
            logger.error(f"Ошибка загрузки скрипта {token}: {e}")
    return None

def get_all_scripts_from_files() -> List[dict]:
    scripts = []
    for filename in os.listdir(SCRIPTS_DIR):
        if filename.endswith('.json'):
            token = filename[:-5]
            script_data = load_script_from_file(token)
            if script_data:
                scripts.append(script_data)
    return scripts

def delete_script_file(token: str):
    file_path = os.path.join(SCRIPTS_DIR, f"{token}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        script_cache.pop(token, None)
        return True
    return False

def update_script_views_in_file(token: str):
    script_data = load_script_from_file(token)
    if script_data:
        script_data['views'] = script_data.get('views', 0) + 1
        file_path = os.path.join(SCRIPTS_DIR, f"{token}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        script_cache[token] = script_data

def save_channel_to_file(channel_data: dict):
    channel_id = channel_data['channel_id']
    file_path = os.path.join(CHANNELS_DIR, f"{channel_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(channel_data, f, ensure_ascii=False, indent=2)
    
    channel_cache[channel_id] = channel_data

def load_channel_from_file(channel_id: str) -> Optional[dict]:
    if channel_id in channel_cache:
        return channel_cache[channel_id]
    
    file_path = os.path.join(CHANNELS_DIR, f"{channel_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                channel_data = json.load(f)
                channel_cache[channel_id] = channel_data
                return channel_data
        except Exception as e:
            logger.error(f"Ошибка загрузки канала {channel_id}: {e}")
    return None

def get_all_channels_from_files() -> List[dict]:
    channels = []
    for filename in os.listdir(CHANNELS_DIR):
        if filename.endswith('.json'):
            channel_id = filename[:-5]
            channel_data = load_channel_from_file(channel_id)
            if channel_data:
                channels.append(channel_data)
    return channels

def delete_channel_file(channel_id: str):
    file_path = os.path.join(CHANNELS_DIR, f"{channel_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        channel_cache.pop(channel_id, None)
        return True
    return False

async def get_real_channel_subscribers(bot, channel_id: str) -> int:
    try:
        chat = await bot.get_chat(channel_id)
        members_count = await chat.get_member_count()
        return members_count
    except Exception as e:
        logger.error(f"Ошибка получения подписчиков канала {channel_id}: {e}")
        return 0

async def update_all_channels_subscribers(bot):
    channels = get_all_channels_from_files()
    for channel_data in channels:
        try:
            channel_id = channel_data['channel_id']
            real_subscribers = await get_real_channel_subscribers(bot, channel_id)
            
            channel_data['real_subscribers'] = real_subscribers
            channel_data['current_subscribers'] = real_subscribers
            channel_data['last_updated'] = datetime.now().isoformat()
            
            save_channel_to_file(channel_data)
            logger.info(f"Обновлены подписчики канала {channel_id}: {real_subscribers}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления подписчиков канала {channel_data['channel_id']}: {e}")

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                permissions TEXT DEFAULT 'view_stats',
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем таблицу для хранения пользователей для рассылки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        for admin_id in ADMIN_IDS:
            cursor.execute(
                'INSERT OR IGNORE INTO admins (user_id, permissions, added_by) VALUES (?, ?, ?)',
                (admin_id, 'all', admin_id)
            )
        
        conn.commit()
    
    logger.info("База данных успешно инициализирована")

def generate_token(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_admin(user_id: int) -> bool:
    if user_id in admin_cache:
        return admin_cache[user_id]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone() is not None
        admin_cache[user_id] = result
        return result

def get_admin_permissions(user_id: int) -> List[str]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT permissions FROM admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            if result[0] == 'all':
                return ['all']
            return result[0].split(',') if result[0] else []
        return []

def has_permission(user_id: int, permission: str) -> bool:
    permissions = get_admin_permissions(user_id)
    return 'all' in permissions or permission in permissions

def get_all_scripts() -> List[tuple]:
    scripts_data = get_all_scripts_from_files()
    return [(s['token'], s['script_content'], s.get('views', 0)) for s in scripts_data]

def get_all_channels() -> List[tuple]:
    channels_data = get_all_channels_from_files()
    result = []
    for c in channels_data:
        result.append((
            c['channel_id'], 
            c['username'], 
            c.get('initial_subscribers', 0), 
            c.get('current_subscribers', 0),
            c.get('real_subscribers', 0)
        ))
    return result

def get_all_admins() -> List[tuple]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, permissions FROM admins')
        return cursor.fetchall()

def update_script_views(token: str):
    update_script_views_in_file(token)

def save_user_to_db(user_id: int, username: str, first_name: str, last_name: str = ""):
    """Сохраняем пользователя в базу для рассылки"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name))
        conn.commit()

def get_all_users() -> List[tuple]:
    """Получаем всех пользователей для рассылки"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name FROM users')
        return cursor.fetchall()

def get_user_count() -> int:
    """Получаем количество пользователей в базе"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

async def check_user_subscription(user_id: int, bot) -> Tuple[int, int, List[str]]:
    channels = get_all_channels()
    total_channels = len(channels)
    subscribed_count = 0
    not_subscribed = []
    
    tasks = []
    for channel_id, username, _, _, _ in channels:
        tasks.append(check_single_channel_subscription(bot, user_id, channel_id, username))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, tuple):
            if result[0]:
                subscribed_count += 1
            else:
                not_subscribed.append(result[1])
    
    return subscribed_count, total_channels, not_subscribed

async def check_single_channel_subscription(bot, user_id: int, channel_id: str, username: str) -> Tuple[bool, str]:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        
        if member.status in ['left', 'kicked', 'restricted']:
            return False, username
        else:
            return True, username
            
    except BadRequest as e:
        if "user not found" in str(e).lower() or "chat not found" in str(e).lower():
            return False, username
        logger.error(f"BadRequest для {username}: {str(e)}")
        return False, username
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для {username}: {str(e)}")
        return False, username

async def safe_edit_message(query, text, reply_markup=None, parse_mode='HTML'):
    """Безопасное редактирование сообщения"""
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        await query.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    start_time = datetime.now()
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        user_id = update.effective_user.id
        is_callback = False
    
    # Сохраняем пользователя в базу для рассылки
    user = update.effective_user
    if user:
        save_user_to_db(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or ""
        )
    
    if context.args:
        token = context.args[0]
        await handle_script_access(update, context, token)
        return
    
    keyboard = []
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")])
    keyboard.append([InlineKeyboardButton("🚀 Главный канал", url="https://t.me/robloxscriptrbx")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""**👋 Привет, {update.effective_user.first_name if update.effective_user else 'друг'}!**

Рад видеть тебя в **BAFScripts** 🤖 — умном помощнике для автоматизации от команды RobloxScriptRBX!

**✨ Что я умею:**
• 🔗 **Мгновенный доступ** — умные ссылки ко всем ресурсам
• ⚡ **Автоматизация** — готовые скрипты и инструменты
• 📁 **Шаблоны** — чистый код без лишнего мусора  
• 🔄 **Актуальность** — регулярные обновления и проверки

**📢 Где основной контент?**
Все новости и материалы публикуются в наших Telegram-каналах — обязательно подпишись!

**🌐 Наши ресурсы:**
• 🚀 **Главный канал:** [𝐑𝐎𝐁𝐋𝐎𝐗 𝐒𝐂𝐑𝐈𝐑𝐓𝐒](https://t.me/Bafanchik_Script)

**🛡️ Безопасность важна:**
Всегда проверяй код перед использованием и соблюдай правила платформ!"""
    
    if is_callback:
        try:
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await query.edit_message_media(
                        media=InputFile(photo),
                        caption=welcome_text,
                        parse_mode='Markdown'
                    )
                    await query.edit_message_reply_markup(reply_markup=reply_markup)
            else:
                await query.edit_message_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение: {e}")
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await query.message.reply_photo(
                        photo=InputFile(photo),
                        caption=welcome_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            else:
                await query.message.reply_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
    else:
        try:
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=InputFile(photo),
                        caption=welcome_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            else:
                await update.message.reply_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка при отправке приветствия: {e}")
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    execution_time = (datetime.now() - start_time).total_seconds()
    if execution_time > 0.1:
        logger.warning(f"Время выполнения start: {execution_time:.3f} сек")
    else:
        logger.info(f"Время выполнения start: {execution_time:.3f} сек")

async def handle_script_access(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Обработка доступа к скрипту с проверкой подписки"""
    script_data = load_script_from_file(token)
    
    if not script_data:
        text = "❌ Скрипт не найден!"
        if update.message:
            await update.message.reply_text(text, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, parse_mode='HTML')
        return
    
    channels = get_all_channels()
    
    if channels:
        user_id = update.effective_user.id
        subscribed_count, total_channels, not_subscribed_list = await check_user_subscription(user_id, context.bot)
        
        if subscribed_count >= total_channels:
            update_script_views(token)
            await send_script(update, script_data['script_content'], token)
            return
        
        keyboard = []
        channels_to_show = []
        
        for channel_id, username, _, _, _ in channels:
            if username in not_subscribed_list:
                channels_to_show.append((username, f"https://t.me/{username[1:] if username.startswith('@') else username}"))
        
        for i in range(0, len(channels_to_show), 2):
            row = []
            for j in range(2):
                if i + j < len(channels_to_show):
                    username, url = channels_to_show[i + j]
                    row.append(InlineKeyboardButton(f"➕ {username}", url=url))
            if row:
                keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("✅ Я подписался!", callback_data=f"check_sub_{token}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"<b>❗️ Чтобы получить скрипт, подпишитесь на следующие каналы ({subscribed_count} из {total_channels}):</b>"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await send_script(update, script_data['script_content'], token)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка подписки пользователя на все каналы"""
    query = update.callback_query
    await query.answer("🔄 Проверяю подписки...")
    
    token = query.data.replace("check_sub_", "")
    user_id = query.from_user.id
    
    subscribed_count, total_channels, not_subscribed_list = await check_user_subscription(user_id, context.bot)
    
    if subscribed_count >= total_channels:
        script_data = load_script_from_file(token)
        
        if script_data:
            update_script_views(token)
            await send_script(query, script_data['script_content'], token)
        else:
            await query.edit_message_text("❌ Скрипт не найден!", parse_mode='HTML')
    else:
        keyboard = []
        channels_to_show = []
        channels = get_all_channels()
        
        for channel_id, username, _, _, _ in channels:
            if username in not_subscribed_list:
                channels_to_show.append((username, f"https://t.me/{username[1:] if username.startswith('@') else username}"))
        
        for i in range(0, len(channels_to_show), 2):
            row = []
            for j in range(2):
                if i + j < len(channels_to_show):
                    username, url = channels_to_show[i + j]
                    row.append(InlineKeyboardButton(f"➕ {username}", url=url))
            if row:
                keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_sub_{token}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"<b>❗️ Чтобы получить скрипт, подпишитесь на следующие каналы ({subscribed_count} из {total_channels}):</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def send_script(update, script_content: str, token: str):
    """Отправка скрипта пользователю"""
    text = f"<b>✅ Вот ваш скрипт:</b>\n\n<code>{script_content}</code>\n\n🚀 <b>Удачи в игре!</b>"
    
    reply_markup = None
    
    if hasattr(update, 'edit_message_text'):
        await update.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    elif hasattr(update, 'message'):
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ========== ФУНКЦИИ РАССЫЛКИ ==========

async def broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("📝 Текстовая рассылка", callback_data="broadcast_text")],
        [InlineKeyboardButton("🖼 Рассылка с фото", callback_data="broadcast_photo")],
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="users_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"<b>📢 Меню рассылки</b>\n\n"
    text += f"<b>👥 Всего пользователей в базе:</b> <code>{user_count}</code>\n"
    text += f"<b>📊 Охват аудитории:</b> <code>{user_count}</code> пользователей\n\n"
    text += "<b>Выберите тип рассылки:</b>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователей"""
    query = update.callback_query
    await query.answer()
    
    users = get_all_users()
    user_count = len(users)
    
    # Группируем по датам (примерная статистика)
    today = datetime.now().date()
    week_ago = datetime.now().date()
    
    text = f"<b>📊 Статистика пользователей</b>\n\n"
    text += f"<b>👥 Всего пользователей:</b> <code>{user_count}</code>\n\n"
    
    if user_count > 0:
        text += "<b>Последние 10 пользователей:</b>\n"
        for i, user in enumerate(users[:10], 1):
            user_id, username, first_name, last_name = user
            username_display = f"@{username}" if username else "Без username"
            name = f"{first_name} {last_name}".strip() if last_name else first_name
            text += f"{i}. {name} ({username_display}) - ID: <code>{user_id}</code>\n"
    
    if user_count > 10:
        text += f"\n<i>... и еще {user_count - 10} пользователей</i>"
    
    keyboard = [
        [InlineKeyboardButton("📢 Начать рассылку", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def broadcast_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало текстовой рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_count = get_user_count()
    
    text = f"<b>📝 Текстовая рассылка</b>\n\n"
    text += f"<b>👥 Будет отправлено:</b> <code>{user_count}</code> пользователям\n\n"
    text += "<b>Введите текст для рассылки:</b>\n"
    text += "<i>Поддерживается HTML разметка</i>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)
    
    return BROADCAST_INPUT_TEXT

async def broadcast_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки с фото"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_count = get_user_count()
    
    text = f"<b>🖼 Рассылка с фото</b>\n\n"
    text += f"<b>👥 Будет отправлено:</b> <code>{user_count}</code> пользователям\n\n"
    text += "<b>Отправьте фото для рассылки:</b>\n"
    text += "<i>Можно отправить как файл или фотографию</i>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)
    
    return BROADCAST_INPUT_PHOTO

async def broadcast_input_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного текста для рассылки"""
    text = update.message.text
    context.user_data['broadcast_text'] = text
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать рассылку", callback_data="start_broadcast_text")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    preview_text = f"<b>📝 Предпросмотр рассылки</b>\n\n"
    preview_text += f"<b>👥 Кому:</b> <code>{user_count}</code> пользователям\n\n"
    preview_text += f"<b>📄 Текст:</b>\n{text}\n\n"
    preview_text += f"<b>📏 Длина текста:</b> <code>{len(text)}</code> символов\n\n"
    preview_text += "<b>Начать рассылку?</b>"
    
    await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    
    return BROADCAST_CONFIRM

async def broadcast_input_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученного фото для рассылки"""
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        context.user_data['broadcast_photo'] = photo_file.file_id
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        photo_file = await update.message.document.get_file()
        context.user_data['broadcast_photo'] = photo_file.file_id
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте изображение!")
        return BROADCAST_INPUT_PHOTO
    
    keyboard = [
        [InlineKeyboardButton("➡️ Далее: ввод текста", callback_data="input_photo_caption")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Фото получено! Теперь введите текст для рассылки:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return BROADCAST_INPUT_TEXT

async def broadcast_input_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод текста для фото-рассылки"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "📝 Введите текст для рассылки с фото:", reply_markup=reply_markup)
    
    return BROADCAST_INPUT_TEXT

async def broadcast_confirm_photo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение фото-рассылки с текстом"""
    text = update.message.text
    context.user_data['broadcast_text'] = text
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать рассылку", callback_data="start_broadcast_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    preview_text = f"<b>🖼 Предпросмотр рассылки с фото</b>\n\n"
    preview_text += f"<b>👥 Кому:</b> <code>{user_count}</code> пользователям\n\n"
    preview_text += f"<b>📄 Текст:</b>\n{text}\n\n"
    preview_text += f"<b>📏 Длина текста:</b> <code>{len(text)}</code> символов\n\n"
    preview_text += "<b>Начать рассылку?</b>"
    
    await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    
    return BROADCAST_CONFIRM

async def start_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск текстовой рассылки"""
    query = update.callback_query
    await query.answer()
    
    text = context.user_data.get('broadcast_text', '')
    
    if not text:
        await safe_edit_message(query, "❌ Текст для рассылки не найден!")
        return ConversationHandler.END
    
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        await safe_edit_message(query, "❌ Нет пользователей для рассылки!")
        return ConversationHandler.END
    
    # Отправляем начальное сообщение
    progress_msg = await query.message.reply_text(
        f"🔄 <b>Начинаю рассылку...</b>\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Отправлено: <code>0</code>\n"
        f"❌ Ошибок: <code>0</code>\n"
        f"📊 Прогресс: <code>0%</code>",
        parse_mode='HTML'
    )
    
    success = 0
    failed = 0
    start_time = datetime.now()
    
    # Рассылка с ограничением скорости
    for i, user in enumerate(users, 1):
        user_id = user[0]
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML'
            )
            success += 1
            
            # Обновляем прогресс каждые 10 сообщений или каждые 5%
            if i % 10 == 0 or i == total_users:
                progress = int((i / total_users) * 100)
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code> ({i}/{total_users})\n"
                    f"⚡ Скорость: <code>{speed:.1f}</code> сообщ./сек",
                    parse_mode='HTML'
                )
            
            # Небольшая задержка для избежания ограничений Telegram
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            
            # Обновляем прогресс при ошибках
            if failed % 5 == 0:
                progress = int((i / total_users) * 100)
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code>",
                    parse_mode='HTML'
                )
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    # Финальное сообщение
    await progress_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Успешно отправлено: <code>{success}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>\n"
        f"📊 Охват: <code>{(success/total_users*100):.1f}%</code>\n"
        f"⏱ Время: <code>{total_time:.1f}</code> секунд\n"
        f"⚡ Средняя скорость: <code>{(total_users/total_time):.1f}</code> сообщ./сек",
        parse_mode='HTML'
    )
    
    # Очищаем данные
    context.user_data.pop('broadcast_text', None)
    
    keyboard = [
        [InlineKeyboardButton("📢 Новая рассылка", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "✅ Рассылка завершена!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def start_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск рассылки с фото"""
    query = update.callback_query
    await query.answer()
    
    photo_id = context.user_data.get('broadcast_photo')
    text = context.user_data.get('broadcast_text', '')
    
    if not photo_id or not text:
        await safe_edit_message(query, "❌ Данные для рассылки неполные!")
        return ConversationHandler.END
    
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        await safe_edit_message(query, "❌ Нет пользователей для рассылки!")
        return ConversationHandler.END
    
    # Отправляем начальное сообщение
    progress_msg = await query.message.reply_text(
        f"🔄 <b>Начинаю рассылку с фото...</b>\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Отправлено: <code>0</code>\n"
        f"❌ Ошибок: <code>0</code>\n"
        f"📊 Прогресс: <code>0%</code>",
        parse_mode='HTML'
    )
    
    success = 0
    failed = 0
    start_time = datetime.now()
    
    # Рассылка с ограничением скорости
    for i, user in enumerate(users, 1):
        user_id = user[0]
        
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                parse_mode='HTML'
            )
            success += 1
            
            # Обновляем прогресс каждые 10 сообщений или каждые 5%
            if i % 10 == 0 or i == total_users:
                progress = int((i / total_users) * 100)
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code> ({i}/{total_users})\n"
                    f"⚡ Скорость: <code>{speed:.1f}</code> сообщ./сек",
                    parse_mode='HTML'
                )
            
            # Большая задержка для фото (Telegram более строгий к фото)
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки фото пользователю {user_id}: {e}")
            
            # Обновляем прогресс при ошибках
            if failed % 5 == 0:
                progress = int((i / total_users) * 100)
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code>",
                    parse_mode='HTML'
                )
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    # Финальное сообщение
    await progress_msg.edit_text(
        f"✅ <b>Рассылка с фото завершена!</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Успешно отправлено: <code>{success}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>\n"
        f"📊 Охват: <code>{(success/total_users*100):.1f}%</code>\n"
        f"⏱ Время: <code>{total_time:.1f}</code> секунд\n"
        f"⚡ Средняя скорость: <code>{(total_users/total_time):.1f}</code> сообщ./сек",
        parse_mode='HTML'
    )
    
    # Очищаем данные
    context.user_data.pop('broadcast_photo', None)
    context.user_data.pop('broadcast_text', None)
    
    keyboard = [
        [InlineKeyboardButton("📢 Новая рассылка", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "✅ Рассылка с фото завершена!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена рассылки"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем данные
    context.user_data.pop('broadcast_text', None)
    context.user_data.pop('broadcast_photo', None)
    
    await broadcast_menu(update, context)
    return ConversationHandler.END

# ========== АДМИН ПАНЕЛЬ С ПЛАВНЫМИ ПЕРЕХОДАМИ ==========

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная панель администратора"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ У вас нет доступа к админ панели!")
        return
    
    keyboard = []
    
    if has_permission(user_id, 'add_script'):
        keyboard.append([InlineKeyboardButton("➕ Добавить скрипт", callback_data="add_script")])
    if has_permission(user_id, 'delete_script'):
        keyboard.append([InlineKeyboardButton("➖ Удалить скрипт", callback_data="delete_script")])
    if has_permission(user_id, 'add_channel'):
        keyboard.append([InlineKeyboardButton("➕ Добавить ОП", callback_data="add_channel")])
    if has_permission(user_id, 'remove_channel'):
        keyboard.append([InlineKeyboardButton("✔ Удалить ОП", callback_data="remove_channel")])
    if has_permission(user_id, 'list_channels'):
        keyboard.append([InlineKeyboardButton("🗒 Список ОП", callback_data="list_channels")])
    if has_permission(user_id, 'add_admin'):
        keyboard.append([InlineKeyboardButton("➕ Добавить Админа", callback_data="add_admin")])
    if has_permission(user_id, 'remove_admin'):
        keyboard.append([InlineKeyboardButton("➖ Снять Админа", callback_data="remove_admin")])
    if has_permission(user_id, 'list_admins'):
        keyboard.append([InlineKeyboardButton("📋 Список Админов", callback_data="list_admins")])
    if has_permission(user_id, 'view_stats'):
        keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="view_stats")])
    if has_permission(user_id, 'broadcast'):
        keyboard.append([InlineKeyboardButton("📢 Рассылка", callback_data="broadcast_menu")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>👑 Админ панель</b>", reply_markup=reply_markup)

async def add_script_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления скрипта"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_script'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления скриптов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📩 Отправьте содержимое скрипта:</b>", reply_markup=reply_markup)
    
    return ADD_SCRIPT

async def add_script_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления скрипта"""
    script_content = update.message.text
    user_id = update.message.from_user.id
    
    token = generate_token()
    
    save_script_to_file(token, script_content, user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_username = context.bot.username
    await update.message.reply_text(
        f"<b>✅ Скрипт добавлен!</b>\n\n"
        f"<b>Token:</b> <code>{token}</code>\n"
        f"<b>Ссылка:</b> <code>https://t.me/{bot_username}?start={token}</code>\n"
        f"<b>Сохранен в:</b> <code>scripts/{token}.json</code>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def delete_script_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления скрипта - запрос токена"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'delete_script'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления скриптов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("📋 Показать все скрипты", callback_data="show_all_scripts")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Введите токен скрипта для удаления:</b>", reply_markup=reply_markup)
    
    return DELETE_SCRIPT_INPUT

async def delete_script_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного токена для удаления"""
    token = update.message.text.strip().upper()
    
    script_data = load_script_from_file(token)
    
    if not script_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="delete_script")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Скрипт с токеном {token} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if delete_script_file(token):
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ <b>Скрипт с токеном {token} успешно удален!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="delete_script")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Ошибка при удалении скрипта с токеном {token}!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return ConversationHandler.END

async def show_all_scripts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все скрипты для удаления"""
    query = update.callback_query
    await query.answer()
    
    scripts = get_all_scripts()
    
    if not scripts:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(query, "<b>❌ Нет доступных скриптов!</b>", reply_markup=reply_markup)
        return
    
    text = "<b>📋 Все скрипты:</b>\n\n"
    for i, (token, content, views) in enumerate(scripts, 1):
        preview = content[:30] + "..." if len(content) > 30 else content
        text += f"{i}. <code>{token}</code> | 👁 {views} | {preview}\n"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Ввести токен для удаления", callback_data="delete_script")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления канала - шаг 1: ввод ID"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_channel'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления каналов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📢 Введите ID канала (например: -1001234567890):</b>", reply_markup=reply_markup)
    
    return ADD_CHANNEL_ID

async def add_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: ввод ссылки на канал"""
    channel_id = update.message.text.strip()
    
    # Удаляем сообщение пользователя
    try:
        await update.message.delete()
    except:
        pass
    
    context.user_data['channel_id'] = channel_id
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>🔗 Введите ссылку на канал:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_CHANNEL_LINK

async def add_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления канала"""
    channel_link = update.message.text.strip()
    user_id = update.message.from_user.id
    channel_id = context.user_data.get('channel_id')
    
    try:
        if channel_link.startswith('https://t.me/'):
            username = '@' + channel_link.split('/')[-1]
        elif channel_link.startswith('@'):
            username = channel_link
        else:
            username = '@' + channel_link
        
        real_subscribers = await get_real_channel_subscribers(context.bot, channel_id)
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось найти канал: {e}\n"
            "Убедитесь, что бот добавлен в канал как администратор!"
        )
        return ConversationHandler.END
    
    channel_data = {
        'channel_id': channel_id,
        'username': username,
        'invite_link': f"https://t.me/{username[1:]}",
        'initial_subscribers': real_subscribers,
        'current_subscribers': real_subscribers,
        'real_subscribers': real_subscribers,
        'added_by': user_id,
        'added_date': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    
    save_channel_to_file(channel_data)
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>✅ ОП канал добавлен!</b>\n\n"
        f"<b>ID:</b> <code>{channel_id}</code>\n"
        f"<b>Ссылка:</b> <code>{username}</code>\n"
        f"<b>Текущее кол-во подписчиков:</b> <code>{real_subscribers}</code>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    context.user_data.pop('channel_id', None)
    
    return ConversationHandler.END

async def remove_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор канала для удаления"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'remove_channel'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления каналов!")
        return
    
    channels = get_all_channels()
    
    if not channels:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(query, "<b>❌ Нет добавленных каналов!</b>", reply_markup=reply_markup)
        return
    
    keyboard = []
    for channel_id, username, initial_subs, current_subs, real_subs in channels:
        display_subs = real_subs if real_subs > 0 else current_subs
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {username} | 👥 {display_subs} подписчиков",
                callback_data=f"rmch_{channel_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Выберите канал для удаления:</b>", reply_markup=reply_markup)

async def remove_channel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление канала"""
    query = update.callback_query
    await query.answer()
    
    channel_id = query.data.replace("rmch_", "")
    
    if delete_channel_file(channel_id):
        await safe_edit_message(query, f"<b>✅ Канал удален!</b>")
    else:
        await safe_edit_message(query, f"<b>❌ Ошибка при удалении канала!</b>")
    
    await admin_panel(update, context)

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение списка каналов"""
    query = update.callback_query
    await query.answer()
    
    await update_all_channels_subscribers(context.bot)
    
    channels = get_all_channels()
    
    if not channels:
        text = "<b>🗒 Список каналов пуст!</b>"
    else:
        text = "<b>🗒 Список каналов:</b>\n\n"
        for i, (channel_id, username, initial_subs, current_subs, real_subs) in enumerate(channels, 1):
            display_subs = real_subs if real_subs > 0 else current_subs
            growth = display_subs - initial_subs
            growth_sign = "+" if growth >= 0 else ""
            text += f"{i}. {username}\n   ID: <code>{channel_id}</code>\n   Подписчиков: {display_subs}\n   Прирост: {growth_sign}{growth}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления администратора"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_admin'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления администраторов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>👤 Введите ID пользователя:</b>", reply_markup=reply_markup)
    
    return ADD_ADMIN

async def add_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор прав для нового администратора"""
    try:
        new_admin_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!", parse_mode='HTML')
        return ConversationHandler.END
    
    if is_admin(new_admin_id):
        await update.message.reply_text("❌ Этот пользователь уже администратор!", parse_mode='HTML')
        return ConversationHandler.END
    
    context.user_data['new_admin_id'] = new_admin_id
    context.user_data['admin_permissions'] = ['view_stats']
    
    keyboard = []
    for perm_key, perm_name in PERMISSIONS.items():
        if perm_key == 'view_stats':
            keyboard.append([InlineKeyboardButton(f"✅ {perm_name}", callback_data=f"perm_{perm_key}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {perm_name}", callback_data=f"perm_{perm_key}")])
    
    keyboard.append([InlineKeyboardButton("💾 Сохранить", callback_data="save_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>🔧 Настройка прав для ID {new_admin_id}:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return SET_ADMIN_RIGHTS

async def toggle_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение прав администратора"""
    query = update.callback_query
    await query.answer()
    
    perm_key = query.data.replace("perm_", "")
    new_admin_id = context.user_data.get('new_admin_id', 'N/A')
    
    if 'admin_permissions' not in context.user_data:
        context.user_data['admin_permissions'] = ['view_stats']
    
    current_perms = context.user_data['admin_permissions']
    
    if perm_key in current_perms:
        if perm_key != 'view_stats':
            current_perms.remove(perm_key)
    else:
        current_perms.append(perm_key)
    
    keyboard = []
    for p_key, p_name in PERMISSIONS.items():
        status = "✅" if p_key in current_perms else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {p_name}", callback_data=f"perm_{p_key}")])
    
    keyboard.append([InlineKeyboardButton("💾 Сохранить", callback_data="save_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, f"<b>🔧 Настройка прав для ID {new_admin_id}:</b>", reply_markup=reply_markup)

async def save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового администратора"""
    query = update.callback_query
    await query.answer()
    
    new_admin_id = context.user_data.get('new_admin_id')
    permissions = context.user_data.get('admin_permissions', ['view_stats'])
    
    if not new_admin_id:
        await safe_edit_message(query, "❌ Ошибка: ID не найден!")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO admins (user_id, permissions, added_by) VALUES (?, ?, ?)',
            (new_admin_id, ','.join(permissions), query.from_user.id)
        )
        conn.commit()
    
    admin_cache[new_admin_id] = True
    
    context.user_data.pop('new_admin_id', None)
    context.user_data.pop('admin_permissions', None)
    
    await safe_edit_message(query, f"<b>✅ Администратор {new_admin_id} добавлен!</b>\n<b>Права:</b> {', '.join(permissions)}")
    await admin_panel(update, context)
    return ConversationHandler.END

async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор администратора для удаления"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'remove_admin'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления администраторов!")
        return
    
    admins = get_all_admins()
    user_id = query.from_user.id
    
    keyboard = []
    for admin_id, permissions in admins:
        if admin_id != user_id and admin_id not in ADMIN_IDS:
            perm_count = "Все" if permissions == 'all' else str(len(permissions.split(',')))
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 ID:{admin_id} | {perm_count} прав",
                    callback_data=f"rmadm_{admin_id}"
                )
            ])
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await safe_edit_message(query, "<b>❌ Нет администраторов для удаления!</b>", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Выберите администратора:</b>", reply_markup=reply_markup)

async def remove_admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление администратора"""
    query = update.callback_query
    await query.answer()
    
    admin_id = int(query.data.replace("rmadm_", ""))
    
    if admin_id in ADMIN_IDS:
        await safe_edit_message(query, "<b>❌ Нельзя удалить главного администратора!</b>")
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
    
    admin_cache.pop(admin_id, None)
    
    await safe_edit_message(query, f"<b>✅ Администратор {admin_id} удален!</b>")
    await admin_panel(update, context)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение списка администраторов"""
    query = update.callback_query
    await query.answer()
    
    admins = get_all_admins()
    
    main_admins = []
    other_admins = []
    
    for admin_id, permissions in admins:
        if permissions == 'all':
            main_admins.append(admin_id)
        else:
            other_admins.append(admin_id)
    
    text = "<b>📋 Список администраторов</b>\n\n"
    
    if main_admins:
        text += "<b>Главные админы</b>\n"
        for admin_id in main_admins:
            text += f"• {admin_id}\n"
        text += "\n"
    
    if other_admins:
        text += "<b>Доп. Администраторы</b>\n"
        for admin_id in other_admins:
            text += f"• {admin_id}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню статистики"""
    query = update.callback_query
    await query.answer()
    
    text = "<b>📊 Статистика</b>"
    
    keyboard = [
        [InlineKeyboardButton("📢 Каналы", callback_data="stats_channels")],
        [InlineKeyboardButton("📦 Скрипты", callback_data="stats_scripts")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def stats_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика каналов - запрос ID"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📢 Введите ID канала для просмотра статистики:</b>", reply_markup=reply_markup)
    
    return VIEW_CHANNEL_STATS

async def stats_channels_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ID канала для статистики"""
    channel_id = update.message.text.strip()
    
    channel_data = load_channel_from_file(channel_id)
    
    if not channel_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="stats_channels")],
            [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Канал с ID {channel_id} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    try:
        real_subscribers = await get_real_channel_subscribers(context.bot, channel_id)
        channel_data['real_subscribers'] = real_subscribers
        channel_data['current_subscribers'] = real_subscribers
        save_channel_to_file(channel_data)
    except:
        real_subscribers = channel_data.get('real_subscribers', 0)
    
    initial_subs = channel_data.get('initial_subscribers', 0)
    growth = real_subscribers - initial_subs
    growth_sign = "+" if growth >= 0 else ""
    
    text = f"""<b>📊 Статистика канала</b>

<b>ID:</b> <code>{channel_data['channel_id']}</code>
<b>Ссылка:</b> {channel_data['username']}
<b>Пригласительная ссылка:</b> {channel_data.get('invite_link', 'Нет')}

<b>📈 Статистика подписчиков:</b>
• Начальное количество: {initial_subs}
• Текущее количество: {real_subscribers}
• Прирост: {growth_sign}{growth}

<b>📅 Информация:</b>
• Добавлен: {channel_data.get('added_date', 'Неизвестно')}
• Добавил: {channel_data.get('added_by', 'Неизвестно')}
• Последнее обновление: {channel_data.get('last_updated', 'Никогда')}"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return ConversationHandler.END

async def stats_scripts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика скриптов - запрос токена"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📦 Введите токен скрипта для просмотра статистики:</b>", reply_markup=reply_markup)
    
    return VIEW_SCRIPT_STATS

async def stats_scripts_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода токена скрипта для статистики"""
    token = update.message.text.strip().upper()
    
    script_data = load_script_from_file(token)
    
    if not script_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="stats_scripts")],
            [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Скрипт с токеном {token} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    views = script_data.get('views', 0)
    created_date = script_data.get('created_date', 'Неизвестно')
    created_by = script_data.get('created_by', 'Неизвестно')
    
    try:
        created_date_obj = datetime.fromisoformat(created_date)
        created_date_formatted = created_date_obj.strftime("%d.%m.%Y %H:%M")
    except:
        created_date_formatted = created_date
    
    text = f"""<b>📊 Статистика скрипта</b>

<b>Токен:</b> <code>{token}</code>
<b>👁 Количество переходов:</b> <b>{views}</b>

<b>📅 Информация:</b>
• Создан: {created_date_formatted}
• Создал: {created_by}

<b>🔗 Ссылка для доступа:</b>
<code>https://t.me/{context.bot.username}?start={token}</code>"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Центральный обработчик callback-запросов"""
    start_time = datetime.now()
    query = update.callback_query
    data = query.data
    
    handlers = {
        "admin_panel": admin_panel,
        "list_channels": list_channels,
        "list_admins": list_admins,
        "view_stats": view_stats,
        "stats_channels": stats_channels,
        "stats_scripts": stats_scripts,
        "show_all_scripts": show_all_scripts,
        "broadcast_menu": broadcast_menu,
        "users_stats": users_stats,
        "back_to_start": start,
    }
    
    if data in handlers:
        await handlers[data](update, context)
    elif data.startswith("check_sub_"):
        await check_subscription(update, context)
    elif data.startswith("rmch_"):
        await remove_channel_confirm(update, context)
    elif data.startswith("rmadm_"):
        await remove_admin_confirm(update, context)
    elif data == "add_script":
        await add_script_start(update, context)
    elif data == "delete_script":
        await delete_script_start(update, context)
    elif data == "add_channel":
        await add_channel_start(update, context)
    elif data == "remove_channel":
        await remove_channel_start(update, context)
    elif data == "add_admin":
        await add_admin_start(update, context)
    elif data == "remove_admin":
        await remove_admin_start(update, context)
    elif data == "save_admin":
        await save_admin(update, context)
    elif data.startswith("perm_"):
        await toggle_permission(update, context)
    elif data in ["broadcast_text", "broadcast_photo"]:
        if data == "broadcast_text":
            await broadcast_text_start(update, context)
        else:
            await broadcast_photo_start(update, context)
    elif data == "input_photo_caption":
        await broadcast_input_photo_caption(update, context)
    elif data in ["start_broadcast_text", "start_broadcast_photo"]:
        if data == "start_broadcast_text":
            await start_broadcast_text(update, context)
        else:
            await start_broadcast_photo(update, context)
    
    execution_time = (datetime.now() - start_time).total_seconds()
    if execution_time > 0.1:
        logger.warning(f"Время выполнения {data}: {execution_time:.3f} сек")
    else:
        logger.info(f"Время выполнения {data}: {execution_time:.3f} сек")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    await admin_panel(update, context)
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    if isinstance(context.error, Conflict):
        logger.error("⚠️ Обнаружен конфликт: другой экземпляр бота уже запущен!")
        logger.error("🛑 Остановите все другие экземпляры бота и перезапустите этот")

def main():
    """Главная функция запуска бота"""
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_error_handler(error_handler)
    
    application.add_handler(CommandHandler("start", start))
    
    # Добавляем рассылку текста
    broadcast_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_text_start, pattern="^broadcast_text$")],
        states={
            BROADCAST_INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_input_text)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(start_broadcast_text, pattern="^start_broadcast_text$"),
                               CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")],
        per_message=False
    )
    
    # Добавляем рассылку фото
    broadcast_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_photo_start, pattern="^broadcast_photo$")],
        states={
            BROADCAST_INPUT_PHOTO: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, broadcast_input_photo)],
            BROADCAST_INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_confirm_photo_text)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(start_broadcast_photo, pattern="^start_broadcast_photo$"),
                               CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")]
        },
        fallbacks=[
            CallbackQueryHandler(broadcast_input_photo_caption, pattern="^input_photo_caption$"),
            CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")
        ],
        per_message=False
    )
    
    add_script_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_script_start, pattern="^add_script$")],
        states={
            ADD_SCRIPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_script_finish)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel)$")],
        per_message=False
    )
    
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_start, pattern="^add_channel$")],
        states={
            ADD_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_id)],
            ADD_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_finish)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel)$")],
        per_message=False
    )
    
    add_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_admin_start, pattern="^add_admin$")],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_finish)],
            SET_ADMIN_RIGHTS: [CallbackQueryHandler(toggle_permission, pattern="^perm_")]
        },
        fallbacks=[
            CallbackQueryHandler(save_admin, pattern="^save_admin$"),
            CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel)$")
        ],
        per_message=False
    )
    
    delete_script_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_script_start, pattern="^delete_script$")],
        states={
            DELETE_SCRIPT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_script_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel)$"),
            CallbackQueryHandler(show_all_scripts, pattern="^show_all_scripts$")
        ],
        per_message=False
    )
    
    stats_channels_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(stats_channels, pattern="^stats_channels$")],
        states={
            VIEW_CHANNEL_STATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_channels_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel|view_stats)$")
        ],
        per_message=False
    )
    
    stats_scripts_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(stats_scripts, pattern="^stats_scripts$")],
        states={
            VIEW_SCRIPT_STATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_scripts_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^(back_to_start|admin_panel|view_stats)$")
        ],
        per_message=False
    )
    
    # Регистрируем все обработчики
    application.add_handler(broadcast_text_conv)
    application.add_handler(broadcast_photo_conv)
    application.add_handler(add_script_conv)
    application.add_handler(add_channel_conv)
    application.add_handler(add_admin_conv)
    application.add_handler(delete_script_conv)
    application.add_handler(stats_channels_conv)
    application.add_handler(stats_scripts_conv)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info(f"📁 Скрипты сохраняются в: {SCRIPTS_DIR}")
    logger.info(f"📁 Каналы сохраняются в: {CHANNELS_DIR}")
    logger.info(f"📸 Изображение приветствия: {WELCOME_IMAGE_PATH}")
    logger.info(f"👥 База пользователей для рассылки: {DB_PATH}")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Conflict:
        logger.error("❌ Конфликт: другой экземпляр бота уже запущен!")
        logger.error("💡 Остановите все другие экземпляры и перезапустите бота")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == '__main__':
    main()
