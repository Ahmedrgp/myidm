import asyncio

# ==========================================
# 0. إصلاح مشكلة Python 3.12+ / 3.14 على Render
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import os
import sys
import time
import math
import re
import logging
import tempfile
import sqlite3
import zipfile
import urllib.parse
from dotenv import load_dotenv
import aiohttp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, RPCError, MessageNotModified

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

try:
    from torrentp import TorrentDownloader
    TORRENTP_AVAILABLE = True
except ImportError:
    TORRENTP_AVAILABLE = False

load_dotenv()

# ==========================================
# 1. إعدادات OMNIPOTENT OVERLORD ENGINE ⚡🌌👑
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

MAX_SINGLE_FILE_SIZE = 2000 * 1024 * 1024  # 2,000 MB (~2 GB)
SPLIT_PART_SIZE = 1950 * 1024 * 1024      # 1.95 GB
DOWNLOAD_DIR = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
START_TIME = time.time()
DB_FILE = "bot_database.db"

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

# ==========================================
# 2. قاموس اللغات المزدوج الشامل (Arabic & English Dictionary)
# ==========================================
TEXTS = {
    "ar": {
        "welcome": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌌 <b>مرحباً بك يا {name} في المحرك الخارق OMNIPOTENT OVERLORD! ⚡👑</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "متاح الآن أقصى سرعة تنزيل بـ <b>الروابط المباشرة + التورينت (Magnet / .torrent)</b> ومصفوفة تسريع شبكية فائقة!\n\n"
            "💡 <b>طريقة الاستخدام:</b>\n"
            "• أرسل أي رابط تحميل مباشر (HTTP / HTTPS)\n"
            "• أرسل أي رابط تورينت مغناطيسي (Magnet Link)\n"
            "• أرسل أي ملف تورينت (file.torrent) مباشرة!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "god_panel": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌌 <b>لوحة تحكم OMNIPOTENT OVERLORD ENGINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 <b>خيوط التسريع القصوى:</b> <code>{threads}x Parallel Workers</code>\n"
            "🧲 <b>دعم التورينت:</b> <code>مفعل 100% (Magnet & Torrent Files)</code>\n"
            "🌐 <b>اللغة الحالية:</b> <code>🇸🇦 العربية</code>\n"
            "📄 <b>إجمالي التحميلات:</b> <code>{files} ملفات</code>\n"
            "📊 <b>إجمالي حجم البيانات:</b> <code>{bytes}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "probe_info": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔎 <b>فاحص الروابط OMNIPOTENT Probe</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "استخدم الأمر الفاحص لمعاينة تفاصيل الملف مسبقاً:\n\n"
            "<code>/probe الرابط المباشر</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "settings_title": "⚙️ <b>إعدادات التسريع واللغة وتفضيلات OMNIPOTENT ENGINE:</b>",
        "btn_panel": "⚡ لوحة تحكم OMNIPOTENT",
        "btn_history": "📜 سجل التحميلات",
        "btn_settings": "⚙️ إعدادات التسريع واللغة",
        "btn_probe": "🔎 فحص الروابط Probe",
        "btn_stats": "📊 إحصائيات المحرك",
        "btn_back": "🔙 العودة للقائمة الرئيسية",
        "btn_cancel": "🛑 إلغاء العملية فوراً",
        "btn_lang": "🌐 اللغة: 🇸🇦 العربية",
        "btn_mode_auto": "🎬 وضع الرفع: تلقائي",
        "btn_mode_doc": "📄 وضع الرفع: مستند دائم",
        "btn_threads": "⚡ التسريع: {threads}x Workers",
        "transfer_rate": "🚀 معدل النقل الخارق:",
        "processed_size": "📦 الحجم المعالج:",
        "eta": "⏱️ الوقت المتبقي:",
        "downloading": "جاري التنزيل بوضع OMNIPOTENT OVERLORD...",
        "uploading": "جاري الرفع المباشر إلى تليجرام...",
        "torrent_connecting": "🧲 OMNIPOTENT Torrent: جاري جلب البيانات والاتصال بالـ Peers...",
        "success_title": "🌌 تمت العملية بنجاح ورفع الملف بـ OMNIPOTENT ENGINE! 👑",
        "file_name": "📄 اسم الملف:",
        "category": "التصنيف:",
        "final_size": "📊 الحجم النهائي:",
        "total_time": "⏱️ الوقت الإجمالي:",
        "avg_speed": "🚀 متوسط السرعة:",
        "help_text": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📜 <b>دليل الاستخدام الناري السريع</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. <b>الروابط المباشرة:</b> أرسل رابط الملف المباشر هنا\n"
            "2. <b>روابط التورينت (Magnet):</b> أرسل رابط <code>magnet:?xt=...</code>\n"
            "3. <b>ملفات التورينت:</b> أرسل ملف <code>.torrent</code> مباشرة هنا!\n\n"
            "📝 <b>خيارات التسمية الاختيارية:</b>\n"
            "• <code>الرابط | اسم مخصص</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    },
    "en": {
        "welcome": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌌 <b>Welcome {name} to OMNIPOTENT OVERLORD ENGINE! ⚡👑</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Maximum speed download is active for <b>Direct Links + Torrents (Magnet / .torrent)</b>!\n\n"
            "💡 <b>How to use:</b>\n"
            "• Send any direct HTTP/HTTPS link\n"
            "• Send any Magnet Link (magnet:?xt=...)\n"
            "• Send any .torrent file directly!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "god_panel": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌌 <b>OMNIPOTENT OVERLORD Control Panel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 <b>Parallel Threads:</b> <code>{threads}x Workers</code>\n"
            "🧲 <b>Torrent Support:</b> <code>100% Active (Magnet & Torrent)</code>\n"
            "🌐 <b>Language:</b> <code>🇺🇸 English</code>\n"
            "📄 <b>Total Downloads:</b> <code>{files} files</code>\n"
            "📊 <b>Total Data:</b> <code>{bytes}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "probe_info": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔎 <b>OMNIPOTENT Link Probe</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Use the probe command to inspect file details:\n\n"
            "<code>/probe Direct_URL</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "settings_title": "⚙️ <b>OMNIPOTENT Engine Settings & Preferences:</b>",
        "btn_panel": "⚡ OMNIPOTENT Panel",
        "btn_history": "📜 Download History",
        "btn_settings": "⚙️ Settings & Language",
        "btn_probe": "🔎 Probe Inspector",
        "btn_stats": "📊 Engine Stats",
        "btn_back": "🔙 Back to Main Menu",
        "btn_cancel": "🛑 Cancel Task Immediately",
        "btn_lang": "🌐 Language: 🇺🇸 English",
        "btn_mode_auto": "🎬 Upload Mode: Auto Media",
        "btn_mode_doc": "📄 Upload Mode: Document",
        "btn_threads": "⚡ Acceleration: {threads}x Workers",
        "transfer_rate": "🚀 Transfer Speed:",
        "processed_size": "📦 Processed Data:",
        "eta": "⏱️ Time Remaining:",
        "downloading": "Downloading with OMNIPOTENT ENGINE...",
        "uploading": "Uploading directly to Telegram...",
        "torrent_connecting": "🧲 OMNIPOTENT Torrent: Connecting to Peers & Fetching metadata...",
        "success_title": "🌌 Successfully processed & uploaded with OMNIPOTENT ENGINE! 👑",
        "file_name": "📄 File Name:",
        "category": "Category:",
        "final_size": "📊 Final Size:",
        "total_time": "⏱️ Total Duration:",
        "avg_speed": "🚀 Average Speed:",
        "help_text": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📜 <b>Quick User Guide</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. <b>Direct Links:</b> Send any direct HTTP/HTTPS URL\n"
            "2. <b>Torrent Magnets:</b> Send <code>magnet:?xt=...</code>\n"
            "3. <b>Torrent Files:</b> Send any <code>.torrent</code> file directly!\n\n"
            "📝 <b>Custom Naming:</b>\n"
            "• <code>URL | Custom_Name.ext</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    }
}

# ==========================================
# 3. إدارة وتحديث قاعدة البيانات الدائمة
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at REAL,
            upload_mode TEXT DEFAULT 'auto',
            enable_thumbs INTEGER DEFAULT 1,
            enable_caption INTEGER DEFAULT 1,
            fast_speed INTEGER DEFAULT 1,
            god_threads INTEGER DEFAULT 64,
            lang TEXT DEFAULT 'ar'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            size INTEGER,
            category TEXT DEFAULT '📁 عام',
            timestamp REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY,
            val_num INTEGER DEFAULT 0,
            val_float REAL DEFAULT 0.0
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN god_threads INTEGER DEFAULT 64")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ar'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE history ADD COLUMN category TEXT DEFAULT '📁 عام'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def db_add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, time.time()))
    conn.commit()
    conn.close()

def db_get_user_settings(user_id: int) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT upload_mode, enable_thumbs, enable_caption, fast_speed, god_threads, lang FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if row:
        return {
            "upload_mode": row[0],
            "enable_thumbs": row[1],
            "enable_caption": row[2],
            "fast_speed": row[3],
            "god_threads": row[4] or 64,
            "lang": row[5] or "ar"
        }
    return {"upload_mode": "auto", "enable_thumbs": 1, "enable_caption": 1, "fast_speed": 1, "god_threads": 64, "lang": "ar"}

def db_update_user_setting(user_id: int, key: str, val):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def db_add_history(user_id: int, filename: str, size: int, category: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, filename, size, category, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (user_id, filename, size, category, time.time()))
    conn.commit()
    conn.close()

def db_get_history(user_id: int, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT filename, size, category, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows

def db_get_global_stats() -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), SUM(size) FROM history")
    hist_row = cursor.fetchone()
    total_files = hist_row[0] or 0
    total_bytes = hist_row[1] or 0
    conn.close()
    return {"users": total_users, "files": total_files, "bytes": total_bytes}

def tr(lang: str, key: str, **kwargs) -> str:
    lang_dict = TEXTS.get(lang, TEXTS["ar"])
    template = lang_dict.get(key, TEXTS["ar"].get(key, ""))
    return template.format(**kwargs) if kwargs else template

init_db()

ACTIVE_TASKS = {}
request_queue = asyncio.Queue()

# ==========================================
# 4. خادم الويب للإنعاش (aiohttp Web Server)
# ==========================================
async def handle_health_check(request):
    return web.Response(text="⚡ OMNIPOTENT OVERLORD ENGINE - ABSOLUTE POWER 100%")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 خادم الويب الشغّال (OMNIPOTENT ENGINE) يعمل على المنفذ: {PORT}")

# ==========================================
# 5. إعداد عميل Pyrogram الفائق (16 Workers)
# ==========================================
bot = Client(
    "downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    workers=16
)

# ==========================================
# 6. مستخرج ومفكك الروابط المطلق
# ==========================================
async def unrestrict_direct_link(url: str) -> str:
    # Mediafire
    if "mediafire.com" in url:
        try:
            if CURL_CFFI_AVAILABLE:
                async with CurlAsyncSession(impersonate="chrome124") as session:
                    resp = await session.get(url, headers=STEALTH_HEADERS, allow_redirects=True)
                    if resp.status_code == 200:
                        match = re.search(r'href="(https?://download\d+\.mediafire\.com/[^"]+)"', resp.text)
                        if match:
                            return match.group(1)
            else:
                async with aiohttp.ClientSession(auto_decompress=False) as session:
                    async with session.get(url, headers=STEALTH_HEADERS) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            match = re.search(r'href="(https?://download\d+\.mediafire\.com/[^"]+)"', html)
                            if match:
                                return match.group(1)
        except Exception:
            pass

    # Pixeldrain
    if "pixeldrain.com/u/" in url:
        file_id = url.split("pixeldrain.com/u/")[1].split("?")[0].split("/")[0]
        return f"https://pixeldrain.com/api/file/{file_id}"

    # GitHub Blob
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Dropbox
    if "dropbox.com" in url:
        url = url.replace("dl=0", "dl=1")
        if "?dl=1" not in url and "&dl=1" not in url:
            url += "?dl=1"
        return url

    # Google Drive
    gdrive_match = re.search(r'drive\.google\.com/file/d/([^/]+)', url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Catbox
    if "catbox.moe" in url:
        return url

    return url

# ==========================================
# 7. التنسيق المساعد وحساب الأحجام والوقت
# ==========================================
def humanbytes(size: int) -> str:
    if not size:
        return "0 B"
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'KiB', 2: 'MiB', 3: 'GiB', 4: 'TiB'}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels.get(n, 'B')}"

def time_formatter(seconds: int) -> str:
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((f"{days}d, " if days else "") +
           (f"{hours}h, " if hours else "") +
           (f"{minutes}m, " if minutes else "") +
           (f"{seconds}s" if seconds else ""))
    return tmp if tmp else "0s"

def get_god_category(filename: str) -> tuple:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.3gp', '.wmv'):
        return "🎬", "OMNIPOTENT Video", True
    elif ext in ('.mp3', '.m4a', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma'):
        return "🎵", "OMNIPOTENT Audio", False
    elif ext in ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'):
        return "📦", "OMNIPOTENT Archive", False
    elif ext in ('.apk', '.xapk', '.apks', '.exe', '.msi', '.py', '.js', '.html'):
        return "📱", "OMNIPOTENT Software", False
    elif ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'):
        return "🖼️", "OMNIPOTENT Image", False
    elif ext in ('.pdf', '.docx', '.doc', '.txt', '.epub'):
        return "📄", "OMNIPOTENT Document", False
    else:
        return "📁", "OMNIPOTENT General", False

def smart_extract_filename(url: str, headers: dict) -> str:
    content_disp = headers.get("Content-Disposition", "") or headers.get("content-disposition", "")
    if content_disp:
        for part in content_disp.split(";"):
            if "filename=" in part:
                filename = part.split("filename=")[1].strip('"\'; ')
                if filename:
                    return urllib.parse.unquote(filename)
    
    parsed = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed.path)
    if filename and "." in filename:
        return urllib.parse.unquote(filename)

    ctype = (headers.get("Content-Type", "") or headers.get("content-type", "")).lower()
    ext_map = {
        "video/mp4": ".mp4",
        "video/x-matroska": ".mkv",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/x-rar-compressed": ".rar",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "audio/mpeg": ".mp3",
        "application/vnd.android.package-archive": ".apk"
    }
    for mime, ext in ext_map.items():
        if mime in ctype:
            return f"download_{int(time.time())}{ext}"

    return f"file_{int(time.time())}.bin"

def make_start_keyboard(lang: str = "ar"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tr(lang, "btn_panel"), callback_data="btn_god_panel"),
            InlineKeyboardButton(tr(lang, "btn_history"), callback_data="btn_history")
        ],
        [
            InlineKeyboardButton(tr(lang, "btn_settings"), callback_data="btn_settings"),
            InlineKeyboardButton(tr(lang, "btn_probe"), callback_data="btn_probe_info")
        ],
        [
            InlineKeyboardButton(tr(lang, "btn_stats"), callback_data="btn_stats")
        ]
    ])

