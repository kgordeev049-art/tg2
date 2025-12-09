import logging
import random
import string
import asyncio
from datetime import datetime, timedelta
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
LINKS_DIR = os.path.join(BASE_DIR, "links")
WELCOME_IMAGE_PATH = os.path.join(BASE_DIR, "dobro.jpg")

# Состояния для разных функций
(ADD_SCRIPT_GAME, ADD_SCRIPT_NAME, ADD_SCRIPT_PHOTO, ADD_SCRIPT_CONTENT, 
 ADD_SCRIPT_KEY, ADD_SCRIPT_CONFIRM, ADD_CHANNEL_ID, ADD_CHANNEL_LINK, 
 ADD_ADMIN, SET_ADMIN_RIGHTS, DELETE_SCRIPT_INPUT, VIEW_CHANNEL_STATS, 
 VIEW_SCRIPT_STATS, CREATE_LINK_CONTENT, CREATE_LINK_BUTTON, SEARCH_SCRIPTS) = range(16)

# Состояния для рассылки
(BROADCAST_SELECT_TYPE, BROADCAST_INPUT_TEXT, BROADCAST_INPUT_PHOTO, 
 BROADCAST_CONFIRM, BROADCAST_IN_PROGRESS) = range(5)

def create_directories():
    dirs_to_create = [
        SCRIPTS_DIR,
        CHANNELS_DIR,
        LINKS_DIR
    ]
    
    for directory in dirs_to_create:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Создана директория: {directory}")

create_directories()

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
    'broadcast': '📢 Рассылка',
    'create_link': '🔗 Создание ссылки'
}

script_cache = {}
channel_cache = {}
admin_cache = {}
users_cache = {}
link_cache = {}
subscription_timers = {}

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ========== ФУНКЦИИ ДЛЯ СКРИПТОВ ==========
def save_script_to_file(token: str, script_data: dict):
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
        save_script_to_file(token, script_data)

# ========== ФУНКЦИИ ДЛЯ КАНАЛОВ ==========
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