def make_settings_keyboard(user_id: int):
    st = db_get_user_settings(user_id)
    lang = st["lang"]
    mode_str = tr(lang, "btn_mode_auto") if st["upload_mode"] == "auto" else tr(lang, "btn_mode_doc")
    threads_str = tr(lang, "btn_threads", threads=st['god_threads'])
    lang_btn_str = "🌐 اللغة: 🇸🇦 العربية" if lang == "ar" else "🌐 Language: 🇺🇸 English"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang_btn_str, callback_data="toggle_lang")],
        [InlineKeyboardButton(mode_str, callback_data="toggle_mode")],
        [InlineKeyboardButton(threads_str, callback_data="toggle_threads")],
        [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]
    ])

def make_back_keyboard(lang: str = "ar"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]
    ])

def make_cancel_keyboard(task_id: str, lang: str = "ar"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "btn_cancel"), callback_data=f"cancel_{task_id}")]
    ])

async def progress_bar(current: int, total: int, status_text: str, message: Message, start_time: float, last_update: list, icon: str = "🌌", task_id: str = None, lang: str = "ar"):
    now = time.time()
    diff = now - start_time
    
    if current != total and (now - last_update[0]) < 2.0:
        return

    last_update[0] = now
    percentage = (current * 100 / total) if total else 0
    speed = current / diff if diff > 0 else 0
    time_to_completion = round((total - current) / speed) if (total and speed > 0) else 0
    
    filled_blocks = math.floor(percentage / 10) if total else 5
    bar = '▰' * filled_blocks + '▱' * (10 - filled_blocks)
    
    total_str = humanbytes(total) if total else "..."
    perc_str = f"{round(percentage, 1)}%" if total else "N/A"
    eta_str = time_formatter(time_to_completion) if total else "..."

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{icon} <b>{status_text}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{bar}</code> <b>{perc_str}</b>\n\n"
        f"{tr(lang, 'transfer_rate')} <code>{humanbytes(speed)}/s</code> 🔥🌌\n"
        f"{tr(lang, 'processed_size')} <code>{humanbytes(current)}</code> / <code>{total_str}</code>\n"
        f"{tr(lang, 'eta')} <code>{eta_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    reply_markup = make_cancel_keyboard(task_id, lang=lang) if task_id else None
    
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except (RPCError, MessageNotModified):
        pass

# ==========================================
# 9. معالجات الرسائل والأوامر المزدوجة
# ==========================================
@bot.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    st = db_get_user_settings(user_id)
    sender = message.from_user.first_name if message.from_user else 'Master'
    
    welcome_text = tr(st["lang"], "welcome", name=sender)
    await message.reply_text(welcome_text, reply_markup=make_start_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("god") | filters.command("godmode") | filters.command("omnipotent"))
async def god_panel_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    g_stats = db_get_global_stats()
    
    god_card = tr(st["lang"], "god_panel", threads=st['god_threads'], files=g_stats['files'], bytes=humanbytes(g_stats['bytes']))
    await message.reply_text(god_card, reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("probe"))
async def probe_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("❌ URL required: <code>/probe URL</code>", parse_mode=ParseMode.HTML)
        return
    
    raw_url = args[1].strip()
    status_msg = await message.reply_text("🔎 <b>Inspecting URL / جاري الفحص...</b>", parse_mode=ParseMode.HTML)
    
    try:
        direct_url = await unrestrict_direct_link(raw_url)
        parsed_url = urllib.parse.urlparse(direct_url)
        referer_header = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        if CURL_CFFI_AVAILABLE:
            headers = {**STEALTH_HEADERS, "Referer": referer_header}
            async with CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                resp = await session.get(direct_url, headers=headers)
                status = resp.status_code
                clen = resp.headers.get("Content-Length", "N/A")
                ctype = resp.headers.get("Content-Type", "N/A")
                fname = smart_extract_filename(direct_url, resp.headers)
        else:
            timeout = aiohttp.ClientTimeout(total=15, sock_connect=10)
            headers = {**STEALTH_HEADERS, "Referer": referer_header}
            async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                async with session.head(direct_url, headers=headers, allow_redirects=True) as resp:
                    status = resp.status
                    clen = resp.headers.get("Content-Length", "N/A")
                    ctype = resp.headers.get("Content-Type", "N/A")
                    fname = smart_extract_filename(direct_url, resp.headers)

        icon, category, _ = get_god_category(fname)
        size_str = humanbytes(int(clen)) if clen.isdigit() else clen
        
        probe_card = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌌 <b>OMNIPOTENT Probe Report:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 <b>File:</b> <code>{fname}</code>\n"
            f"{icon} <b>Category:</b> <code>{category}</code>\n"
            f"📊 <b>Size:</b> <code>{size_str}</code>\n"
            f"🌐 <b>HTTP Code:</b> <code>{status} OK</code>\n"
            f"🏷️ <b>Type:</b> <code>{ctype}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await status_msg.edit_text(probe_card, parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Probe Failed / فشل الفحص:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("settings") | filters.command("lang"))