# ========== ФУНКЦИИ ДЛЯ ССЫЛОК ==========
def save_link_to_file(token: str, link_data: dict):
    file_path = os.path.join(LINKS_DIR, f"{token}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(link_data, f, ensure_ascii=False, indent=2)
    
    link_cache[token] = link_data

def load_link_from_file(token: str) -> Optional[dict]:
    if token in link_cache:
        return link_cache[token]
    
    file_path = os.path.join(LINKS_DIR, f"{token}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                link_data = json.load(f)
                link_cache[token] = link_data
                return link_data
        except Exception as e:
            logger.error(f"Ошибка загрузки ссылки {token}: {e}")
    return None

def get_all_links_from_files() -> List[dict]:
    links = []
    for filename in os.listdir(LINKS_DIR):
        if filename.endswith('.json'):
            token = filename[:-5]
            link_data = load_link_from_file(token)
            if link_data:
                links.append(link_data)
    return links

def delete_link_file(token: str):
    file_path = os.path.join(LINKS_DIR, f"{token}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        link_cache.pop(token, None)
        return True
    return False

def update_link_views_in_file(token: str):
    link_data = load_link_from_file(token)
    if link_data:
        link_data['views'] = link_data.get('views', 0) + 1
        save_link_to_file(token, link_data)

# ========== ОБЩИЕ ФУНКЦИИ ==========
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

def generate_token(length: int = 8) -> str:
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
    return [(s['token'], s.get('game_name', ''), s.get('script_name', ''), s['script_content'], s.get('views', 0)) for s in scripts_data]

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
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name))
        conn.commit()

def get_all_users() -> List[tuple]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name FROM users')
        return cursor.fetchall()

def get_user_count() -> int:
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

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = datetime.now()
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        user_id = update.effective_user.id
        is_callback = False
    
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
        link_data = load_link_from_file(token)
        if link_data:
            await handle_link_access(update, context, token)
        else:
            script_data = load_script_from_file(token)
            if script_data:
                await handle_script_access(update, context, token)
            else:
                text = "❌ Ссылка не найдена!"
                if update.message:
                    await update.message.reply_text(text, parse_mode='HTML')
                else:
                    await update.callback_query.edit_message_text(text, parse_mode='HTML')
        return
    
    keyboard = [
        [InlineKeyboardButton("🔗 Начать байпасс ссылок", callback_data="bypass_start")],
        [InlineKeyboardButton("📦 Каталог скриптов", callback_data="catalog")],
        [InlineKeyboardButton("🔎 Поиск скриптов", callback_data="search_scripts")],
        [InlineKeyboardButton("⚙️ Сервисы для байп", callback_data="services")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")]
    ]
    
    keyboard.append([InlineKeyboardButton("🚀 Главный канал", url="https://t.me/robloxscriptrbx")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """<b>👋 Добро пожаловать в BAFScripts_bot!</b>

🔗 <b>Нужен простой способ обхода ссылок?</b>
Наш бот поддерживает популярные сервисы, чтобы быстро получать доступ к контенту.

📦 <b>Также доступен поиск скриптов по категориям!</b>

🚀 <b>Начните прямо сейчас: используйте меню ниже.</b>"""
    
    if is_callback:
        try:
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await query.edit_message_media(
                        media=InputFile(photo),
                        caption=welcome_text,
                        parse_mode='HTML'
                    )
                    await query.edit_message_reply_markup(reply_markup=reply_markup)
            else:
                await query.edit_message_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение: {e}")
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await query.message.reply_photo(
                        photo=InputFile(photo),
                        caption=welcome_text,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
            else:
                await query.message.reply_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    else:
        try:
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=InputFile(photo),
                        caption=welcome_text,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
            else:
                await update.message.reply_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Ошибка при отправке приветствия: {e}")
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    execution_time = (datetime.now() - start_time).total_seconds()
    if execution_time > 0.1:
        logger.warning(f"Время выполнения start: {execution_time:.3f} сек")
    else:
        logger.info(f"Время выполнения start: {execution_time:.3f} сек")

async def panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /PanelAdmin"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к админ панели!")
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
    if has_permission(user_id, 'create_link'):
        keyboard.append([InlineKeyboardButton("🔗 Создание ссылки", callback_data="create_link")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>👑 Панель администратора BAFScripts</b>\n\n"
        "Здесь вы можете управлять ботом, добавлять скрипты, настраивать каналы и многое другое.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# ========== КАТАЛОГ СКРИПТОВ ==========
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Каталог скриптов"""
    query = update.callback_query
    await query.answer()
    
    # Получаем все скрипты
    scripts = get_all_scripts()
    
    if not scripts:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "<b>📭 Каталог скриптов пуст</b>\n\n"
            "Скриптов пока нет в базе данных.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    # Создаем словарь для группировки по играм
    games_dict = {}
    for token, game_name, script_name, content, views in scripts:
        if game_name not in games_dict:
            games_dict[game_name] = []
        games_dict[game_name].append((token, script_name, views))
    
    # Создаем клавиатуру с категориями
    keyboard = []
    for game_name in sorted(games_dict.keys()):
        if game_name:
            keyboard.append([
                InlineKeyboardButton(f"📁 {game_name}", callback_data=f"category_{game_name}")
            ])
    
    # Добавляем скрипты без категории
    if '' in games_dict or 'Без категории' in games_dict:
        keyboard.append([
            InlineKeyboardButton("📁 Без категории", callback_data="category_Без категории")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "<b>📂 Категории</b>\n\n"
        "Выберите раздел:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать скрипты в категории"""
    query = update.callback_query
    await query.answer()
    
    category_name = query.data.replace("category_", "")
    
    # Получаем все скрипты
    scripts = get_all_scripts()
    
    # Фильтруем скрипты по категории
    if category_name == "Без категории":
        category_scripts = [(t, g, n, c, v) for t, g, n, c, v in scripts if not g or g == '']
    else:
        category_scripts = [(t, g, n, c, v) for t, g, n, c, v in scripts if g == category_name]
    
    if not category_scripts:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад в каталог", callback_data="catalog")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"<b>📭 В категории '{category_name}' нет скриптов</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    # Создаем клавиатуру со скриптами в сетке 2x2
    keyboard = []
    row = []
    
    for i, (token, game_name, script_name, content, views) in enumerate(category_scripts, 1):
        display_name = script_name or token
        if len(display_name) > 15:
            display_name = display_name[:15] + "..."
        
        button = InlineKeyboardButton(f"🧩{display_name}", callback_data=f"script_{token}")
        row.append(button)
        
        if i % 2 == 0 or i == len(category_scripts):
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в каталог", callback_data="catalog")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"<b>📂 {category_name}</b>\n\n"
        f"Найдено скриптов: <b>{len(category_scripts)}</b>\n\n"
        "Выберите скрипт:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# ========== ОБРАБОТКА СКРИПТОВ ==========
async def handle_script_access(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Обработка доступа к скрипту"""
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
        if update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            user_id = update.effective_user.id
        
        subscribed_count, total_channels, not_subscribed_list = await check_user_subscription(user_id, context.bot)
        
        if subscribed_count >= total_channels:
            update_script_views(token)
            await send_script(update, script_data, token)
            return
        
        # Формируем текст с каналами для подписки
        text = f"<b>Подпишись на каналы, чтобы получить скрипт — бот проверит подписки автоматически</b>\n\n"
        
        for channel_id, username, _, _, _ in channels:
            if username in not_subscribed_list:
                text += f"<b>=></b> {username}\n"
        
        text += f"\nУ вас есть 60 секунд, чтобы подписаться на эти каналы"
        
        # Сохраняем время начала ожидания
        user_key = f"{user_id}_{token}"
        subscription_timers[user_key] = datetime.now()
        
        # Отправляем сообщение с таймером
        if update.message:
            timer_msg = await update.message.reply_text(
                text,
                parse_mode='HTML'
            )
        else:
            timer_msg = await update.callback_query.message.reply_text(
                text,
                parse_mode='HTML'
            )
        
        # Запускаем таймер
        context.job_queue.run_once(
            check_subscription_timer,
            60,
            data={
                'chat_id': update.effective_chat.id,
                'message_id': timer_msg.message_id,
                'user_id': user_id,
                'token': token
            }
        )
        
        # Кнопка для проверки подписки
        keyboard = [[InlineKeyboardButton("✅ Я подписался!", callback_data=f"check_sub_{token}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(
                "Подпишитесь для продолжения:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.callback_query.message.reply_text(
                "Подпишитесь для продолжения:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        update_script_views(token)
        await send_script(update, script_data, token)

async def check_subscription_timer(context):
    """Проверка таймера подписки"""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    message_id = job_data['message_id']
    user_id = job_data['user_id']
    token = job_data['token']
    
    user_key = f"{user_id}_{token}"
    
    # Проверяем, истекло ли время
    if user_key in subscription_timers:
        start_time = subscription_timers[user_key]
        if datetime.now() - start_time > timedelta(seconds=60):
            # Время истекло
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="<b>Время истекло...</b>",
                parse_mode='HTML'
            )
            subscription_timers.pop(user_key, None)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка подписки"""
    query = update.callback_query
    await query.answer("🔄 Проверяю подписки...")
    
    token = query.data.replace("check_sub_", "")
    user_id = query.from_user.id
    
    user_key = f"{user_id}_{token}"
    
    # Проверяем, не истекло ли время
    if user_key in subscription_timers:
        start_time = subscription_timers[user_key]
        if datetime.now() - start_time > timedelta(seconds=60):
            await query.edit_message_text("<b>Время истекло...</b>", parse_mode='HTML')
            subscription_timers.pop(user_key, None)
            return
    
    subscribed_count, total_channels, not_subscribed_list = await check_user_subscription(user_id, context.bot)
    
    if subscribed_count >= total_channels:
        script_data = load_script_from_file(token)
        
        if script_data:
            update_script_views(token)
            await send_script(query, script_data, token)
        else:
            await query.edit_message_text("❌ Скрипт не найден!", parse_mode='HTML')
    else:
        # Формируем текст с оставшимися каналами
        text = f"<b>Вы подписались не на все каналы ({subscribed_count} из {total_channels})</b>\n\n"
        
        channels = get_all_channels()
        for channel_id, username, _, _, _ in channels:
            if username in not_subscribed_list:
                text += f"<b>=></b> {username}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_sub_{token}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def send_script(update, script_data: dict, token: str):
    """Отправка скрипта"""
    script_content = script_data.get('script_content', '')
    game_name = script_data.get('game_name', '')
    script_name = script_data.get('script_name', '')
    has_key = script_data.get('has_key', False)
    
    # Экранируем HTML символы в скрипте
    escaped_content = script_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Формируем заголовок
    if game_name and script_name:
        title = f"<b>🎮 {game_name} - {script_name}</b>\n\n"
    elif script_name:
        title = f"<b>🎮 {script_name}</b>\n\n"
    else:
        title = f"<b>🎮 Скрипт {token}</b>\n\n"
    
    # Формируем сообщение для "поделиться"
    bot_username = None
    if hasattr(update, 'bot'):
        bot_username = update.bot.username
    elif hasattr(update, 'message') and update.message:
        bot_username = update.message.bot.username
    elif hasattr(update, 'callback_query'):
        bot_username = update.callback_query.message.bot.username
    
    share_url = f"https://t.me/{bot_username}?start={token}" if bot_username else f"Нажмите /start {token}"
    
    # Кнопки
    keyboard = [
        [InlineKeyboardButton("📤 Поделиться", switch_inline_query=f"script_{token}")],
        [InlineKeyboardButton("📦 В каталог", callback_data="catalog")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем полный скрипт
    script_message = f"{title}<code>{escaped_content}</code>\n\n🚀 <b>Удачи в игре!</b>"
    
    if hasattr(update, 'edit_message_text'):
        await update.edit_message_text(script_message, parse_mode='HTML')
        await update.message.reply_text(
            f"🔑 <b>Ключ:</b> <code>{token}</code>\n"
            f"🔗 <b>Ссылка для распространения:</b> <code>{share_url}</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    elif hasattr(update, 'message'):
        await update.message.reply_text(script_message, parse_mode='HTML')
        await update.message.reply_text(
            f"🔑 <b>Ключ:</b> <code>{token}</code>\n"
            f"🔗 <b>Ссылка для распространения:</b> <code>{share_url}</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await update.reply_text(script_message, parse_mode='HTML')
        await update.reply_text(
            f"🔑 <b>Ключ:</b> <code>{token}</code>\n"
            f"🔗 <b>Ссылка для распространения:</b> <code>{share_url}</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# ========== ДОБАВЛЕНИЕ СКРИПТА (НОВЫЙ ПРОЦЕСС) ==========
async def add_script_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления скрипта - шаг 1: название игры"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_script'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления скриптов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🎮 Введите название игры:</b>", reply_markup=reply_markup)
    
    return ADD_SCRIPT_GAME

async def add_script_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: название скрипта"""
    game_name = update.message.text.strip()
    context.user_data['game_name'] = game_name
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>📝 Введите название скрипта:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_SCRIPT_NAME

async def add_script_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: фотография скрипта"""
    script_name = update.message.text.strip()
    context.user_data['script_name'] = script_name
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>🖼 Отправьте фотографию вашего скрипта:</b>\n"
        "(если фотографии нет, отправьте любой текст)",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_SCRIPT_PHOTO

async def add_script_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: содержимое скрипта"""
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        context.user_data['photo_id'] = photo_file.file_id
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        photo_file = await update.message.document.get_file()
        context.user_data['photo_id'] = photo_file.file_id
    else:
        context.user_data['photo_id'] = None
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>📄 Отправьте сам скрипт:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_SCRIPT_CONTENT

async def add_script_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 5: выбор ключа"""
    script_content = update.message.text
    context.user_data['script_content'] = script_content
    
    keyboard = [
        [
            InlineKeyboardButton("🔑 С ключом", callback_data="key_yes"),
            InlineKeyboardButton("🚫 Без ключа", callback_data="key_no")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>🔑 Ваш скрипт с ключом или без?</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_SCRIPT_KEY

async def add_script_key_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 6: подтверждение"""
    query = update.callback_query
    await query.answer()
    
    has_key = query.data == "key_yes"
    context.user_data['has_key'] = has_key
    
    # Генерируем токен
    token = generate_token()
    context.user_data['token'] = token
    
    # Формируем превью поста
    game_name = context.user_data.get('game_name', '')
    script_name = context.user_data.get('script_name', '')
    script_content = context.user_data.get('script_content', '')
    has_key_text = "🔑 С ключом" if has_key else "🚫 Без ключа"
    
    preview_text = f"<b>🎮 {game_name}</b>\n"
    preview_text += f"<b>📝 {script_name}</b>\n\n"
    if len(script_content) > 100:
        preview_text += f"<code>{script_content[:100]}...</code>\n\n"
    else:
        preview_text += f"<code>{script_content}</code>\n\n"
    preview_text += f"<b>{has_key_text}</b>\n"
    preview_text += f"<b>🔑 Ключ:</b> <code>{token}</code>"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="confirm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, 
        f"<b>📋 Это верный пост скрипта?</b>\n\n{preview_text}",
        reply_markup=reply_markup
    )
    
    return ADD_SCRIPT_CONFIRM

async def add_script_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 7: завершение добавления скрипта"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_no":
        await safe_edit_message(query, "❌ Добавление скрипта отменено!")
        return ConversationHandler.END
    
    # Сохраняем скрипт
    token = context.user_data['token']
    script_data = {
        'token': token,
        'game_name': context.user_data.get('game_name', ''),
        'script_name': context.user_data.get('script_name', ''),
        'script_content': context.user_data.get('script_content', ''),
        'photo_id': context.user_data.get('photo_id'),
        'has_key': context.user_data.get('has_key', False),
        'created_by': query.from_user.id,
        'created_date': datetime.now().isoformat(),
        'views': 0
    }
    
    save_script_to_file(token, script_data)
    
    # Формируем ссылку для распространения
    bot_username = context.bot.username
    share_url = f"https://t.me/{bot_username}?start={token}"
    
    keyboard = [
        [InlineKeyboardButton("📤 Поделиться", switch_inline_query=f"script_{token}")],
        [InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query,
        f"<b>✅ Скрипт успешно добавлен!</b>\n\n"
        f"<b>🔗 Ссылка для распространения:</b>\n"
        f"<code>{share_url}</code>\n\n"
        f"<b>🔑 Ключ:</b> <code>{token}</code>",
        reply_markup=reply_markup
    )
    
    # Очищаем данные
    context.user_data.clear()
    
    return ConversationHandler.END

# ========== КОПИРОВАНИЕ ССЫЛКИ ==========
async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Копирование ссылки в буфер обмена"""
    query = update.callback_query
    await query.answer()
    
    token = query.data.replace("copy_", "")
    
    # Для Telegram Web App можно использовать copyTextToClipboard
    # Но в обычном боте просто отправляем ссылку
    bot_username = context.bot.username
    link_url = f"https://t.me/{bot_username}?start={token}"
    
    await query.message.reply_text(
        f"📋 <b>Ссылка скопирована!</b>\n\n"
        f"<code>{link_url}</code>\n\n"
        f"Отправьте эту ссылку, чтобы поделиться скриптом.",
        parse_mode='HTML'
    )

# ========== НАСТРОЙКИ ==========
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек"""
    query = update.callback_query
    await query.answer()
    
    text = "<b>⚙️ Настройки</b>\n\n"
    text += "Здесь будут появляться параметры пользователя.\n"
    text += "Пока ничего настраивать не нужно 😊"
    
    keyboard = [
        [InlineKeyboardButton("🛡️ Назад в меню", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup)

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мой профиль"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    # Получаем статистику пользователя
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT last_seen FROM users WHERE user_id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        last_seen = result['last_seen'] if result else "Неизвестно"
    
    text = f"<b>Пробиль</b>\n\n"
    text += f"<b>ID:</b> <code>{user_id}</code>\n"
    text += f"<b>Имя:</b> {user.first_name or 'Не указано'}\n"
    if user.last_name:
        text += f"<b>Фамилия:</b> {user.last_name}\n"
    text += f"<b>Username:</b> @{user.username or 'Не указан'}\n"
    text += f"<b>Последняя активность:</b> {last_seen}"
    
    if is_admin(user_id):
        text += "\n\n<b>🎖 Статус:</b> Администратор"
    
    keyboard = [
        [InlineKeyboardButton("📋 В меню", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup)

# ========== ОБРАБОТКА ССЫЛОК ==========
async def handle_link_access(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Обработка доступа по ссылке"""
    link_data = load_link_from_file(token)
    
    if not link_data:
        text = "❌ Ссылка не найдена или устарела!"
        if update.message:
            await update.message.reply_text(text, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, parse_mode='HTML')
        return
    
    # Увеличиваем счетчик просмотров
    update_link_views_in_file(token)
    
    # Отправляем контент в зависимости от типа
    content_type = link_data.get('content_type', 'text')
    content = link_data.get('content', '')
    caption = link_data.get('caption', '')
    button_text = link_data.get('button_text')
    button_url = link_data.get('button_url')
    
    # Создаем клавиатуру, если есть кнопка
    reply_markup = None
    if button_text and button_url:
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    chat_id = update.effective_chat.id
    
    try:
        if content_type == 'text':
            await context.bot.send_message(
                chat_id=chat_id,
                text=content,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        elif content_type == 'photo':
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=content,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        elif content_type == 'video':
            await context.bot.send_video(
                chat_id=chat_id,
                video=content,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        elif content_type == 'document':
            await context.bot.send_document(
                chat_id=chat_id,
                document=content,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка отправки контента ссылки {token}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при отправке контента.",
            parse_mode='HTML'
        )

# ========== ОБРАБОТЧИК CALLBACK ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    data = query.data
    
    handlers = {
        "admin_panel": admin_panel,
        "back_to_start": start,
        "bypass_start": bypass_start,
        "catalog": catalog,
        "search_scripts": search_scripts_start,
        "services": services_bypass,
        "settings": settings_menu,
        "my_profile": my_profile,
        "list_channels": list_channels,
        "list_admins": list_admins,
        "view_stats": view_stats,
        "stats_channels": stats_channels,
        "stats_scripts": stats_scripts,
        "show_all_scripts": show_all_scripts,
        "broadcast_menu": broadcast_menu,
        "users_stats": users_stats,
        "create_link": create_link_start,
    }
    
    if data in handlers:
        await handlers[data](update, context)
    elif data.startswith("check_sub_"):
        await check_subscription(update, context)
    elif data.startswith("script_"):
        token = data.replace("script_", "")
        await handle_script_access(update, context, token)
    elif data.startswith("copy_"):
        await copy_link(update, context)
    elif data.startswith("category_"):
        await show_category(update, context)
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
    elif data.startswith("key_"):
        await add_script_key_choice(update, context)
    elif data.startswith("confirm_"):
        await add_script_confirm(update, context)

# ========== ЗАПУСК БОТА ==========
def main():
    """Главная функция"""
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("PanelAdmin", panel_admin))
    
    # ConversationHandler для добавления скрипта
    add_script_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_script_start, pattern="^add_script$")],
        states={
            ADD_SCRIPT_GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_script_game)],
            ADD_SCRIPT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_script_name)],
            ADD_SCRIPT_PHOTO: [MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.TEXT, add_script_photo)],
            ADD_SCRIPT_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_script_content)],
            ADD_SCRIPT_KEY: [CallbackQueryHandler(add_script_key_choice, pattern="^key_")],
            ADD_SCRIPT_CONFIRM: [CallbackQueryHandler(add_script_confirm, pattern="^confirm_")]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^admin_panel$")],
        per_message=False
    )
    
    # Добавляем другие ConversationHandler...
    # (остальные ConversationHandler остаются без изменений)
    
    application.add_handler(add_script_conv)
    
    # Добавляем обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Бот BAFScripts запущен и готов к работе!")
    
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