async def settings_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    await message.reply_text(
        tr(st["lang"], "settings_title"),
        reply_markup=make_settings_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command("help"))
async def help_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    await message.reply_text(tr(st["lang"], "help_text"), reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("stats"))
async def stats_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    g_stats = db_get_global_stats()
    queue_size = request_queue.qsize()
    uptime_sec = int(time.time() - START_TIME)
    
    stats_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Engine Stats / إحصائيات المحرك</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ <b>Uptime:</b> <code>{time_formatter(uptime_sec)}</code>\n"
        f"📄 <b>Total Files:</b> <code>{g_stats['files']}</code>\n"
        f"📊 <b>Total Bytes:</b> <code>{humanbytes(g_stats['bytes'])}</code>\n"
        f"⏳ <b>Queue Size:</b> <code>{queue_size}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(stats_text, reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("history"))
async def history_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    st = db_get_user_settings(user_id)
    history_list = db_get_history(user_id, limit=10)
    
    if not history_list:
        text = "📜 <b>No download history found / لا يوجد سجل تحميلات بعد.</b>"
    else:
        text = "📜 <b>Latest Downloads / أحدث التحميلات:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, (fname, fsize, fcat, fts) in enumerate(history_list, 1):
            t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(fts))
            text += f"{i}. 📄 <code>{fname}</code>\n   🏷️ {fcat} | 📊 {humanbytes(fsize)} | ⏱️ {t_str}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    await message.reply_text(text, reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id if query.from_user else 0
    st = db_get_user_settings(user_id)
    lang = st["lang"]
    
    if data.startswith("cancel_"):
        task_id = data.split("cancel_", 1)[1]
        if task_id in ACTIVE_TASKS:
            ACTIVE_TASKS[task_id]["cancelled"] = True
            await query.answer("🛑 Task cancelled / تم الإلغاء...", show_alert=True)
        else:
            await query.answer("⚠️ Task already completed.", show_alert=True)
        return

    if data == "toggle_lang":
        new_lang = "en" if lang == "ar" else "ar"
        db_update_user_setting(user_id, "lang", new_lang)
        await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
        await query.answer("Language updated! / تم تغيير اللغة!", show_alert=True)
        return

    elif data == "toggle_mode":
        new_mode = "doc" if st["upload_mode"] == "auto" else "auto"
        db_update_user_setting(user_id, "upload_mode", new_mode)
        await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
        await query.answer("Upload mode toggled!")
        return

    elif data == "toggle_threads":
        thread_modes = [16, 32, 64]
        curr_idx = thread_modes.index(st["god_threads"]) if st["god_threads"] in thread_modes else 0
        new_threads = thread_modes[(curr_idx + 1) % len(thread_modes)]
        db_update_user_setting(user_id, "god_threads", new_threads)
        await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
        await query.answer(f"Threads updated to {new_threads}x!")
        return

    if data == "btn_start":
        sender = query.from_user.first_name if query.from_user else 'Master'
        await query.message.edit_text(tr(lang, "welcome", name=sender), reply_markup=make_start_keyboard(lang), parse_mode=ParseMode.HTML)

    elif data == "btn_god_panel":
        g_stats = db_get_global_stats()
        god_card = tr(lang, "god_panel", threads=st['god_threads'], files=g_stats['files'], bytes=humanbytes(g_stats['bytes']))
        await query.message.edit_text(god_card, reply_markup=make_back_keyboard(lang), parse_mode=ParseMode.HTML)

    elif data == "btn_probe_info":
        await query.message.edit_text(tr(lang, "probe_info"), reply_markup=make_back_keyboard(lang), parse_mode=ParseMode.HTML)

    elif data == "btn_settings":
        await query.message.edit_text(
            tr(lang, "settings_title"),
            reply_markup=make_settings_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "btn_help":
        await query.message.edit_text(tr(lang, "help_text"), reply_markup=make_back_keyboard(lang), parse_mode=ParseMode.HTML)

    elif data == "btn_history":
        history_list = db_get_history(user_id, limit=10)
        if not history_list:
            text = "📜 <b>No download history found / لا يوجد سجل تحميلات بعد.</b>"
        else:
            text = "📜 <b>Latest Downloads / أحدث التحميلات:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for i, (fname, fsize, fcat, fts) in enumerate(history_list, 1):
                t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(fts))
                text += f"{i}. 📄 <code>{fname}</code>\n   🏷️ {fcat} | 📊 {humanbytes(fsize)} | ⏱️ {t_str}\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        await query.message.edit_text(text, reply_markup=make_back_keyboard(lang), parse_mode=ParseMode.HTML)

    elif data == "btn_stats":
        g_stats = db_get_global_stats()
        queue_size = request_queue.qsize()
        uptime_sec = int(time.time() - START_TIME)
        stats_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Engine Stats / إحصائيات المحرك</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>Uptime:</b> <code>{time_formatter(uptime_sec)}</code>\n"
            f"📄 <b>Total Files:</b> <code>{g_stats['files']}</code>\n"
            f"📊 <b>Total Bytes:</b> <code>{humanbytes(g_stats['bytes'])}</code>\n"
            f"⏳ <b>Queue Size:</b> <code>{queue_size}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.message.edit_text(stats_text, reply_markup=make_back_keyboard(lang), parse_mode=ParseMode.HTML)

    await query.answer()

# ==========================================
# 10. استقبال وتجهيز المستندات والتورينت (.torrent Document)
# ==========================================
@bot.on_message(filters.document & ~filters.service)
async def handle_document_torrent(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id:
        db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")

    doc = message.document
    if doc and doc.file_name and doc.file_name.lower().endswith(".torrent"):
        status_msg = await message.reply_text("🧲 <b>Downloading .torrent file & initializing Torrent Engine...</b>", parse_mode=ParseMode.HTML)
        torrent_file = await message.download(file_name=os.path.join(DOWNLOAD_DIR, doc.file_name))
        await request_queue.put(("torrent", torrent_file, status_msg, message))

# ==========================================
# 11. استقبال الروابط الفورية والتورينت المغناطيسي (Magnet Links)
# ==========================================
@bot.on_message((filters.text | filters.caption) & ~filters.service)
async def handle_all_messages(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id:
        db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")

    msg_time = message.date.timestamp() if message.date else 0
    if msg_time and (time.time() - msg_time) > 45:
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        return

    if text.startswith("/"):
        if text.startswith("/eval"):
            code = text.replace("/eval", "", 1).strip()
            try:
                res = eval(code)
                await message.reply_text(f"💻 <b>Eval Result:</b>\n<code>{res}</code>", parse_mode=ParseMode.HTML)
            except Exception as e:
                await message.reply_text(f"❌ <b>Eval Error:</b>\n<code>{e}</code>", parse_mode=ParseMode.HTML)
        return

    # التورينت المغناطيسي (Magnet Links)
    if "magnet:?" in text:
        magnet_match = re.search(r'magnet:\?[^\s]+', text)
        if magnet_match:
            magnet_url = magnet_match.group(0)
            status_msg = await message.reply_text("🧲 <b>OMNIPOTENT Magnet Link received! Connecting to Peers...</b>", parse_mode=ParseMode.HTML)
            await request_queue.put(("torrent", magnet_url, status_msg, message))
            return

    is_zip_bundle = False
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    if lines and lines[0].upper() == "[ZIP]":
        is_zip_bundle = True
        lines = lines[1:]

    valid_requests = []
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        raw_url = parts[0]
        if "http://" in raw_url or "https://" in raw_url:
            url_match = re.search(r'https?://[^\s]+', raw_url)
            if url_match:
                extracted_url = url_match.group(0)
                custom_name = parts[1] if len(parts) > 1 and parts[1] else None
                custom_caption = parts[2] if len(parts) > 2 and parts[2] else None
                valid_requests.append((extracted_url, custom_name, custom_caption))

    if not valid_requests:
        return

    if is_zip_bundle:
        status_msg = await message.reply_text("📦 <b>Downloading files & building single ZIP bundle...</b>", parse_mode=ParseMode.HTML)
        await request_queue.put(("zip_bundle", valid_requests, status_msg, message))
        return

    if len(valid_requests) > 1:
        await message.reply_text(
            f"📥 <b>Received {len(valid_requests)} URLs! Added to queue... 🚀</b>",
            parse_mode=ParseMode.HTML
        )

    for item in valid_requests:
        url, custom_name, custom_caption = item
        queue_pos = request_queue.qsize() + 1
        
        if queue_pos > 1:
            status_msg = await message.reply_text(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>OMNIPOTENT Queue Position #{queue_pos-1}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📄 <b>URL:</b> <code>{url[:45]}...</code>\n\n"
                f"<i>Processing will start automatically...</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML
            )
        else:
            status_msg = await message.reply_text(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Extracting & processing OMNIPOTENT URL...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML
            )

        await request_queue.put(("single", (url, custom_name, custom_caption), status_msg, message))

async def queue_worker():
    while True:
        task_data = await request_queue.get()
        task_type = task_data[0]
        
        try:
            if task_type == "torrent":
                _, torrent_src, status_msg, user_msg = task_data
                await process_torrent_download(torrent_src, status_msg, user_msg)
            elif task_type == "zip_bundle":
                _, valid_requests, status_msg, user_msg = task_data
                await process_zip_bundle(valid_requests, status_msg, user_msg)
            else:
                _, (url, custom_name, custom_caption), status_msg, user_msg = task_data
                await process_download_and_upload(url, custom_name, custom_caption, status_msg, user_msg)
        except Exception as e:
            logger.exception(f"خطأ أثناء معالجة المهمة: {e}")
        finally:
            request_queue.task_done()

# ==========================================
# 12. معالجة وتنزيل ملفات التورينت (Torrent & Magnet Downloader Engine)
# ==========================================
async def process_torrent_download(torrent_src: str, status_msg: Message, user_msg: Message):
    user_id = user_msg.from_user.id if user_msg.from_user else 0
    st = db_get_user_settings(user_id)
    lang = st["lang"]

    if not TORRENTP_AVAILABLE:
        await status_msg.edit_text("❌ <b>Torrent engine module missing (torrentp)!</b>", parse_mode=ParseMode.HTML)
        return

    task_id = f"task_{int(time.time() * 1000)}"
    ACTIVE_TASKS[task_id] = {"cancelled": False}
    start_time = time.time()
    
    await status_msg.edit_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧲 <b>{tr(lang, 'torrent_connecting')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=make_cancel_keyboard(task_id, lang=lang),
        parse_mode=ParseMode.HTML
    )

    try:
        downloader = TorrentDownloader(torrent_src, save_path=DOWNLOAD_DIR)
        dl_task = asyncio.create_task(downloader.start_download())
        
        while not dl_task.done():
            if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                downloader.stop_download()
                dl_task.cancel()
                await status_msg.edit_text("🛑 <b>Torrent task cancelled!</b>", parse_mode=ParseMode.HTML)
                return
            await asyncio.sleep(2.0)

        await dl_task
        
        downloaded_items = []
        for root, dirs, files in os.walk(DOWNLOAD_DIR):
            for file in files:
                fpath = os.path.join(root, file)
                if os.path.getmtime(fpath) >= start_time and not file.endswith(".torrent"):
                    downloaded_items.append(fpath)

        if not downloaded_items:
            await status_msg.edit_text("❌ <b>No downloaded files found from Torrent!</b>", parse_mode=ParseMode.HTML)
            return

        for fpath in downloaded_items:
            fname = os.path.basename(fpath)
            fsize = os.path.getsize(fpath)
            await process_single_local_file_upload(fpath, fname, fsize, status_msg, user_msg, user_id, start_time, task_id)

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Torrent Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        ACTIVE_TASKS.pop(task_id, None)

async def process_single_local_file_upload(file_path: str, filename: str, actual_file_size: int, status_msg: Message, user_msg: Message, user_id: int, start_time: float, task_id: str):
    settings = db_get_user_settings(user_id)
    lang = settings["lang"]
    icon, category_desc, is_video_type = get_god_category(filename)
    force_video = False if settings["upload_mode"] == "doc" else is_video_type
    
    if actual_file_size > MAX_SINGLE_FILE_SIZE:
        num_parts = math.ceil(actual_file_size / SPLIT_PART_SIZE)
        await status_msg.edit_text(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✂️ <b>OMNIPOTENT Splitter: Splitting giant torrent file into {num_parts} parts...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML
        )
        part_number = 1
        ext = os.path.splitext(filename)[1]
        with open(file_path, "rb") as src_file:
            while True:
                if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    return
                chunk_data = src_file.read(SPLIT_PART_SIZE)
                if not chunk_data:
                    break
                part_filename = f"{os.path.splitext(filename)[0]}.part{part_number:03d}{ext}"
                part_filepath = os.path.join(DOWNLOAD_DIR, part_filename)
                with open(part_filepath, "wb") as part_file:
                    part_file.write(chunk_data)
                await user_msg.reply_document(
                    document=part_filepath,
                    caption=f"🧩 <b>Torrent Part {part_number}/{num_parts}</b>\n📄 <code>{part_filename}</code>",
                    parse_mode=ParseMode.HTML
                )
                if os.path.exists(part_filepath): os.remove(part_filepath)
                part_number += 1
        db_add_history(user_id, filename, actual_file_size, category_desc)
        await status_msg.delete()
        return

    await status_msg.edit_text(f"📤 <b>{tr(lang, 'uploading')}</b>", parse_mode=ParseMode.HTML)
    up_start_time = time.time()
    last_update = [0]
    
    async def pyrogram_progress(current, total):
        await progress_bar(current, total, tr(lang, "uploading"), status_msg, up_start_time, last_update, icon="📤", task_id=task_id, lang=lang)

    caption = f"📄 <b>File:</b> <code>{filename}</code>\n{icon} <b>Category:</b> {category_desc}\n📊 <b>Size:</b> <code>{humanbytes(actual_file_size)}</code>"
    
    if force_video:
        await user_msg.reply_video(video=file_path, caption=caption, supports_streaming=True, progress=pyrogram_progress, parse_mode=ParseMode.HTML)
    else:
        await user_msg.reply_document(document=file_path, caption=caption, progress=pyrogram_progress, parse_mode=ParseMode.HTML)
        
    total_time_spent = round(time.time() - start_time)
    avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
    db_add_history(user_id, filename, actual_file_size, category_desc)
    await status_msg.delete()
    
    success_card = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tr(lang, 'success_title')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tr(lang, 'file_name')} <code>{filename}</code>\n"
        f"{icon} {tr(lang, 'category')} {category_desc}\n"
        f"{tr(lang, 'final_size')} <code>{humanbytes(actual_file_size)}</code>\n"
        f"{tr(lang, 'total_time')} <code>{time_formatter(total_time_spent)}</code>\n"
        f"{tr(lang, 'avg_speed')} <code>{humanbytes(avg_speed)}/s</code> 🔥🌌\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)

async def process_zip_bundle(valid_requests: list, status_msg: Message, user_msg: Message):
    zip_filename = f"bundle_{int(time.time())}.zip"
    zip_filepath = os.path.join(DOWNLOAD_DIR, zip_filename)
    downloaded_files = []
    
    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for idx, (raw_url, cname, _) in enumerate(valid_requests, 1):
                await status_msg.edit_text(f"📦 <b>Downloading file {idx}/{len(valid_requests)} for ZIP bundle...</b>", parse_mode=ParseMode.HTML)
                direct_url = await unrestrict_direct_link(raw_url)
                parsed_url = urllib.parse.urlparse(direct_url)
                referer_header = f"{parsed_url.scheme}://{parsed_url.netloc}/"
                
                if CURL_CFFI_AVAILABLE:
                    headers = {**STEALTH_HEADERS, "Referer": referer_header}
                    async with CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                        resp = await session.get(direct_url, headers=headers, stream=True)
                        fname = cname or smart_extract_filename(direct_url, resp.headers)
                        temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                        with open(temp_fpath, "wb") as f:
                            async for chunk in resp.aiter_content(2048 * 1024):
                                if chunk: f.write(chunk)
                        zip_file.write(temp_fpath, arcname=fname)
                        downloaded_files.append(temp_fpath)
                else:
                    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
                    headers = {**STEALTH_HEADERS, "Referer": referer_header}
                    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                        async with session.get(direct_url, headers=headers, allow_redirects=True) as resp:
                            if resp.status == 200:
                                fname = cname or smart_extract_filename(direct_url, resp.headers)
                                temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                                with open(temp_fpath, "wb") as f:
                                    async for chunk in resp.content.iter_chunked(2048 * 1024):
                                        if chunk: f.write(chunk)
                                zip_file.write(temp_fpath, arcname=fname)
                                downloaded_files.append(temp_fpath)
        
        zip_size = os.path.getsize(zip_filepath)
        await status_msg.edit_text("📤 <b>ZIP Bundle created! Uploading to Telegram...</b>", parse_mode=ParseMode.HTML)
        
        await user_msg.reply_document(
            document=zip_filepath,
            caption=f"📦 <b>OMNIPOTENT ZIP Bundle ({len(downloaded_files)} files)</b>\n📊 <b>Size:</b> <code>{humanbytes(zip_size)}</code>",
            parse_mode=ParseMode.HTML
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>ZIP bundle failed:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        for fpath in downloaded_files:
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        if os.path.exists(zip_filepath):
            try: os.remove(zip_filepath)
            except Exception: pass

async def process_download_and_upload(raw_url: str, custom_name: str, custom_caption: str, status_msg: Message, user_msg: Message):
    file_path = None
    start_time = time.time()
    task_id = f"task_{int(time.time() * 1000)}"
    ACTIVE_TASKS[task_id] = {"cancelled": False}
    user_id = user_msg.from_user.id if user_msg.from_user else 0
    settings = db_get_user_settings(user_id)
    lang = settings["lang"]
    
    try:
        direct_url = await unrestrict_direct_link(raw_url)
        parsed_url = urllib.parse.urlparse(direct_url)
        referer_header = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        status_tracker = {"downloaded": 0}
        dl_start_time = time.time()
        last_update = [0]
        download_success = False

        profiles = [
            ("chrome124", referer_header),
            ("firefox120", "https://www.google.com/"),
            ("safari15_5", direct_url)
        ]

        if CURL_CFFI_AVAILABLE:
            for target_prof, target_ref in profiles:
                if download_success or ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    break

                max_stalled_retries = 5
                for retry_idx in range(max_stalled_retries):
                    if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        break

                    headers = {**STEALTH_HEADERS, "Referer": target_ref}
                    if status_tracker["downloaded"] > 0:
                        headers["Range"] = f"bytes={status_tracker['downloaded']}-"

                    try:
                        async with CurlAsyncSession(impersonate=target_prof, allow_redirects=True) as session:
                            resp = await session.get(direct_url, headers=headers, stream=True)
                            
                            if resp.status_code not in (200, 206, 301, 302, 307, 308):
                                break
                            
                            content_length = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                            total_size = int(content_length) if content_length and content_length.isdigit() else 0
                            if resp.status_code == 206 and total_size:
                                total_size += status_tracker["downloaded"]

                            extracted_filename = smart_extract_filename(direct_url, resp.headers)
                            _, ext = os.path.splitext(extracted_filename)
                            
                            if custom_name:
                                filename = f"{custom_name}{ext}" if ext and not custom_name.lower().endswith(ext.lower()) else custom_name
                            else:
                                filename = extracted_filename

                            icon, category_desc, is_video_type = get_god_category(filename)
                            file_path = os.path.join(DOWNLOAD_DIR, filename)

                            size_disp = humanbytes(total_size) if total_size else "..."
                            info_card = (
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"⚡ <b>OMNIPOTENT Downloader Prepared:</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📄 <b>File:</b> <code>{filename}</code>\n"
                                f"{icon} <b>Category:</b> {category_desc}\n"
                                f"📊 <b>Size:</b> <code>{size_disp}</code>\n"
                                f"🚀 <b>Auto-Resume Engine:</b> {target_prof} (Retry {retry_idx+1})\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                            )
                            await status_msg.edit_text(info_card, reply_markup=make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                            mode = "a+b" if status_tracker["downloaded"] > 0 else "wb"
                            last_chunk_time = time.time()
                            stalled = False

                            with open(file_path, mode) as f:
                                if status_tracker["downloaded"] > 0:
                                    f.seek(status_tracker["downloaded"])
                                
                                async for chunk in resp.aiter_content(1024 * 1024):
                                    if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                                        await status_msg.edit_text("🛑 <b>Download cancelled!</b>", parse_mode=ParseMode.HTML)
                                        return
                                    if chunk:
                                        f.write(chunk)
                                        status_tracker["downloaded"] += len(chunk)
                                        last_chunk_time = time.time()
                                        await progress_bar(
                                            status_tracker["downloaded"],
                                            total_size,
                                            tr(lang, "downloading"),
                                            status_msg,
                                            dl_start_time,
                                            last_update,
                                            icon="⚡",
                                            task_id=task_id,
                                            lang=lang
                                        )
                                    
                                    if (time.time() - last_chunk_time) > 5.0:
                                        logger.warning(f"⚠️ Stream stalled for 5s. Auto-Resuming from byte {status_tracker['downloaded']}...")
                                        stalled = True
                                        break

                            if not stalled:
                                download_success = True
                                break

                    except Exception as ex:
                        logger.warning(f"Connection retry {retry_idx} error: {ex}")
                        await asyncio.sleep(1.0)

        if not download_success and not ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
            headers = {**STEALTH_HEADERS, "Referer": referer_header}
            async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                async with session.get(direct_url, headers=headers, allow_redirects=True) as response:
                    if response.status not in (200, 206):
                        await status_msg.edit_text(f"❌ <b>URL Error: Server responded with status {response.status}</b>", parse_mode=ParseMode.HTML)
                        return
                    
                    content_length = response.headers.get("Content-Length")
                    total_size = int(content_length) if content_length and content_length.isdigit() else 0
                    
                    extracted_filename = smart_extract_filename(direct_url, response.headers)
                    _, ext = os.path.splitext(extracted_filename)
                    filename = f"{custom_name}{ext}" if custom_name else extracted_filename
                    icon, category_desc, is_video_type = get_god_category(filename)
                    file_path = os.path.join(DOWNLOAD_DIR, filename)

                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(2048 * 1024):
                            if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                                await status_msg.edit_text("🛑 <b>Download cancelled!</b>", parse_mode=ParseMode.HTML)
                                return

                            if chunk:
                                f.write(chunk)
                                status_tracker["downloaded"] += len(chunk)
                                await progress_bar(
                                    status_tracker["downloaded"],
                                    total_size,
                                    tr(lang, "downloading"),
                                    status_msg,
                                    dl_start_time,
                                    last_update,
                                    icon="⚡",
                                    task_id=task_id,
                                    lang=lang
                                )
        
        actual_file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
        
        if actual_file_size > MAX_SINGLE_FILE_SIZE:
            num_parts = math.ceil(actual_file_size / SPLIT_PART_SIZE)
            await status_msg.edit_text(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✂️ <b>OMNIPOTENT Splitter: Splitting giant file into {num_parts} parts...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML
            )
            part_number = 1
            with open(file_path, "rb") as src_file:
                while True:
                    if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        return
                    chunk_data = src_file.read(SPLIT_PART_SIZE)
                    if not chunk_data:
                        break
                    part_filename = f"{os.path.splitext(filename)[0]}.part{part_number:03d}{ext}"
                    part_filepath = os.path.join(DOWNLOAD_DIR, part_filename)
                    with open(part_filepath, "wb") as part_file:
                        part_file.write(chunk_data)
                    await user_msg.reply_document(
                        document=part_filepath,
                        caption=f"🧩 <b>Part {part_number}/{num_parts}</b>\n📄 <code>{part_filename}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    if os.path.exists(part_filepath): os.remove(part_filepath)
                    part_number += 1
            db_add_history(user_id, filename, actual_file_size, category_desc)
            await status_msg.delete()
            return

        await status_msg.edit_text(f"📤 <b>{tr(lang, 'uploading')}</b>", reply_markup=make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)
        up_start_time = time.time()
        last_update = [0]
        
        async def pyrogram_progress(current, total):
            if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                return
            await progress_bar(
                current, total, tr(lang, "uploading"), status_msg, up_start_time, last_update, icon="📤", task_id=task_id, lang=lang
            )

        caption = custom_caption if custom_caption else f"📄 <b>File:</b> <code>{filename}</code>\n{icon} <b>Category:</b> {category_desc}\n📊 <b>Size:</b> <code>{humanbytes(actual_file_size)}</code>"

        if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            await status_msg.edit_text("🛑 <b>Upload cancelled!</b>", parse_mode=ParseMode.HTML)
            return

        force_video = False if settings["upload_mode"] == "doc" else is_video_type
        if force_video:
            await user_msg.reply_video(video=file_path, caption=caption, supports_streaming=True, progress=pyrogram_progress, parse_mode=ParseMode.HTML)
        else:
            await user_msg.reply_document(document=file_path, caption=caption, progress=pyrogram_progress, parse_mode=ParseMode.HTML)
            
        total_time_spent = round(time.time() - start_time)
        avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
        
        db_add_history(user_id, filename, actual_file_size, category_desc)
        await status_msg.delete()
        
        success_card = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tr(lang, 'success_title')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tr(lang, 'file_name')} <code>{filename}</code>\n"
            f"{icon} {tr(lang, 'category')} {category_desc}\n"
            f"{tr(lang, 'final_size')} <code>{humanbytes(actual_file_size)}</code>\n"
            f"{tr(lang, 'total_time')} <code>{time_formatter(total_time_spent)}</code>\n"
            f"{tr(lang, 'avg_speed')} <code>{humanbytes(avg_speed)}/s</code> 🔥🌌\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)

    except aiohttp.ClientError as e:
        await status_msg.edit_text(f"❌ <b>Network Connection Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ <b>Request Timeout.</b>", parse_mode=ParseMode.HTML)
    except OSError as e:
        await status_msg.edit_text(f"❌ <b>Disk/Storage Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except RPCError as e:
        await status_msg.edit_text(f"❌ <b>Telegram Upload Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Unexpected Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        ACTIVE_TASKS.pop(task_id, None)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

# ==========================================
# 13. نقطة البداية وتشغيل البوت (Main Entry Point)
# ==========================================
async def main():
    if not API_ID or not API_HASH or not BOT_TOKEN:
        logger.error("❌ API_ID, API_HASH, or BOT_TOKEN missing!")
        sys.exit(1)

    await start_web_server()
    asyncio.create_task(queue_worker())

    logger.info("Starting Pyrogram Client with Bilingual OMNIPOTENT OVERLORD ENGINE...")
    await bot.start()
    
    me = await bot.get_me()
    logger.info("==================================================")
    logger.info(f"⚡ OMNIPOTENT BILINGUAL ENGINE ACTIVATED!")
    logger.info(f"👤 Bot Username: @{me.username}")
    logger.info(f"🆔 Bot ID: {me.id}")
    logger.info("==================================================")

    try:
        await bot.set_bot_commands([
            BotCommand("start", "🚀 Main Menu / القائمة الرئيسية"),
            BotCommand("omnipotent", "⚡ OMNIPOTENT Control Panel"),
            BotCommand("probe", "🔎 Inspect Direct URL / فحص الرابط"),
            BotCommand("settings", "⚙️ Language & Settings / الإعدادات واللغة"),
            BotCommand("help", "📜 Usage Guide / دليل الاستخدام"),
            BotCommand("history", "📜 History / سجل التحميلات"),
            BotCommand("stats", "📊 Engine Stats / إحصائيات المحرك")
        ])
    except Exception as e:
        logger.warning(f"Set commands notice: {e}")

    await idle()
    await bot.stop()

if __name__ == "__main__":
    try:
        bot.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
