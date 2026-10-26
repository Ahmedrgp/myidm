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
import json
import time
import math
import re
import gc
import logging
import tempfile
import sqlite3
import zipfile
import urllib.parse
import html
import hashlib
import shutil
from dotenv import load_dotenv
import aiohttp
from aiohttp import web

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, RPCError, MessageNotModified

import pyrogram.utils
# Fix 64-bit Telegram Channel IDs in Pyrogram (-100...)
pyrogram.utils.MIN_CHANNEL_ID = -10099999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000

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

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
    try:
        from yt_dlp.extractor import odnoklassniki
        _orig_ok_parse_json = odnoklassniki.OdnoklassnikiIE._parse_json
        def _safe_ok_parse_json(self, json_string, *args, **kwargs):
            if isinstance(json_string, (dict, list)):
                return json_string
            return _orig_ok_parse_json(self, json_string, *args, **kwargs)
        odnoklassniki.OdnoklassnikiIE._parse_json = _safe_ok_parse_json
    except Exception as _patch_err:
        pass
except ImportError:
    YTDLP_AVAILABLE = False

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
# حسابات المالك المصرح لها حصرياً (Private Owner Access)
ADMIN_IDS = {1594244556, 7639267441}
_env_admin = os.environ.get("ADMIN_ID", "").strip()
if _env_admin:
    for _aid in _env_admin.replace(";", ",").split(","):
        if _aid.strip().isdigit():
            ADMIN_IDS.add(int(_aid.strip()))

ADMIN_ID = 1594244556

def is_admin(user_id: int) -> bool:
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS

def _owner_filter(_, __, message):
    if not ADMIN_IDS:
        return True
    uid = message.from_user.id if message.from_user else 0
    return uid in ADMIN_IDS

owner_filter = filters.create(_owner_filter, name="OwnerFilter")

USER_SESSION_STRING = (os.environ.get("USER_SESSION_STRING", "") or os.environ.get("PREMIUM_SESSION", "")).strip().strip("'\"")

if USER_SESSION_STRING:
    MAX_SINGLE_FILE_SIZE = 4000 * 1024 * 1024  # 4,000 MB (~4 GB Telegram Premium Limit)
    SPLIT_PART_SIZE = 3950 * 1024 * 1024      # 3.95 GB
else:
    MAX_SINGLE_FILE_SIZE = 2000 * 1024 * 1024  # 2,000 MB (~2 GB Bot Limit)
    SPLIT_PART_SIZE = 1950 * 1024 * 1024      # 1.95 GB

BASE_TMP = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
DOWNLOAD_DIR = os.path.join(BASE_TMP, "ctele_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
START_TIME = time.time()
DASHBOARD_SECRET = os.environ.get("DASHBOARD_SECRET") or hashlib.sha256(f"{API_HASH}_{BOT_TOKEN}".encode()).hexdigest()[:16]
DB_FILE = "bot_database.db"

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
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
        "btn_caption_on": "📝 الوصف: مفعل ✅",
        "btn_caption_off": "📝 الوصف: معطل ❌",
        "btn_thumbs_on": "🖼️ المعاينة والمصغرات: مفعلة ✅",
        "btn_thumbs_off": "🖼️ المعاينة والمصغرات: معطلة ❌",
        "btn_cleantags_on": "🧹 تنظيف الإعلانات: مفعل ✅",
        "btn_cleantags_off": "🧹 تنظيف الإعلانات: معطل ❌",
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
            "3. <b>ملفات التورينت:</b> أرسل ملف <code>.torrent</code> مباشرة هنا!\n"
            "4. <b>حزمة ZIP مجمعة:</b> أرسل كلمة <code>[ZIP]</code> في السطر الأول ثم الروابط في الأسطر التالية لدمجها تلقائياً في ملف ZIP واحد!\n\n"
            "📝 <b>خيارات التسمية والكابشن المخصص:</b>\n"
            "• <code>الرابط | اسم مخصص | وصف مخصص</code>\n"
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
        "btn_caption_on": "📝 Caption: Enabled ✅",
        "btn_caption_off": "📝 Caption: Disabled ❌",
        "btn_thumbs_on": "🖼️ Thumbnails: Enabled ✅",
        "btn_thumbs_off": "🖼️ Thumbnails: Disabled ❌",
        "btn_cleantags_on": "🧹 Clean Ads & Tags: Enabled ✅",
        "btn_cleantags_off": "🧹 Clean Ads & Tags: Disabled ❌",
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
            "3. <b>Torrent Files:</b> Send any <code>.torrent</code> file directly!\n"
            "4. <b>Bulk ZIP Bundle:</b> Send <code>[ZIP]</code> as the first line, then list URLs to bundle them into a single ZIP archive!\n\n"
            "📝 <b>Custom Naming & Captions:</b>\n"
            "• <code>URL | Custom_Name.ext | Custom_Caption</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    }
}

# ==========================================
# 3. إدارة وتحديث قاعدة البيانات الدائمة
# ==========================================
ALLOWED_USER_SETTINGS = {
    "upload_mode", "enable_thumbs", "enable_caption", "fast_speed",
    "god_threads", "lang", "clean_tags", "custom_prefix", "custom_suffix",
    "channel_tag", "brand_position", "channel_button"
}

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    
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
            lang TEXT DEFAULT 'ar',
            clean_tags INTEGER DEFAULT 1,
            custom_prefix TEXT DEFAULT '',
            custom_suffix TEXT DEFAULT '',
            channel_tag TEXT DEFAULT '',
            brand_position TEXT DEFAULT 'suffix',
            channel_button INTEGER DEFAULT 1
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_replacements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            find_text TEXT,
            replace_text TEXT
        )
    """)
    
    for col, col_def in [
        ("god_threads", "INTEGER DEFAULT 64"),
        ("lang", "TEXT DEFAULT 'ar'"),
        ("clean_tags", "INTEGER DEFAULT 1"),
        ("custom_prefix", "TEXT DEFAULT ''"),
        ("custom_suffix", "TEXT DEFAULT ''"),
        ("channel_tag", "TEXT DEFAULT ''"),
        ("brand_position", "TEXT DEFAULT 'suffix'"),
        ("channel_button", "INTEGER DEFAULT 1")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("ALTER TABLE history ADD COLUMN category TEXT DEFAULT '📁 عام'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def db_add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, time.time()))
    conn.commit()
    conn.close()

def db_get_user_settings(user_id: int) -> dict:
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT upload_mode, enable_thumbs, enable_caption, fast_speed, god_threads, lang,
                   clean_tags, custom_prefix, custom_suffix, channel_tag, brand_position, channel_button
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if row:
        return {
            "upload_mode": row[0] or "auto",
            "enable_thumbs": row[1] if row[1] is not None else 1,
            "enable_caption": row[2] if row[2] is not None else 1,
            "fast_speed": row[3] if row[3] is not None else 1,
            "god_threads": row[4] or 64,
            "lang": row[5] or "ar",
            "clean_tags": row[6] if row[6] is not None else 1,
            "custom_prefix": row[7] or "",
            "custom_suffix": row[8] or "",
            "channel_tag": (row[9] if len(row) > 9 and row[9] is not None else "") or "",
            "brand_position": (row[10] if len(row) > 10 and row[10] is not None else "suffix") or "suffix",
            "channel_button": (row[11] if len(row) > 11 and row[11] is not None else 1)
        }
    return {
        "upload_mode": "auto",
        "enable_thumbs": 1,
        "enable_caption": 1,
        "fast_speed": 1,
        "god_threads": 64,
        "lang": "ar",
        "clean_tags": 1,
        "custom_prefix": "",
        "custom_suffix": "",
        "channel_tag": "",
        "brand_position": "suffix",
        "channel_button": 1
    }

def db_add_replacement(user_id: int, find_text: str, replace_text: str):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO custom_replacements (user_id, find_text, replace_text)
        VALUES (?, ?, ?)
    """, (user_id, find_text, replace_text))
    conn.commit()
    conn.close()

def db_get_user_replacements(user_id: int) -> list:
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT find_text, replace_text FROM custom_replacements WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_clear_user_replacements(user_id: int):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_replacements WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def db_get_total_users_count() -> int:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        cnt = cursor.fetchone()[0]
        conn.close()
        return cnt
    except Exception:
        return 0

def db_update_user_setting(user_id: int, key: str, val):
    if key not in ALLOWED_USER_SETTINGS:
        logger.warning(f"Rejected attempt to update unauthorized setting: {key}")
        return
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def db_add_history(user_id: int, filename: str, size: int, category: str):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, filename, size, category, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (user_id, filename, size, category, time.time()))
    conn.commit()
    conn.close()

def db_get_history(user_id: int, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT filename, size, category, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows

def db_get_all_user_ids() -> list:
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [r[0] for r in rows if r[0]]

def db_get_global_stats() -> dict:
    conn = sqlite3.connect(DB_FILE, timeout=30)
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

DASHBOARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ OMNIPOTENT OVERLORD | Live Monitor & Dashboard</title>
    <style>
        :root {
            --bg-base: #090d16;
            --bg-card: #111827;
            --border: #1f293d;
            --cyan: #00f0ff;
            --purple: #8b5cf6;
            --green: #10b981;
            --red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg-base); color: var(--text-main); min-height: 100vh; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
        .logo-box { display: flex; align-items: center; gap: 12px; }
        .logo-icon { font-size: 28px; filter: drop-shadow(0 0 10px rgba(0,240,255,0.6)); }
        .logo-title { font-size: 22px; font-weight: 800; background: linear-gradient(135deg, #00f0ff, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .status-badge { display: inline-flex; align-items: center; gap: 8px; background: rgba(16, 185, 129, 0.15); color: var(--green); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); }
        .status-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; margin-bottom: 24px; }
        .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 20px; position: relative; overflow: hidden; transition: transform 0.2s, border-color 0.2s; }
        .card:hover { transform: translateY(-2px); border-color: rgba(0,240,255,0.3); }
        .card-title { font-size: 13px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .card-value { font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 8px; }
        .card-sub { font-size: 12px; color: var(--text-muted); }
        .progress-bar-bg { width: 100%; height: 6px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; margin-top: 10px; }
        .progress-bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
        .fill-cyan { background: linear-gradient(90deg, #00f0ff, #3b82f6); }
        .fill-purple { background: linear-gradient(90deg, #8b5cf6, #ec4899); }
        .fill-green { background: linear-gradient(90deg, #10b981, #00f0ff); }
        .fill-orange { background: linear-gradient(90deg, #f59e0b, #ef4444); }
        .chart-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 22px; margin-bottom: 24px; }
        .chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .chart-legend { display: flex; gap: 16px; font-size: 13px; }
        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-color { width: 12px; height: 12px; border-radius: 3px; }
        canvas { width: 100%; height: 200px; display: block; border-radius: 8px; }
        .tasks-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 22px; }
        .table-wrap { overflow-x: auto; margin-top: 14px; }
        table { width: 100%; border-collapse: collapse; text-align: right; font-size: 14px; }
        th { padding: 12px 16px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--border); font-size: 13px; }
        td { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.04); vertical-align: middle; }
        .empty-tasks { text-align: center; padding: 36px 16px; color: var(--text-muted); font-size: 14px; }
        .btn-cancel-task { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
        .btn-cancel-task:hover { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="logo-box">
                <span class="logo-icon">⚡</span>
                <div>
                    <h1 class="logo-title">OMNIPOTENT OVERLORD ENGINE</h1>
                    <div style="font-size: 12px; color: var(--text-muted);">نظام المراقبة الحية والتحكم في الخادم والمهام</div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div class="status-badge"><span class="status-dot"></span> متصل ويعمل بنشاط</div>
                <div id="uptime_disp" style="font-size: 13px; color: var(--text-muted);">تشغيل: 0s</div>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="card-title"><span>استهلاك المعالج (CPU)</span><span>⚡</span></div>
                <div class="card-value" id="cpu_val">0.0%</div>
                <div class="card-sub" id="cpu_sub">معدل التحميل الحقيقي</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-cyan" id="cpu_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>الذاكرة العشوائية (RAM)</span><span>🧠</span></div>
                <div class="card-value" id="ram_val">0 MB</div>
                <div class="card-sub" id="ram_sub">المستخدم من الإجمالي</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-purple" id="ram_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>المساحة التخزينية (Disk)</span><span>💾</span></div>
                <div class="card-value" id="disk_val">0 GB</div>
                <div class="card-sub" id="disk_sub">المساحة المتوفرة</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-green" id="disk_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>المهام وطابور المعالجة</span><span>⏳</span></div>
                <div class="card-value" id="tasks_val">0 / 0</div>
                <div class="card-sub" id="tasks_sub">0 مهام نشطة | 0 في الانتظار</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-orange" id="tasks_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>البيانات المعالجة التراكمية</span><span>📊</span></div>
                <div class="card-value" id="data_val">0 B</div>
                <div class="card-sub" id="files_sub">0 ملفات مكتملة بالكامل</div>
            </div>
            <div class="card">
                <div class="card-title"><span>المستخدمون المسجلون</span><span>👥</span></div>
                <div class="card-value" id="users_val">0</div>
                <div class="card-sub">قاعدة بيانات SQLite المحلية</div>
            </div>
        </div>

        <div class="chart-card">
            <div class="chart-header">
                <div style="font-size: 15px; font-weight: 700;">📈 مخطط الأداء الحي والضغط اللحظي (Live Telemetry)</div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-color" style="background: var(--cyan);"></div><span>المعالج (CPU %)</span></div>
                    <div class="legend-item"><div class="legend-color" style="background: var(--purple);"></div><span>الذاكرة (RAM %)</span></div>
                </div>
            </div>
            <canvas id="liveChart"></canvas>
        </div>

        <div class="tasks-card">
            <div style="font-size: 15px; font-weight: 700; margin-bottom: 6px;">🚀 المهام الجارية في الوقت الفعلي (Active Tasks)</div>
            <div style="font-size: 13px; color: var(--text-muted);">جميع عمليات التحميل والرفع المباشر والتورينت الجارية الآن:</div>
            <div class="table-wrap">
                <table id="tasksTable">
                    <thead>
                        <tr>
                            <th>معرف المهمة (Task ID)</th>
                            <th>الملف / المصدر</th>
                            <th>التقدم</th>
                            <th>السرعة</th>
                            <th>الحالة</th>
                            <th>إجراء</th>
                        </tr>
                    </thead>
                    <tbody id="tasksBody">
                        <tr><td colspan="6" class="empty-tasks">⚡ لا توجد أي مهام تحميل أو رفع جارية حالياً (السيرفر في وضع الاستعداد).</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const SECRET_KEY = "__SECRET_KEY__";
        const cpuHistory = new Array(30).fill(0);
        const ramHistory = new Array(30).fill(0);

        const canvas = document.getElementById('liveChart');
        const ctx = canvas.getContext('2d');

        function resizeCanvas() {
            canvas.width = canvas.parentElement.clientWidth - 44;
            canvas.height = 200;
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        function drawChart() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Grid lines
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.lineWidth = 1;
            for (let y = 0; y <= 100; y += 25) {
                const py = canvas.height - (y / 100) * canvas.height;
                ctx.beginPath();
                ctx.moveTo(0, py);
                ctx.lineTo(canvas.width, py);
                ctx.stroke();
            }

            function drawLine(data, color) {
                ctx.beginPath();
                const step = canvas.width / (data.length - 1);
                data.forEach((val, i) => {
                    const x = i * step;
                    const y = canvas.height - (val / 100) * canvas.height;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.strokeStyle = color;
                ctx.lineWidth = 2.5;
                ctx.stroke();
            }

            drawLine(cpuHistory, '#00f0ff');
            drawLine(ramHistory, '#a855f7');
        }

        async function fetchStats() {
            try {
                const res = await fetch(`/api/dashboard/stats?key=${SECRET_KEY}`);
                if (!res.ok) return;
                const d = await res.json();

                document.getElementById('cpu_val').innerText = d.cpu_percent + '%';
                document.getElementById('cpu_bar').style.width = Math.min(d.cpu_percent, 100) + '%';

                document.getElementById('ram_val').innerText = d.ram_used_mb + ' MB';
                document.getElementById('ram_sub').innerText = `${d.ram_used_mb} MB من ${d.ram_total_mb} MB (${d.ram_percent}%)`;
                document.getElementById('ram_bar').style.width = Math.min(d.ram_percent, 100) + '%';

                document.getElementById('disk_val').innerText = d.disk_free_gb + ' GB';
                document.getElementById('disk_sub').innerText = `${d.disk_used_gb} GB مستخدم من ${d.disk_total_gb} GB (${d.disk_percent}%)`;
                document.getElementById('disk_bar').style.width = Math.min(d.disk_percent, 100) + '%';

                document.getElementById('tasks_val').innerText = `${d.active_tasks_count} / ${d.queue_size}`;
                document.getElementById('tasks_sub').innerText = `${d.active_tasks_count} مهام نشطة | ${d.queue_size} في الانتظار`;
                document.getElementById('tasks_bar').style.width = Math.min((d.active_tasks_count + d.queue_size) * 20, 100) + '%';

                document.getElementById('data_val').innerText = d.total_bytes_human;
                document.getElementById('files_sub').innerText = `${d.total_files} ملفات مكتملة بالكامل`;
                document.getElementById('users_val').innerText = d.total_users;
                document.getElementById('uptime_disp').innerText = 'تشغيل: ' + d.uptime_formatted;

                cpuHistory.shift();
                cpuHistory.push(d.cpu_percent);
                ramHistory.shift();
                ramHistory.push(d.ram_percent);
                drawChart();

                const tbody = document.getElementById('tasksBody');
                if (!d.active_tasks || d.active_tasks.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="empty-tasks">⚡ لا توجد أي مهام تحميل أو رفع جارية حالياً (السيرفر في وضع الاستعداد).</td></tr>';
                } else {
                    let html = '';
                    d.active_tasks.forEach(t => {
                        html += `<tr>
                            <td><code>${t.task_id}</code></td>
                            <td><b>${t.filename}</b></td>
                            <td>
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <div style="flex:1; height:6px; background:rgba(255,255,255,0.1); border-radius:3px;">
                                        <div style="width:${t.progress}%; height:100%; background:var(--cyan); border-radius:3px;"></div>
                                    </div>
                                    <span>${t.progress}%</span>
                                </div>
                            </td>
                            <td><span style="color:var(--cyan); font-weight:600;">${t.speed}</span></td>
                            <td><span style="color:${t.cancelled ? 'var(--red)' : 'var(--green)'}; font-weight:600;">${t.cancelled ? 'ملغاة' : 'نشطة'}</span></td>
                            <td><button class="btn-cancel-task" onclick="cancelTask('${t.task_id}')">🛑 إلغاء</button></td>
                        </tr>`;
                    });
                    tbody.innerHTML = html;
                }
            } catch (err) {
                console.error("Dashboard poll error:", err);
            }
        }

        async function cancelTask(taskId) {
            if (!confirm(`هل أنت متأكد من إلغاء المهمة ${taskId}؟`)) return;
            try {
                await fetch(`/api/dashboard/cancel?key=${SECRET_KEY}&task_id=${taskId}`, { method: 'POST' });
                fetchStats();
            } catch(e) {}
        }

        setInterval(fetchStats, 2000);
        fetchStats();
    </script>
</body>
</html>
"""

async def handle_dashboard_view(request):
    key = request.query.get("key", "")
    if key != DASHBOARD_SECRET:
        return web.Response(
            text="""<!DOCTYPE html><html><head><meta charset="utf-8"><title>403 Access Denied</title>
            <style>body{background:#0a0e17;color:#ef4444;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
            .card{background:#111827;padding:30px;border-radius:12px;border:1px solid #ef4444;text-align:center;}
            h1{margin:0 0 10px;font-size:24px;}p{color:#9ca3af;font-size:14px;}</style></head>
            <body><div class="card"><h1>⛔ 403 Forbidden</h1><p>Invalid or missing dashboard security key.</p></div></body></html>""",
            status=403,
            content_type="text/html"
        )
    return web.Response(text=DASHBOARD_HTML_TEMPLATE.replace("__SECRET_KEY__", DASHBOARD_SECRET), content_type="text/html")

async def handle_dashboard_stats_api(request):
    key = request.query.get("key", "")
    if key != DASHBOARD_SECRET:
        return web.json_response({"error": "unauthorized"}, status=403)

    cpu = psutil.cpu_percent(interval=None) if PSUTIL_AVAILABLE else 0.0
    vmem = psutil.virtual_memory() if PSUTIL_AVAILABLE else None
    ram_used = round(vmem.used / (1024 * 1024)) if vmem else 0
    ram_total = round(vmem.total / (1024 * 1024)) if vmem else 0
    ram_percent = vmem.percent if vmem else 0.0

    disk = shutil.disk_usage(DOWNLOAD_DIR)
    disk_free_gb = round(disk.free / (1024**3), 1)
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round((disk.total - disk.free) / (1024**3), 1)
    disk_percent = round((disk.total - disk.free) / disk.total * 100, 1)

    uptime_sec = int(time.time() - START_TIME)
    g_stats = db_get_global_stats()
    total_users = db_get_total_users_count()

    tasks_data = []
    for tid, tinfo in list(ACTIVE_TASKS.items()):
        tasks_data.append({
            "task_id": tid,
            "cancelled": tinfo.get("cancelled", False),
            "filename": tinfo.get("filename", "Active Job"),
            "progress": tinfo.get("progress", 0),
            "speed": tinfo.get("speed", "0 B/s")
        })

    return web.json_response({
        "status": "online",
        "cpu_percent": cpu,
        "ram_used_mb": ram_used,
        "ram_total_mb": ram_total,
        "ram_percent": ram_percent,
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_percent": disk_percent,
        "uptime_seconds": uptime_sec,
        "uptime_formatted": time_formatter(uptime_sec),
        "active_tasks_count": len(ACTIVE_TASKS),
        "queue_size": request_queue.qsize(),
        "total_users": total_users,
        "total_files": g_stats.get("files", 0),
        "total_bytes": g_stats.get("bytes", 0),
        "total_bytes_human": humanbytes(g_stats.get("bytes", 0)),
        "active_tasks": tasks_data
    })

async def handle_dashboard_cancel_task_api(request):
    key = request.query.get("key", "")
    if key != DASHBOARD_SECRET:
        return web.json_response({"error": "unauthorized"}, status=403)
    tid = request.query.get("task_id", "")
    if tid in ACTIVE_TASKS:
        ACTIVE_TASKS[tid]["cancelled"] = True
        return web.json_response({"success": True, "task_id": tid, "status": "cancelled"})
    return web.json_response({"success": False, "error": "not_found"})

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/dashboard", handle_dashboard_view)
    app.router.add_get("/api/dashboard/stats", handle_dashboard_stats_api)
    app.router.add_post("/api/dashboard/cancel", handle_dashboard_cancel_task_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 خادم الويب الشغّال (OMNIPOTENT ENGINE) يعمل على المنفذ: {PORT}")

# ==========================================
# 5. إعداد عميل Pyrogram الفائق (16 Workers & Multi-DC Parallel Transfers)
# ==========================================
bot = Client(
    "downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    workers=16
)

user_bot = None
if USER_SESSION_STRING:
    user_bot = Client(
        "premium_user_uploader",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING,
        workdir=".",
        workers=16
    )

def get_uploader_client():
    if user_bot and getattr(user_bot, "is_connected", False):
        return user_bot
    return bot

# ==========================================
# 6. فحص التوقيع الرقمي للبايتات (Binary Magic Bytes Signature Verification)
# ==========================================
def is_valid_binary_file(filepath: str) -> tuple:
    if not filepath or not os.path.exists(filepath):
        return False, ""
    
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return False, ""

    try:
        with open(filepath, "rb") as f:
            header = f.read(8192)
    except Exception:
        return False, ""

    # إذا كان الملف يحتوي على بايتات فارغة (null bytes)، فهو حتماً ملف ثنائي وليس صفحة HTML
    if b"\x00" in header:
        return True, ""

    # تواقيع الملفات الثنائية المعروفة
    known_magic = (
        b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",  # ZIP, APK, JAR, DOCX, etc.
        b"\x1f\x8b",                                  # GZIP
        b"Rar!\x1a\x07",                              # RAR
        b"7z\xbc\xaf\x27\x1c",                        # 7Z
        b"%PDF",                                      # PDF
        b"\xff\xd8\xff",                              # JPEG
        b"\x89PNG\r\n\x1a\n",                         # PNG
        b"GIF87a", b"GIF89a",                         # GIF
        b"RIFF",                                      # WEBP, AVI, WAV
        b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2",# MP3
        b"OggS",                                      # OGG
        b"fLaC",                                      # FLAC
        b"\x1aE\xdf\xa3",                             # MKV, WEBM
        b"MZ",                                        # EXE, DLL
        b"\x7fELF",                                   # Linux ELF
    )
    if any(header.startswith(sig) for sig in known_magic):
        return True, ""

    # فحص صريح لنصوص HTML
    header_lower = header.lstrip().lower()
    html_signatures = (
        b"<!doctype html", b"<html", b"<?xml", b"<head", b"<script", b"<!--",
        b"<body", b"<div", b"<title"
    )
    if any(header_lower.startswith(sig) for sig in html_signatures) or (b"<html" in header_lower[:1024]):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f_full:
                return False, f_full.read(300 * 1024)
        except Exception:
            return False, header.decode("utf-8", errors="ignore")

    # إذا لم يكن يحتوي على وسوم HTML، فهو ملف صالح (مثل ملفات نصية، ترجمات srt، كود، إلخ)
    return True, ""

def extract_video_embed_from_html(html_text: str, original_url: str) -> tuple:
    """استخراج مشغلات وسيرفرات الفيديو المضمنة في صفحات المشاهدة (مثل AhwakTV، FaselHD، وغيرها)"""
    if not html_text:
        return None, None

    # استخراج عنوان الفيلم أو الحلقة بدقة
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if not title_match:
        title_match = re.search(r'<title>([^<]+)</title>', html_text, re.I)

    extracted_title = ""
    if title_match:
        raw_t = html.unescape(title_match.group(1)).strip()
        cleaned = re.split(r'[-|–—•»]', raw_t)[0].strip()
        cleaned = re.sub(r'[\\/*?:"<>|]', '', cleaned).strip()
        extracted_title = cleaned

    candidate_urls = []

    # 1. عناصر قوائم السيرفرات (WatchList / data-embed-url / data-url / data-src)
    embed_attrs = [
        r'<li[^>]*data-embed-url=["\']([^"\']+)["\']',
        r'data-embed-url=["\']([^"\']+)["\']',
        r'data-url=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+)["\']',
        r'data-embed=["\']([^"\']+)["\']'
    ]
    for pattern in embed_attrs:
        for match in re.findall(pattern, html_text, re.I):
            clean = html.unescape(match).strip()
            if clean.startswith("//"):
                clean = "https:" + clean
            if clean.startswith("http"):
                candidate_urls.append(clean)

    # 2. إطارات iframes المضمنة
    for ifr in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I):
        clean = html.unescape(ifr).strip()
        if clean.startswith("//"):
            clean = "https:" + clean
        if clean.startswith("http"):
            candidate_urls.append(clean)

    # 3. تدفقات الفيديو المباشرة ومصادر HTML5 video في كود الصفحة
    for v in re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mpd|mp4)[^\s"\'<>]*)', html_text, re.I):
        candidate_urls.append(v)

    # استبعاد روابط التواصل الاجتماعي والإعلانات
    ignore_domains = ["facebook.com", "twitter.com", "x.com", "google.com", "disqus.com", "analytics", "doubleclick", "mg.pamphiltre"]
    unique_candidates = []
    seen = set()
    for c in candidate_urls:
        if c not in seen and not any(ign in c.lower() for ign in ignore_domains):
            seen.add(c)
            unique_candidates.append(c)

    # ترتيب الأفضلية: تفضيل سيرفرات OK.ru ثم Dood و Streamwish وباقي السيرفرات
    priority_hosts = [
        "ok.ru", "odnoklassniki", "dood", "streamwish", "filelions", "vidtube",
        "streamtape", "mixdrop", "mp4upload", "vidspeed", "voe.sx", "uqload", "vk.com"
    ]

    sorted_candidates = sorted(
        unique_candidates,
        key=lambda u: next((i for i, h in enumerate(priority_hosts) if h in u.lower()), 999)
    )

    if sorted_candidates:
        best_candidate = sorted_candidates[0]
        m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/)(\d+)', best_candidate)
        if m_ok:
            best_candidate = f"https://ok.ru/videoembed/{m_ok.group(1)}"
        return best_candidate, extracted_title

    return None, extracted_title

def extract_real_download_link_from_html(html_text: str, original_url: str) -> str:
    if not html_text:
        return ""

    # فحص روابط تأكيد التحميل لملفات Google Drive الكبيرة
    if "drive.google.com" in original_url or "drive.usercontent.google.com" in original_url:
        g_confirm = re.search(r'href=["\'](/uc\?export=download&[^"\']+)["\']', html_text)
        if g_confirm:
            return "https://drive.google.com" + html.unescape(g_confirm.group(1))
        g_confirm2 = re.search(r'href=["\'](https://drive\.usercontent\.google\.com/download\?[^"\']+)["\']', html_text)
        if g_confirm2:
            return html.unescape(g_confirm2.group(1))

    # فحص مشغلات الفيديو وسيرفرات الأفلام أولاً
    video_embed, video_title = extract_video_embed_from_html(html_text, original_url)
    if video_embed:
        title_part = f"&title={urllib.parse.quote(video_title)}" if video_title else ""
        return f"{video_embed}#ref={urllib.parse.quote(original_url)}{title_part}"

    forbidden = ["an1store.apk", "store.apk", "googleplay", "telegram", "play.google.com", "ad.doubleclick"]
    all_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html_text)
    
    candidate_links = []
    for link in all_links:
        link_lower = link.lower()
        if any(f in link_lower for f in forbidden):
            continue

        if any(link_lower.endswith(ext) or f"{ext}?" in link_lower for ext in ('.apk', '.xapk', '.apks', '.zip', '.rar', '.7z')):
            candidate_links.append(link)
        elif any(kw in link_lower for kw in ("d.an1.com", "d.an1.net", "/downloads/", "/download/", "download_link", "file_download")):
            candidate_links.append(link)

    if candidate_links:
        parsed_orig = urllib.parse.urlparse(original_url)
        orig_name = os.path.basename(parsed_orig.path).replace(".html", "")
        if orig_name:
            orig_name_clean = re.sub(r'[^a-zA-Z0-9]', '', orig_name.split('-')[0]).lower()
            for cl in candidate_links:
                if orig_name_clean and orig_name_clean in cl.lower():
                    return cl
        return candidate_links[0]

    return ""

async def unrestrict_terabox(url: str) -> tuple:
    """فك تشفير واستخراج رابط التنزيل المباشر واسم الملف من TeraBox تلقائياً"""
    try:
        m = re.search(r'(?:surl=|/s/|/share/init\?surl=)([a-zA-Z0-9_-]+)', url)
        if not m:
            return url, None
        raw_id = m.group(1)
        clean_id = raw_id[1:] if raw_id.startswith("1") else raw_id
        
        api_endpoints = [
            f"https://terabox-downloader.online/api/get-info?shorturl={clean_id}",
            f"https://yt-api.org/api/terabox?url={urllib.parse.quote(url)}",
            f"https://terabox-api.online/api?url={urllib.parse.quote(url)}"
        ]
        
        headers = {**STEALTH_HEADERS, "Referer": "https://www.terabox.com/"}
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=8)) as session:
            for api in api_endpoints:
                try:
                    async with session.get(api, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                if "list" in data and len(data["list"]) > 0:
                                    item = data["list"][0]
                                    dlink = item.get("dlink") or item.get("download_link") or item.get("direct_link")
                                    fname = item.get("server_filename") or item.get("filename")
                                    if dlink:
                                        return dlink, fname
                                dlink = data.get("download_link") or data.get("dlink") or data.get("direct_link") or data.get("url")
                                fname = data.get("file_name") or data.get("filename")
                                if dlink and isinstance(dlink, str) and dlink.startswith("http"):
                                    return dlink, fname
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"terabox resolver error: {e}")
    return url, None

async def unrestrict_1fichier(url: str) -> str:
    """تجاوز صفحة الانتظار واستخراج رابط التحميل المباشر لـ 1Fichier"""
    try:
        clean_url = url.split('&')[0]
        headers = {
            **STEALTH_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": clean_url
        }
        data = {"did": "0"}
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(clean_url, headers=headers, data=data, allow_redirects=True) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="ignore")
                    m = re.search(r'href=["\'](https?://[a-zA-Z0-9-]+\.1fichier\.com/[^"\'>\s]+)["\']', text)
                    if m:
                        return m.group(1)
                    m_btn = re.search(r'<a[^>]+class=["\'][^"\']*btn-general[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', text)
                    if m_btn:
                        return m_btn.group(1)
    except Exception as e:
        logger.warning(f"1fichier resolver error: {e}")
    return url

async def unrestrict_mega(url: str) -> tuple:
    """فك روابط Mega.nz واستخراج الرابط المباشر السحابي"""
    try:
        api_url = f"https://megadl.hazex.workers.dev/?url={urllib.parse.quote(url)}"
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(api_url, headers=STEALTH_HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        dlink = data.get("url") or data.get("download_url")
                        fname = data.get("filename") or data.get("file_name")
                        if dlink:
                            return dlink, fname
    except Exception as e:
        logger.warning(f"mega resolver error: {e}")
    return url, None

# ==========================================
# 7. مستخرج ومفكك الروابط المطلق مع محاكاة الـ Referer المباشرة
# ==========================================
async def unrestrict_direct_link(url: str) -> str:
    # TeraBox & Affiliated Domains
    terabox_domains = ["terabox.com", "teraboxapp.com", "1024tera.com", "mirrobox.com", "nephobox.com", "freeterabox.com", "terasharelink.com", "terabox.link", "4funbox.com"]
    if any(d in url.lower() for d in terabox_domains):
        direct_tb, tb_name = await unrestrict_terabox(url)
        if direct_tb and direct_tb != url:
            if tb_name:
                return f"{direct_tb}#title={urllib.parse.quote(tb_name)}"
            return direct_tb

    # 1Fichier & Mirrored Domains
    fichier_domains = ["1fichier.com", "alterupload.com", "cjoint.net", "desfichiers.com", "megadl.fr"]
    if any(d in url.lower() for d in fichier_domains):
        direct_1f = await unrestrict_1fichier(url)
        if direct_1f and direct_1f != url:
            return direct_1f

    # Mega.nz / Mega.co.nz
    if "mega.nz" in url.lower() or "mega.co.nz" in url.lower():
        direct_mega, mega_name = await unrestrict_mega(url)
        if direct_mega and direct_mega != url:
            if mega_name:
                return f"{direct_mega}#title={urllib.parse.quote(mega_name)}"
            return direct_mega

    # Mediafire
    if "mediafire.com" in url:
        try:
            if CURL_CFFI_AVAILABLE:
                async with CurlAsyncSession(impersonate="chrome124") as session:
                    resp = await session.get(url, headers=STEALTH_HEADERS, allow_redirects=True, stream=True)
                    if resp.status_code == 200:
                        content_bytes = bytearray()
                        async for chunk in resp.aiter_content(32 * 1024):
                            content_bytes.extend(chunk)
                            if len(content_bytes) >= 128 * 1024:
                                break
                        html_sample = content_bytes.decode("utf-8", errors="ignore")
                        match = re.search(r'href="(https?://download\d+\.mediafire\.com/[^"]+)"', html_sample)
                        if match:
                            return match.group(1)
        except Exception:
            pass

    # Pixeldrain
    if "pixeldrain.com/u/" in url:
        file_id = url.split("pixeldrain.com/u/")[1].split("?")[0].split("/")[0]
        return f"https://pixeldrain.com/api/file/{file_id}"

    # AN1 (an1.net / an1.com / files.an1.net) مع فرض Referer المباشر
    if "an1.net" in url or "an1.com" in url:
        target_ref = "https://an1.com/"
        custom_cookie = ""
        if "#" in url:
            _, frag = url.split("#", 1)
            p_dict = urllib.parse.parse_qs(frag)
            if "cookie" in p_dict and p_dict["cookie"][0]:
                custom_cookie = f"PHPSESSID={p_dict['cookie'][0]}"
        try:
            if CURL_CFFI_AVAILABLE:
                async with CurlAsyncSession(impersonate="chrome124") as session:
                    headers = {**STEALTH_HEADERS, "Referer": target_ref}
                    if custom_cookie:
                        headers["Cookie"] = custom_cookie
                    resp = await session.get(url, headers=headers, allow_redirects=True, stream=True)
                    if resp.status_code == 200:
                        content_length = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                        cl_bytes = int(content_length) if content_length and content_length.isdigit() else 0
                        if cl_bytes > 1 * 1024 * 1024:
                            return resp.url or url

                        content_bytes = bytearray()
                        async for chunk in resp.aiter_content(32 * 1024):
                            content_bytes.extend(chunk)
                            if len(content_bytes) >= 200 * 1024:
                                break
                        html_sample = content_bytes.decode("utf-8", errors="ignore")
                        
                        # البحث عن سيرفرات التنزيل لـ AN1 (d.an1.com)
                        an1_direct = re.findall(r'href=["\'](https?://d\d*\.an1\.(?:com|net)/[^"\']+)["\']', html_sample, re.IGNORECASE)
                        if an1_direct:
                            return an1_direct[0]
                        
                        extracted = extract_real_download_link_from_html(html_sample, url)
                        if extracted:
                            return extracted
        except Exception:
            pass

    # GitHub Blob
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Dropbox
    if "dropbox.com" in url:
        url = url.replace("dl=0", "dl=1")
        if "dl=1" not in url:
            url += "&dl=1" if "?" in url else "?dl=1"
        return url

    # Google Drive
    gdrive_match = re.search(r'drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([^/&?]+)', url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # DocumentaryArea
    if "documentaryarea.com" in url:
        try:
            if CURL_CFFI_AVAILABLE:
                async with CurlAsyncSession(impersonate="chrome124") as session:
                    target_page = url
                    if "player.php" in url:
                        p_resp = await session.get(url, headers=STEALTH_HEADERS, timeout=15)
                        if p_resp.status_code == 200:
                            v_match = re.search(r'href=[\'"](/video/[^\'"]+)[\'"]', p_resp.text)
                            if v_match:
                                target_page = "https://www.documentaryarea.com" + v_match.group(1)
                    
                    if "video.php" not in target_page:
                        resp = await session.get(target_page, headers=STEALTH_HEADERS, timeout=15)
                        if resp.status_code == 200:
                            m = re.search(r'video\.php\?playback=([a-zA-Z0-9]+)', resp.text)
                            if m:
                                playback_hash = m.group(1)
                                cookies = session.cookies.get_dict()
                                phpsessid = cookies.get("PHPSESSID", "")
                                doc_title = "Documentary"
                                if "/video/" in target_page:
                                    doc_title = target_page.split("/video/")[1].strip("/").replace("+", " ").replace("-", " ")
                                direct_stream = f"https://www.documentaryarea.com/video.php?playback={playback_hash}"
                                return f"{direct_stream}#ref={urllib.parse.quote(target_page)}&cookie={phpsessid}&title={urllib.parse.quote(doc_title)}"
        except Exception as e:
            logger.warning(f"documentaryarea error: {e}")

    # OK.ru / Odnoklassniki / VK Video
    if "ok.ru" in url or "odnoklassniki.ru" in url:
        try:
            clean_url = url.strip()
            if "src=" in clean_url:
                src_match = re.search(r'src=["\']([^"\']+)["\']', clean_url)
                if src_match:
                    clean_url = src_match.group(1)
            if clean_url.startswith("//"):
                clean_url = "https:" + clean_url
            if not clean_url.startswith("http"):
                clean_url = "https://" + clean_url.lstrip("/")

            m_id = re.search(r'(?:video/|videoembed/|ok\.ru/)([0-9]{8,})', clean_url)
            if m_id:
                target_ok_url = f"https://ok.ru/videoembed/{m_id.group(1)}"
            else:
                target_ok_url = clean_url

            movie_title = ""
            if CURL_CFFI_AVAILABLE:
                try:
                    async with CurlAsyncSession(impersonate="chrome124") as session:
                        ok_resp = await session.get(target_ok_url, headers=STEALTH_HEADERS, timeout=10)
                        matches = re.findall(r'data-options="([^"]+)"', ok_resp.text)
                        if matches:
                            unescaped = matches[0].replace("&quot;", '"').replace("&amp;", "&")
                            ok_data = json.loads(unescaped)
                            meta_val = ok_data.get("flashvars", {}).get("metadata", {})
                            if isinstance(meta_val, str):
                                meta_val = json.loads(meta_val)
                            movie_title = meta_val.get("movie", {}).get("title", "")
                            movie_title = re.sub(r'[\\/*?:"<>|]', "", movie_title).strip()
                except Exception:
                    pass

            title_param = f"&title={urllib.parse.quote(movie_title)}" if movie_title else ""
            return f"{target_ok_url}#ref=https://ok.ru/{title_param}"
        except Exception as ok_err:
            logger.warning(f"ok.ru extraction error: {ok_err}")

    # Catbox
    if "catbox.moe" in url:
        return url

    # فاحص عام لصفحات الويب لاستخراج مشغلات الفيديو أو روابط التنزيل المباشرة
    try:
        if CURL_CFFI_AVAILABLE:
            async with CurlAsyncSession(impersonate="chrome124") as session:
                resp = await session.get(url, headers=STEALTH_HEADERS, allow_redirects=True, stream=True)
                content_bytes = bytearray()
                async for chunk in resp.aiter_content(32 * 1024):
                    content_bytes.extend(chunk)
                    if len(content_bytes) >= 300 * 1024:
                        break
                try:
                    html_sample = content_bytes.decode("utf-8")
                    if "\ufffd" in html_sample:
                        html_sample = content_bytes.decode("cp1256", errors="ignore")
                except Exception:
                    html_sample = content_bytes.decode("cp1256", errors="ignore")

                extracted = extract_real_download_link_from_html(html_sample, url)
                if extracted:
                    return extracted
    except Exception:
        pass

    return url

# ==========================================
# 8. التنسيق المساعد وحساب الأحجام والوقت
# ==========================================
def humanbytes(size) -> str:
    if not size:
        return "0 B"
    try:
        size = float(size)
    except (ValueError, TypeError):
        return "0 B"
    if size <= 0:
        return "0 B"
    power = 1024
    n = 0
    power_labels = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels[n]}"

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

def sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename.replace("\\", "/"))
    clean = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', base).strip('. ')
    return clean or f"file_{int(time.time())}.bin"

def clean_and_rename_filename(raw_filename: str, user_id: int = 0) -> str:
    """محرك تطهير الوسوم وتعديل الأسماء الذكي (Smart Renamer & Tag Cleaner)"""
    if not raw_filename:
        return f"file_{int(time.time())}.bin"
    
    base = os.path.basename(raw_filename.replace("\\", "/"))
    name_part, ext_part = os.path.splitext(base)
    
    st = db_get_user_settings(user_id) if user_id else {}
    clean_tags = st.get("clean_tags", 1)
    prefix = st.get("custom_prefix", "")
    suffix = st.get("custom_suffix", "")
    
    # 1. إزالة الإعلانات والوسوم الدعائية تلقائياً إذا كانت مفعلة
    if clean_tags:
        tlds = r'(?:com|ru|net|org|to|io|me|site|online|store|vip|cc|xyz|app|club|info|biz)'
        # إزالة وسوم الإعلانات المحصورة بين أقواس أولاً
        name_part = re.sub(r'(?i)\[(?:TG|telegram|official|channel)[^\]]*\]', '', name_part)
        name_part = re.sub(r'(?i)\((?:TG|telegram|official|channel)[^)]*\)', '', name_part)
        name_part = re.sub(r'(?i)\{(?:TG|telegram|official|channel)[^}]*\}', '', name_part)
        # إزالة أي أقواس تحتوي على روابط أو أسماء مواقع (مثل [an1.com] أو (5play.ru))
        name_part = re.sub(r'(?i)\[[^\]]*\.' + tlds + r'[^\]]*\]', '', name_part)
        name_part = re.sub(r'(?i)\([^)]*\.' + tlds + r'[^)]*\)', '', name_part)
        name_part = re.sub(r'(?i)\{[^}]*\.' + tlds + r'[^}]*\}', '', name_part)
        # إزالة الروابط الكاملة: www.site.com, site.com, t.me/xxx, https://...
        name_part = re.sub(r'(?i)(?:https?://|www\.)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?', '', name_part)
        name_part = re.sub(r'(?i)(?:t\.me|telegram\.me)/[a-zA-Z0-9_]+', '', name_part)
        # إزالة الإشارات: @ChannelName
        name_part = re.sub(r'@[a-zA-Z0-9_]+', '', name_part)
        # ✅ إزالة نطاقات المواقع الروسية والعالمية المضمنة في أسماء الملفات (مثل: -an1.com, _5play.ru, -androeed.ru, -apkpure.com, إلخ)
        # مسبوقة بفاصل (- أو _ أو مسافة) ويليها النطاق
        name_part = re.sub(r'(?i)[-_\s]+[a-zA-Z0-9-]+\.' + tlds + r'(?:\b|$)', '', name_part)
        # حالة وجود النطاق في بداية الاسم (مثل: an1.com_Subway_Surfers)
        name_part = re.sub(r'(?i)^[a-zA-Z0-9-]+\.' + tlds + r'[-_\s.]+', '', name_part)
        # إزالة أسماء أشهر مواقع المود الشائعة إذا وجدت مفصولة حتى لو بدون امتداد
        name_part = re.sub(r'(?i)[-_\s]+(?:an1|5play|androeed|lenov|pdalife|apkmody|apkpure|rexdl|revdl|happymod|moddroid|playmods)(?=[-_\s]|$)', '', name_part)

    # 2. تطبيق قواعد الاستبدال المخصصة المحددة من المستخدم/المسؤول
    if user_id:
        try:
            rules = db_get_user_replacements(user_id)
            for f_txt, r_txt in rules:
                if f_txt and f_txt in name_part:
                    name_part = name_part.replace(f_txt, r_txt)
        except Exception:
            pass

    # 3. تطهير المسافات والرموز الزائدة
    name_part = re.sub(r'[\s_]+', ' ', name_part).strip(' .-_')
    if not name_part:
        name_part = f"file_{int(time.time())}"

    # 4. تطبيق حقوق القناة التلقائية (Auto-Branding) والبادئة واللاحقة المخصصة
    channel_tag = st.get("channel_tag", "").strip()
    brand_position = st.get("brand_position", "suffix")
    
    # تطبيق وسم القناة التلقائي إذا لم تكن هناك لاحقة/بادئة يدوية تتعارض
    if channel_tag:
        clean_tag = channel_tag if channel_tag.startswith("@") or channel_tag.startswith("http") else f"@{channel_tag}"
        if brand_position == "suffix" and not suffix:
            name_part = f"{name_part} {clean_tag}".strip()
        elif brand_position == "prefix" and not prefix:
            name_part = f"[{clean_tag}] {name_part}".strip()

    if prefix:
        name_part = f"{prefix.strip()} {name_part}".strip()
    if suffix:
        name_part = f"{name_part} {suffix.strip()}".strip()

    final_name = f"{name_part}{ext_part}"
    return sanitize_filename(final_name)

def smart_extract_filename(url: str, headers: dict) -> str:
    content_disp = headers.get("Content-Disposition", "") or headers.get("content-disposition", "")
    if content_disp:
        fn_star = re.search(r"filename\*\s*=\s*(?:UTF-8''|utf-8'')([^;\r\n]+)", content_disp, re.IGNORECASE)
        if fn_star:
            clean_star = fn_star.group(1).strip('"\'; ')
            if clean_star:
                return sanitize_filename(urllib.parse.unquote(clean_star))

        fn_match = re.search(r'filename\s*=\s*("([^"]+)"|([^;\r\n]+))', content_disp, re.IGNORECASE)
        if fn_match:
            filename = (fn_match.group(2) or fn_match.group(3) or "").strip('"\'; ')
            if filename:
                return sanitize_filename(urllib.parse.unquote(filename))
    
    parsed = urllib.parse.urlparse(url)
    if "okcdn.ru" in url:
        return f"video_{int(time.time())}.mp4"
    filename = os.path.basename(parsed.path)
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
        "application/vnd.android.package-archive": ".apk",
        "text/plain": ".txt",
        "text/html": ".html"
    }

    if filename:
        clean_fn = urllib.parse.unquote(filename).strip()
        if clean_fn:
            if "." in clean_fn:
                if clean_fn.lower().endswith((".php", ".asp", ".aspx", ".jsp", ".bin", ".cgi")):
                    if "video/mp4" in ctype or "video" in ctype:
                        base = os.path.splitext(clean_fn)[0]
                        return sanitize_filename(f"{base}.mp4" if base != "video" else f"video_{int(time.time())}.mp4")
                    elif "application/vnd.android.package-archive" in ctype:
                        return sanitize_filename(f"{os.path.splitext(clean_fn)[0]}.apk")
                else:
                    return sanitize_filename(clean_fn)
            else:
                return sanitize_filename(clean_fn)

    for mime, ext in ext_map.items():
        if mime in ctype:
            return sanitize_filename(f"download_{int(time.time())}{ext}")

    return f"file_{int(time.time())}.bin"

def parse_chat_id(chat_id_raw):
    if not chat_id_raw:
        return None
    chat_id_str = str(chat_id_raw).strip()
    if (chat_id_str.startswith("-") and chat_id_str[1:].isdigit()) or chat_id_str.isdigit():
        return int(chat_id_str)
    return chat_id_str

def make_start_keyboard(lang: str = "ar", is_admin: bool = False):
    buttons = [
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
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("👑 لوحة المسؤول (Admin Panel)", callback_data="btn_admin_panel")])
    return InlineKeyboardMarkup(buttons)

def make_settings_keyboard(user_id: int):
    st = db_get_user_settings(user_id)
    lang = st["lang"]
    mode_str = tr(lang, "btn_mode_auto") if st["upload_mode"] == "auto" else tr(lang, "btn_mode_doc")
    threads_str = tr(lang, "btn_threads", threads=st['god_threads'])
    lang_btn_str = "🌐 اللغة: 🇸🇦 العربية" if lang == "ar" else "🌐 Language: 🇺🇸 English"
    caption_str = tr(lang, "btn_caption_on") if st.get("enable_caption", 1) else tr(lang, "btn_caption_off")
    thumbs_str = tr(lang, "btn_thumbs_on") if st.get("enable_thumbs", 1) else tr(lang, "btn_thumbs_off")
    clean_str = tr(lang, "btn_cleantags_on") if st.get("clean_tags", 1) else tr(lang, "btn_cleantags_off")
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang_btn_str, callback_data="toggle_lang")],
        [InlineKeyboardButton(mode_str, callback_data="toggle_mode")],
        [InlineKeyboardButton(threads_str, callback_data="toggle_threads")],
        [InlineKeyboardButton(caption_str, callback_data="toggle_caption"), InlineKeyboardButton(thumbs_str, callback_data="toggle_thumbs")],
        [InlineKeyboardButton(clean_str, callback_data="toggle_cleantags")],
        [InlineKeyboardButton("👑 حقوق القناة (Auto-Branding)", callback_data="btn_open_brand")],
        [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]
    ])

def make_brand_keyboard(user_id: int):
    st = db_get_user_settings(user_id)
    b_pos = st.get("brand_position", "suffix")
    pos_desc = "في النهاية (Suffix)" if b_pos == "suffix" else ("في البداية (Prefix)" if b_pos == "prefix" else "معطل ❌")
    pos_text = f"🏷️ موضع الاسم: {pos_desc}"
    btn_state = "🔘 زر القناة بالملف: مفعل ✅" if st.get("channel_button", 1) else "🔘 زر القناة بالملف: معطل ❌"
    cur_ch = st.get("channel_tag") or "غير محدد ❌"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 القناة: {cur_ch}", callback_data="btn_brand_help")],
        [InlineKeyboardButton(pos_text, callback_data="toggle_brand_pos")],
        [InlineKeyboardButton(btn_state, callback_data="toggle_brand_btn")],
        [InlineKeyboardButton("🗑️ مسح القناة والحقوق", callback_data="btn_clear_brand")],
        [InlineKeyboardButton("🔙 العودة للإعدادات", callback_data="btn_settings")]
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
    
    while len(last_update) < 3:
        last_update.append(0)
        
    last_time = last_update[0]
    last_bytes = last_update[1]
    
    if current != total and last_time > 0 and (now - last_time) < 2.5:
        return

    time_delta = now - last_time if last_time > 0 else (now - start_time)
    bytes_delta = current - last_bytes if last_bytes > 0 else current

    instant_speed = bytes_delta / time_delta if time_delta > 0 else 0
    if instant_speed <= 0:
        overall_diff = now - start_time
        instant_speed = current / overall_diff if overall_diff > 0 else 0

    last_update[0] = now
    last_update[1] = current
    last_update[2] = instant_speed

    speed = instant_speed
    percentage = (current * 100 / total) if total else 0
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
        await asyncio.sleep(e.value + 1)
    except (RPCError, MessageNotModified):
        pass

# ==========================================
# 9. معالجات الرسائل والأوامر المزدوجة
# ==========================================
@bot.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        await message.reply_text("⛔ <b>عذراً، هذا البوت خاص ومخصص للاستخدام الشخصي للمالك فقط.</b>", parse_mode=ParseMode.HTML)
        return
    db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    st = db_get_user_settings(user_id)
    sender = message.from_user.first_name if message.from_user else 'Master'
    is_admin_user = is_admin(user_id)
    
    welcome_text = tr(st["lang"], "welcome", name=sender)
    try:
        await message.reply_text(welcome_text, reply_markup=make_start_keyboard(st["lang"], is_admin=is_admin_user), parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await message.reply_text(welcome_text, reply_markup=make_start_keyboard(st["lang"], is_admin=is_admin_user), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("god") | filters.command("godmode") | filters.command("omnipotent"))
async def god_panel_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    st = db_get_user_settings(user_id)
    g_stats = db_get_global_stats()
    
    god_card = tr(st["lang"], "god_panel", threads=st['god_threads'], files=g_stats['files'], bytes=humanbytes(g_stats['bytes']))
    try:
        await message.reply_text(god_card, reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await message.reply_text(god_card, reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("probe"))
async def probe_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    st = db_get_user_settings(user_id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("❌ URL required: <code>/probe URL</code>", parse_mode=ParseMode.HTML)
        return
    
    raw_url = args[1].strip()
    status_msg = await message.reply_text("🔎 <b>Inspecting URL / جاري الفحص...</b>", parse_mode=ParseMode.HTML)
    
    try:
        direct_url = await unrestrict_direct_link(raw_url)
        custom_cookie = ""
        referer_header = ""
        if "#" in direct_url:
            base_part, fragment_part = direct_url.split("#", 1)
            direct_url = base_part
            params = urllib.parse.parse_qs(fragment_part)
            if "ref" in params:
                referer_header = params["ref"][0]
            if "cookie" in params and params["cookie"][0]:
                custom_cookie = f"PHPSESSID={params['cookie'][0]}"

        parsed_url = urllib.parse.urlparse(direct_url)
        if not referer_header:
            referer_header = "https://an1.com/" if ("an1.net" in direct_url or "an1.com" in direct_url) else f"{parsed_url.scheme}://{parsed_url.netloc}/"

        if CURL_CFFI_AVAILABLE:
            headers = {**STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
            if custom_cookie:
                headers["Cookie"] = custom_cookie
            async with CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                resp = await session.get(direct_url, headers=headers, stream=True)
                status = resp.status_code
                clen = resp.headers.get("Content-Length") or resp.headers.get("content-length") or ""
                crange = resp.headers.get("Content-Range") or resp.headers.get("content-range") or ""
                if "/" in crange:
                    clen = crange.split("/")[1].strip()
                if not clen:
                    clen = "N/A"
                ctype = resp.headers.get("Content-Type") or resp.headers.get("content-type") or "N/A"
                fname = smart_extract_filename(direct_url, resp.headers)
        else:
            timeout = aiohttp.ClientTimeout(total=15, sock_connect=10)
            headers = {**STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
            if custom_cookie:
                headers["Cookie"] = custom_cookie
            async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                async with session.get(direct_url, headers=headers, allow_redirects=True) as resp:
                    status = resp.status
                    clen = resp.headers.get("Content-Length") or resp.headers.get("content-length") or ""
                    crange = resp.headers.get("Content-Range") or resp.headers.get("content-range") or ""
                    if "/" in crange:
                        clen = crange.split("/")[1].strip()
                    if not clen:
                        clen = "N/A"
                    ctype = resp.headers.get("Content-Type") or resp.headers.get("content-type") or "N/A"
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
    if not is_admin(user_id):
        return
    st = db_get_user_settings(user_id)
    await message.reply_text(
        tr(st["lang"], "settings_title"),
        reply_markup=make_settings_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command("help"))
async def help_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    st = db_get_user_settings(user_id)
    await message.reply_text(tr(st["lang"], "help_text"), reply_markup=make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("stats"))
async def stats_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
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
    if not is_admin(user_id):
        return
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

@bot.on_message(filters.command("broadcast"))
async def broadcast_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        await message.reply_text("⛔ <b>عذراً، هذا الأمر مخصص للمسؤول فقط!</b>", parse_mode=ParseMode.HTML)
        return

    broadcast_msg = message.reply_to_message
    broadcast_text = ""
    if not broadcast_msg:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "📢 <b>طريقة استخدام الإذاعة:</b>\n\n"
                "• <code>/broadcast نص الرسالة هنا</code>\n"
                "• أو قم بالرد بأمر <code>/broadcast</code> على أي رسالة أو وسائط لنشرها.",
                parse_mode=ParseMode.HTML
            )
            return
        broadcast_text = args[1].strip()

    status_msg = await message.reply_text("⏳ <b>جاري بدء الإذاعة لجميع المستخدمين...</b>", parse_mode=ParseMode.HTML)
    user_ids = db_get_all_user_ids()
    total_users = len(user_ids)
    success_count = 0
    failed_count = 0

    for uid in user_ids:
        try:
            if broadcast_msg:
                await broadcast_msg.copy(chat_id=uid)
            else:
                await client.send_message(chat_id=uid, text=broadcast_text, parse_mode=ParseMode.HTML)
            success_count += 1
            await asyncio.sleep(0.05)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            try:
                if broadcast_msg:
                    await broadcast_msg.copy(chat_id=uid)
                else:
                    await client.send_message(chat_id=uid, text=broadcast_text, parse_mode=ParseMode.HTML)
                success_count += 1
            except Exception:
                failed_count += 1
        except Exception:
            failed_count += 1

    report = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>تقرير الإذاعة العامة:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>إجمالي المستخدمين:</b> <code>{total_users}</code>\n"
        f"✅ <b>تم الإرسال بنجاح:</b> <code>{success_count}</code>\n"
        f"❌ <b>فشل الإرسال:</b> <code>{failed_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("dashboard"))
async def dashboard_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        await message.reply_text("⛔ <b>عذراً، لوحة تحكم الويب مخصصة لمالك البوت فقط!</b>", parse_mode=ParseMode.HTML)
        return
    dash_url = f"http://localhost:{PORT}/dashboard?key={DASHBOARD_SECRET}"
    card = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>لوحة تحكم ومراقبة السيرفر الحية (Web Dashboard)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>رابط الدخول المباشر:</b>\n"
        f"<code>{dash_url}</code>\n\n"
        f"🔑 <b>مفتاح الأمان السري (Secret Key):</b>\n"
        f"<code>{DASHBOARD_SECRET}</code>\n\n"
        f"💡 <i>ملاحظة: إذا كان البوت على خادم خارجي، استبدل localhost بعنوان IP أو دومين السيرفر.</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(
        card,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 فتح اللوحة في المتصفح", url=dash_url)]]),
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command(["set_prefix", "prefix"]))
async def set_prefix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("🏷️ <b>الاستخدام:</b> <code>/set_prefix [بادئة الاسم]</code>\nمثال: <code>/set_prefix @MyChannel -</code>", parse_mode=ParseMode.HTML)
        return
    new_prefix = args[1].strip()
    db_update_user_setting(user_id, "custom_prefix", new_prefix)
    await message.reply_text(f"✅ <b>تم ضبط البادئة المخصصة بنجاح:</b> <code>{new_prefix}</code>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command(["clear_prefix", "cleanprefix"]))
async def clear_prefix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    db_update_user_setting(user_id, "custom_prefix", "")
    await message.reply_text("✅ <b>تم حذف البادئة المخصصة بنجاح.</b>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command(["set_suffix", "suffix"]))
async def set_suffix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("🏷️ <b>الاستخدام:</b> <code>/set_suffix [لاحقة الاسم]</code>\nمثال: <code>/set_suffix - @MyChannel</code>", parse_mode=ParseMode.HTML)
        return
    new_suffix = args[1].strip()
    db_update_user_setting(user_id, "custom_suffix", new_suffix)
    await message.reply_text(f"✅ <b>تم ضبط اللاحقة المخصصة بنجاح:</b> <code>{new_suffix}</code>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command(["clear_suffix", "cleansuffix"]))
async def clear_suffix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    db_update_user_setting(user_id, "custom_suffix", "")
    await message.reply_text("✅ <b>تم حذف اللاحقة المخصصة بنجاح.</b>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("replace"))
async def replace_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    args = message.text.replace("/replace", "", 1).strip()
    if "|" not in args:
        await message.reply_text(
            "🔄 <b>أداة استبدال النصوص والوسوم في أسماء الملفات:</b>\n\n"
            "• <code>/replace النص_القديم | النص_الجديد</code>\n"
            "• لحذف كلمة معينة: <code>/replace الكلمة | </code>\n"
            "• مثال: <code>/replace [TG:@AdChannel] | </code>",
            parse_mode=ParseMode.HTML
        )
        return
    parts = [p.strip() for p in args.split("|", 1)]
    find_txt = parts[0]
    replace_txt = parts[1] if len(parts) > 1 else ""
    if not find_txt:
        await message.reply_text("❌ <b>النص المراد استبداله لا يمكن أن يكون فارغاً!</b>", parse_mode=ParseMode.HTML)
        return
    db_add_replacement(user_id, find_txt, replace_txt)
    action_text = "بحذفه" if not replace_txt else f"بـ <code>{replace_txt}</code>"
    await message.reply_text(f"✅ <b>تمت إضافة قاعدة الاستبدال:</b> استبدال <code>{find_txt}</code> {action_text}", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command(["replacements", "rules"]))
async def list_replacements_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    rules = db_get_user_replacements(user_id)
    st = db_get_user_settings(user_id)
    clean_state = "✅ مفعل" if st.get("clean_tags", 1) else "❌ معطل"
    prefix = st.get("custom_prefix", "") or "لا يوجد"
    suffix = st.get("custom_suffix", "") or "لا يوجد"
    
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ <b>إعدادات تعديل الأسماء وتطهير الوسوم:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 <b>تنظيف الوسوم الإعلانية:</b> <code>{clean_state}</code>\n"
        f"🏷️ <b>البادئة الحالية:</b> <code>{prefix}</code>\n"
        f"🏷️ <b>اللاحقة الحالية:</b> <code>{suffix}</code>\n\n"
        f"📋 <b>قواعد الاستبدال المخصصة ({len(rules)}):</b>\n"
    )
    if not rules:
        text += "<i>لا توجد قواعد استبدال مخصصة بعد.</i>\n"
    else:
        for i, (f_txt, r_txt) in enumerate(rules, 1):
            repl_disp = f"'{r_txt}'" if r_txt else "[حذف]"
            text += f"{i}. <code>{f_txt}</code> ➔ <code>{repl_disp}</code>\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>لحذف جميع القواعد: <code>/clear_replacements</code></i>"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@bot.on_message(filters.command("clear_replacements"))
async def clear_replacements_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    db_clear_user_replacements(user_id)
    await message.reply_text("✅ <b>تم مسح جميع قواعد استبدال النصوص الخاصة بك بنجاح.</b>", parse_mode=ParseMode.HTML)

@bot.on_message(filters.command(["brand", "branding", "set_brand", "set_channel", "channel"]))
async def brand_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        new_brand = args[1].strip()
        if not new_brand.startswith("@") and not new_brand.startswith("http"):
            new_brand = f"@{new_brand}"
        db_update_user_setting(user_id, "channel_tag", new_brand)
        await message.reply_text(
            f"👑 <b>تم تفعيل حقوق القناة التلقائية بنجاح! (Auto-Branding)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>القناة المعتمدة:</b> <code>{new_brand}</code>\n"
            f"🏷️ <b>الموضع في الاسم:</b> <code>في النهاية (Suffix)</code>\n"
            f"🔘 <b>الزر التفاعلي بالقناة:</b> <code>مفعل ✅</code>\n"
            f"📝 <b>الحقوق في الكابشن:</b> <code>مفعلة ✅</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>أي لعبة أو ملف تحمله الآن سيحمل حقوق قناتك تلقائياً!</i>\n"
            f"لإدارة خيارات العرض أرسل أمر <code>/brand</code> في أي وقت.",
            reply_markup=make_brand_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
        return
    
    st = db_get_user_settings(user_id)
    cur_brand = st.get("channel_tag") or "غير محدد ❌"
    await message.reply_text(
        f"👑 <b>لوحة إدارة حقوق القناة التلقائية (Auto-Branding):</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>القناة الحالية:</b> <code>{cur_brand}</code>\n\n"
        f"💡 <b>طريقة الاستخدام السريع:</b>\n"
        f"• لتعيين القناة: <code>/brand @اسم_قناتك</code>\n"
        f"• لحذف الحقوق: <code>/clear_brand</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"تحكم في كيفية ظهور حقوق قناتك عبر الأزرار أدناه:",
        reply_markup=make_brand_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command(["clear_brand", "clear_channel"]))
async def clear_brand_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
    db_update_user_setting(user_id, "channel_tag", "")
    await message.reply_text("✅ <b>تم حذف حقوق القناة التلقائية بنجاح. ستنزل الملفات بدون وسم القناة.</b>", parse_mode=ParseMode.HTML)

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        user_id = query.from_user.id if query.from_user else 0
        if not is_admin(user_id):
            await query.answer("⛔ ليس لديك صلاحية لاستخدام هذا البوت.", show_alert=True)
            return
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

        elif data == "toggle_caption":
            new_val = 0 if st.get("enable_caption", 1) else 1
            db_update_user_setting(user_id, "enable_caption", new_val)
            await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
            await query.answer("Caption preference updated!")
            return

        elif data == "toggle_thumbs":
            new_val = 0 if st.get("enable_thumbs", 1) else 1
            db_update_user_setting(user_id, "enable_thumbs", new_val)
            await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
            await query.answer("Thumbnail preference updated!")
            return

        elif data == "toggle_cleantags":
            new_val = 0 if st.get("clean_tags", 1) else 1
            db_update_user_setting(user_id, "clean_tags", new_val)
            await query.message.edit_reply_markup(reply_markup=make_settings_keyboard(user_id))
            await query.answer("Tag cleaner updated / تم تحديث تفضيل تنظيف الوسوم!")
            return

        elif data == "btn_open_brand":
            st = db_get_user_settings(user_id)
            cur_brand = st.get("channel_tag") or "غير محدد ❌"
            await query.message.edit_text(
                f"👑 <b>لوحة إدارة حقوق القناة التلقائية (Auto-Branding):</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 <b>القناة الحالية:</b> <code>{cur_brand}</code>\n\n"
                f"💡 <b>طريقة التعيين:</b>\n"
                f"أرسل أمر: <code>/brand @اسم_قناتك</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"تحكم في كيفية ظهور حقوق قناتك عبر الأزرار أدناه:",
                reply_markup=make_brand_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
            return

        elif data == "btn_brand_help":
            await query.answer("لتغيير القناة، أرسل الأمر: /brand @اسم_قناتك", show_alert=True)
            return

        elif data == "toggle_brand_pos":
            pos_modes = ["suffix", "prefix", "none"]
            cur_pos = st.get("brand_position", "suffix")
            new_pos = pos_modes[(pos_modes.index(cur_pos) + 1) % len(pos_modes)] if cur_pos in pos_modes else "suffix"
            db_update_user_setting(user_id, "brand_position", new_pos)
            await query.message.edit_reply_markup(reply_markup=make_brand_keyboard(user_id))
            await query.answer(f"تم تغيير موضع الاسم إلى: {new_pos}!")
            return

        elif data == "toggle_brand_btn":
            new_val = 0 if st.get("channel_button", 1) else 1
            db_update_user_setting(user_id, "channel_button", new_val)
            await query.message.edit_reply_markup(reply_markup=make_brand_keyboard(user_id))
            await query.answer("تم تحديث حالة زر القناة التفاعلي!")
            return

        elif data == "btn_clear_brand":
            db_update_user_setting(user_id, "channel_tag", "")
            await query.message.edit_reply_markup(reply_markup=make_brand_keyboard(user_id))
            await query.answer("تم حذف وسم القناة!", show_alert=True)
            return

        elif data == "btn_settings":
            await query.message.edit_text(
                tr(st["lang"], "settings_title"),
                reply_markup=make_settings_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
            return

        if data == "btn_start":
            sender = query.from_user.first_name if query.from_user else 'Master'
            is_admin_user = is_admin(user_id)
            await query.message.edit_text(tr(lang, "welcome", name=sender), reply_markup=make_start_keyboard(lang, is_admin=is_admin_user), parse_mode=ParseMode.HTML)

        elif data == "btn_admin_panel":
            if not is_admin(user_id):
                await query.answer("⛔ هذا القسم مخصص لمالك البوت فقط!", show_alert=True)
                return
            g_stats = db_get_global_stats()
            queue_size = request_queue.qsize()
            uptime_sec = int(time.time() - START_TIME)
            admin_card = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 <b>لوحة تحكم المسؤول (Admin Panel)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 <b>إجمالي المستخدمين المسجلين:</b> <code>{g_stats['users']} مستخدم</code>\n"
                f"📄 <b>إجمالي الملفات المعالجة:</b> <code>{g_stats['files']}</code>\n"
                f"📊 <b>إجمالي حجم البيانات:</b> <code>{humanbytes(g_stats['bytes'])}</code>\n"
                f"⏳ <b>حجم طابور المعالجة الحالي:</b> <code>{queue_size}</code>\n"
                f"⏱️ <b>مدة تشغيل السيرفر (Uptime):</b> <code>{time_formatter(uptime_sec)}</code>\n\n"
                f"📢 <b>للإذاعة العامة لجميع المستخدمين:</b>\n"
                f"<code>/broadcast نص الرسالة هنا</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            admin_kbd = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 فتح لوحة مراقبة الويب (Web Dashboard)", callback_data="btn_get_dashboard")],
                [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]
            ])
            await query.message.edit_text(admin_card, reply_markup=admin_kbd, parse_mode=ParseMode.HTML)

        elif data == "btn_get_dashboard":
            if not is_admin(user_id):
                await query.answer("⛔ هذا القسم مخصص لمالك البوت فقط!", show_alert=True)
                return
            dash_url = f"http://localhost:{PORT}/dashboard?key={DASHBOARD_SECRET}"
            card = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>لوحة تحكم ومراقبة السيرفر الحية (Web Dashboard)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>رابط الدخول المباشر:</b>\n"
                f"<code>{dash_url}</code>\n\n"
                f"🔑 <b>مفتاح الأمان السري (Key):</b>\n"
                f"<code>{DASHBOARD_SECRET}</code>\n\n"
                f"💡 <i>ملاحظة: إذا كان البوت على استضافة خارجية، استبدل localhost برابط السيرفر.</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await query.message.reply_text(
                card,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 فتح اللوحة في المتصفح", url=dash_url)]]),
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return

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
    except MessageNotModified:
        try:
            await query.answer()
        except Exception:
            pass
    except Exception as cb_err:
        logger.warning(f"Callback query handler notice: {cb_err}")

# ==========================================
# 10. استقبال وتجهيز المستندات والتورينت (.torrent Document)
# ==========================================
@bot.on_message(filters.document & ~filters.service)
async def handle_document_torrent(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return
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
    if not is_admin(user_id):
        return
    if user_id:
        db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")

    msg_time = message.date.timestamp() if message.date else 0
    if msg_time and (time.time() - msg_time) > 300:
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        return

    if text.startswith("/"):
        if text.startswith("/eval"):
            if not is_admin(user_id):
                await message.reply_text("⛔ <b>غير مصرح لك باستخدام هذا الأمر! (Admin Only)</b>", parse_mode=ParseMode.HTML)
                return
            code = text.replace("/eval", "", 1).strip()
            try:
                res = eval(code)
                await message.reply_text(f"💻 <b>Eval Result:</b>\n<code>{res}</code>", parse_mode=ParseMode.HTML)
            except Exception as e:
                await message.reply_text(f"❌ <b>Eval Error:</b>\n<code>{e}</code>", parse_mode=ParseMode.HTML)
            return
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

async def handle_queued_task(task_data):
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
        logger.exception(f"Task error: {e}")
    finally:
        request_queue.task_done()
        gc.collect()

async def queue_worker():
    while True:
        task_data = await request_queue.get()
        asyncio.create_task(handle_queued_task(task_data))

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
        gc.collect()

async def process_single_local_file_upload(file_path: str, filename: str, actual_file_size: int, status_msg: Message, user_msg: Message, user_id: int, start_time: float, task_id: str):
    settings = db_get_user_settings(user_id)
    lang = settings["lang"]
    filename = clean_and_rename_filename(filename, user_id=user_id)
    if task_id in ACTIVE_TASKS: ACTIVE_TASKS[task_id]["filename"] = filename
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

    caption, brand_markup = build_file_caption(filename, actual_file_size, category_desc, icon, user_id)
    
    thumb_path = None
    duration, width, height = 0, 0, 0
    if force_video and settings.get("enable_thumbs", 1):
        thumb_path, duration, width, height = await extract_video_metadata(file_path)

    try:
        if force_video:
            kwargs = {
                "video": file_path,
                "caption": caption,
                "supports_streaming": True,
                "progress": pyrogram_progress,
                "parse_mode": ParseMode.HTML
            }
            if brand_markup: kwargs["reply_markup"] = brand_markup
            if thumb_path and os.path.exists(thumb_path): kwargs["thumb"] = thumb_path
            if duration > 0: kwargs["duration"] = duration
            if width > 0 and height > 0:
                kwargs["width"] = width
                kwargs["height"] = height
            await user_msg.reply_video(**kwargs)
        else:
            kwargs = {
                "document": file_path,
                "caption": caption,
                "progress": pyrogram_progress,
                "parse_mode": ParseMode.HTML
            }
            if brand_markup: kwargs["reply_markup"] = brand_markup
            await user_msg.reply_document(**kwargs)
    finally:
        if thumb_path and os.path.exists(thumb_path):
            try: os.remove(thumb_path)
            except Exception: pass
        
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
    bundle_uid = user_msg.from_user.id if user_msg.from_user else 0
    
    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for idx, (raw_url, cname, _) in enumerate(valid_requests, 1):
                await status_msg.edit_text(f"📦 <b>Downloading file {idx}/{len(valid_requests)} for ZIP bundle...</b>", parse_mode=ParseMode.HTML)
                direct_url = await unrestrict_direct_link(raw_url)
                parsed_url = urllib.parse.urlparse(direct_url)
                referer_header = "https://an1.com/" if ("an1.net" in direct_url or "an1.com" in direct_url) else f"{parsed_url.scheme}://{parsed_url.netloc}/"
                
                if CURL_CFFI_AVAILABLE:
                    headers = {**STEALTH_HEADERS, "Referer": referer_header}
                    async with CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                        resp = await session.get(direct_url, headers=headers, stream=True)
                        raw_fn = cname or smart_extract_filename(direct_url, resp.headers)
                        fname = clean_and_rename_filename(raw_fn, user_id=bundle_uid)
                        base_fn, ext_fn = os.path.splitext(fname)
                        counter = 1
                        temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                        while temp_fpath in downloaded_files or os.path.exists(temp_fpath):
                            fname = f"{base_fn}_{counter}{ext_fn}"
                            temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                            counter += 1
                        with open(temp_fpath, "wb") as f:
                            async for chunk in resp.aiter_content(1024 * 1024):
                                if chunk: f.write(chunk)
                        zip_file.write(temp_fpath, arcname=fname)
                        downloaded_files.append(temp_fpath)
                else:
                    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
                    headers = {**STEALTH_HEADERS, "Referer": referer_header}
                    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                        async with session.get(direct_url, headers=headers, allow_redirects=True) as resp:
                            if resp.status == 200:
                                raw_fn = cname or smart_extract_filename(direct_url, resp.headers)
                                fname = clean_and_rename_filename(raw_fn, user_id=bundle_uid)
                                base_fn, ext_fn = os.path.splitext(fname)
                                counter = 1
                                temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                                while temp_fpath in downloaded_files or os.path.exists(temp_fpath):
                                    fname = f"{base_fn}_{counter}{ext_fn}"
                                    temp_fpath = os.path.join(DOWNLOAD_DIR, fname)
                                    counter += 1
                                with open(temp_fpath, "wb") as f:
                                    async for chunk in resp.content.iter_chunked(1024 * 1024):
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
        gc.collect()

def is_speed_throttled_url(url: str) -> bool:
    """فحص ما إذا كان الرابط يخضع لسقف سرعة محدد من السيرفر (أقل من 1 ميجابايت)"""
    url_lower = url.lower()
    throttled_params = ["max=", "speed=", "limit=", "rate=", "throttle=", "capped="]
    if any(param in url_lower for param in throttled_params):
        return True
    
    throttled_domains = [
        "upfiles.download", "upfiles.com", "uploadhaven.com",
        "rapidgator.net", "1fichier.com", "filerio.in", "dropgalaxy.in",
        "katfile.com", "turbobit.net", "nitroflare.com", "pixeldrain.com",
        "downet.net", "akwam"
    ]
    parsed_netloc = urllib.parse.urlparse(url).netloc.lower()
    if any(domain in parsed_netloc for domain in throttled_domains):
        return True
        
    return False

async def download_multi_stream_turbo(
    direct_url: str,
    file_path: str,
    total_size: int,
    headers: dict,
    status_msg: Message,
    task_id: str,
    lang: str,
    dl_start_time: float,
    last_update: list,
    num_connections: int = 64
) -> bool:
    """محرك تنزيل ديناميكي فائق مع تسريع نهاية التحميل (Dynamic Micro-Blocks & End-Game Hedging) لمنع أي تباطؤ عند 99%"""
    if total_size <= 0:
        return False

    # كتل متوازنة ديناميكياً (512KB - 2MB) لضمان أقصى سرعة نقل وتفادي التباطؤ
    if total_size > 1024 * 1024 * 1024:
        concurrency = min(num_connections, 64)
        block_size = 2 * 1024 * 1024
    elif total_size > 200 * 1024 * 1024:
        concurrency = min(num_connections, 48)
        block_size = 1024 * 1024
    else:
        concurrency = min(num_connections, 32)
        block_size = 512 * 1024

    blocks = []
    current_byte = 0
    b_id = 0
    while current_byte < total_size:
        end_byte = min(current_byte + block_size - 1, total_size - 1)
        blocks.append((b_id, current_byte, end_byte))
        b_id += 1
        current_byte = end_byte + 1

    total_blocks_count = len(blocks)
    block_queue = asyncio.Queue()
    for b in blocks:
        block_queue.put_nowait(b)

    status_tracker = {"downloaded": 0}
    completed_blocks = set()
    in_flight = {}
    lock = asyncio.Lock()

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.seek(total_size - 1)
            f.write(b"\0")
    except Exception as e:
        logger.warning(f"Pre-allocate failed: {e}")
        return False

    try:
        file_handle = open(file_path, "r+b")
    except Exception as e:
        logger.warning(f"Failed to open file handle: {e}")
        return False

    async def fetch_block(b_id: int, start_byte: int, end_byte: int, session: aiohttp.ClientSession):
        if b_id in completed_blocks or ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            return False
        
        req_headers = {**headers, "Range": f"bytes={start_byte}-{end_byte}"}
        expected_len = end_byte - start_byte + 1
        
        try:
            b_timeout = aiohttp.ClientTimeout(total=15, sock_connect=5, sock_read=10)
            async with session.get(direct_url, headers=req_headers, timeout=b_timeout, allow_redirects=True, ssl=False) as resp:
                if resp.status == 206:
                    block_data = await resp.read()
                    if len(block_data) == expected_len and b_id not in completed_blocks:
                        async with lock:
                            if b_id not in completed_blocks:
                                file_handle.seek(start_byte)
                                file_handle.write(block_data)
                                completed_blocks.add(b_id)
                                in_flight.pop(b_id, None)
                                status_tracker["downloaded"] += len(block_data)
                                
                        await progress_bar(
                            status_tracker["downloaded"],
                            total_size,
                            f"🚀 Turbo ({concurrency}x)",
                            status_msg,
                            dl_start_time,
                            last_update,
                            icon="⚡",
                            task_id=task_id,
                            lang=lang
                        )
                        return True
                elif resp.status == 429:
                    await asyncio.sleep(0.5)
        except Exception:
            pass
        return False

    async def worker_loop(worker_id: int, session: aiohttp.ClientSession):
        while len(completed_blocks) < total_blocks_count:
            if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                return False

            b_id = -1
            start_byte = 0
            end_byte = 0

            try:
                b_id, start_byte, end_byte = block_queue.get_nowait()
            except asyncio.QueueEmpty:
                candidate = None
                now = time.time()
                for pending_id, (p_start, p_end, p_time) in list(in_flight.items()):
                    if pending_id not in completed_blocks:
                        if candidate is None or p_time < candidate[3]:
                            candidate = (pending_id, p_start, p_end, p_time)

                if candidate:
                    b_id, start_byte, end_byte, _ = candidate
                else:
                    await asyncio.sleep(0.05)
                    continue

            if b_id in completed_blocks:
                continue

            in_flight[b_id] = (start_byte, end_byte, time.time())
            success = await fetch_block(b_id, start_byte, end_byte, session)

            if not success and b_id not in completed_blocks:
                await block_queue.put((b_id, start_byte, end_byte))
                await asyncio.sleep(0.1)

        return True

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=20)
    connector = aiohttp.TCPConnector(limit=concurrency + 20, limit_per_host=concurrency + 10, keepalive_timeout=30, ssl=False)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            workers = [asyncio.create_task(worker_loop(i, session)) for i in range(concurrency)]
            
            while len(completed_blocks) < total_blocks_count:
                if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    for w in workers:
                        w.cancel()
                    return False
                await asyncio.sleep(0.1)

            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
    finally:
        try:
            file_handle.flush()
            file_handle.close()
        except Exception:
            pass

    if os.path.exists(file_path) and os.path.getsize(file_path) == total_size:
        logger.info(f"✅ Turbo with End-Game Hedging finished {file_path} ({humanbytes(total_size)}) instantly to 100%!")
        return True

    return False

def is_hls_or_video_stream(url: str) -> bool:
    """فحص ما إذا كان الرابط هو رابط بث مباشر m3u8 أو مشغل فيديو ويب"""
    url_lower = url.lower()
    if ".m3u8" in url_lower or ".mpd" in url_lower:
        return True
    
    video_hosts = [
        "hgcloud.to", "hglink.to", "dood.", "doodstream", "vidtube",
        "streamtape", "mixdrop", "mp4upload", "vidoza", "streamwish",
        "filelions", "dropload", "streamvid", "minochinos.com",
        "youtube.com", "youtu.be", "twitter.com", "x.com", "tiktok.com",
        "facebook.com", "fb.watch", "instagram.com", "ok.ru", "odnoklassniki.ru", "vk.com",
        "vidspeed", "voe.sx", "uqload", "yourupload", "ds2play", "okcdn.ru", "mycdn.me"
    ]
    parsed_netloc = urllib.parse.urlparse(url).netloc.lower()
    return any(host in parsed_netloc for host in video_hosts)

async def get_ok_direct_mp4(embed_or_video_url: str) -> tuple:
    """استخراج رابط MP4 المباشر عالي السرعة من سيرفرات OK.ru مع حساب حجم الملف بدقة دون استهلاك الباقة"""
    m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/|ok\.ru/)([0-9]{8,})', embed_or_video_url)
    clean_embed = f"https://ok.ru/videoembed/{m_ok.group(1)}" if m_ok else embed_or_video_url
    
    headers = {**STEALTH_HEADERS, "Referer": "https://ok.ru/"}
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=12)) as session:
        async with session.get(clean_embed, headers=headers) as resp:
            if resp.status != 200:
                return None, None, 0
            text = await resp.text(errors="ignore")
            m = re.search(r'data-options=(["\'])(.*?)\1', text)
            if not m:
                return None, None, 0
            try:
                raw_opts = json.loads(html.unescape(m.group(2)))
            except Exception:
                return None, None, 0
            meta = raw_opts.get("flashvars", {}).get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            
            movie_title = meta.get("movie", {}).get("title", "") if isinstance(meta, dict) else ""
            videos = meta.get("videos", []) if isinstance(meta, dict) else []
            
            # ترتيب الجودات من الأعلى إلى الأدنى لاختيار أفضل نسخة MP4 تدعم التيربو
            q_prio = ["ultra", "quad", "full", "hd", "sd", "low", "lowest", "mobile"]
            direct_url = None
            for q in q_prio:
                for v in videos:
                    if v.get("name") == q and v.get("url"):
                        direct_url = v.get("url")
                        break
                if direct_url:
                    break
            if not direct_url and videos:
                direct_url = videos[0].get("url")
                
            if not direct_url:
                return None, movie_title, 0
                
            # فحص حجم الملف الفعلي عبر طلب Range خفيف (1KB) دون استهلاك الباقة
            probe_headers = {
                "User-Agent": STEALTH_HEADERS["User-Agent"],
                "Referer": "https://ok.ru/",
                "Range": "bytes=0-1024"
            }
            try:
                async with session.get(direct_url, headers=probe_headers, ssl=False) as p_resp:
                    total_size = 0
                    cr = p_resp.headers.get("Content-Range", "")
                    if "/" in cr:
                        total_size = int(cr.split("/")[1])
                    elif "Content-Length" in p_resp.headers:
                        total_size = int(p_resp.headers["Content-Length"])
                    return direct_url, movie_title, total_size
            except Exception:
                return direct_url, movie_title, 0

async def download_video_or_m3u8(
    video_url: str,
    output_dir: str,
    custom_name: str,
    referer_header: str,
    status_msg: Message,
    task_id: str,
    lang: str,
    dl_start_time: float,
    last_update: list,
    num_connections: int = 64
) -> tuple:
    """تحميل روابط البث m3u8 ومشغلات الفيديو المضمنة وتحويلها إلى MP4 1080p عالية الجودة بأقصى سرعة"""
    loop = asyncio.get_running_loop()

    # تطبيع رابط ok.ru لاستخدام videoembed وتجنب بطء صفحة الويب
    m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/)(\d+)', video_url)
    if m_ok:
        video_url = f"https://ok.ru/videoembed/{m_ok.group(1)}"

    # 1. تفعيل محرك التيربو الخارق فائق السرعة لمقاطع OK.ru لتفادي بطء DASH
    if "ok.ru" in video_url or "odnoklassniki.ru" in video_url:
        try:
            logger.info("🚀 OK.ru detected! Resolving high-speed progressive MP4...")
            direct_mp4_url, ok_title, total_file_size = await get_ok_direct_mp4(video_url)
            if direct_mp4_url and total_file_size > 0:
                if custom_name:
                    v_title = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
                else:
                    v_title = ok_title or f"video_{int(time.time())}"
                v_title = re.sub(r'[\\/*?:"<>|]', '', v_title).strip()
                target_mp4 = os.path.join(output_dir, f"{v_title}.mp4")
                
                dl_headers = {
                    "User-Agent": STEALTH_HEADERS["User-Agent"],
                    "Referer": "https://ok.ru/"
                }
                
                logger.info(f"⚡ Launching Multi-Stream Turbo ({num_connections}x) for OK.ru ({humanbytes(total_file_size)})...")
                try:
                    await status_msg.edit_text(
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🚀 <b>Turbo Video Stream Engine ({num_connections}x):</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎬 <b>Title:</b> <code>{v_title}</code>\n"
                        f"📊 <b>Size:</b> <code>{humanbytes(total_file_size)}</code>\n"
                        f"⚡ <b>Full Bandwidth Acceleration Active</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                        reply_markup=make_cancel_keyboard(task_id, lang=lang),
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

                turbo_success = await download_multi_stream_turbo(
                    direct_url=direct_mp4_url,
                    file_path=target_mp4,
                    total_size=total_file_size,
                    headers=dl_headers,
                    status_msg=status_msg,
                    task_id=task_id,
                    lang=lang,
                    dl_start_time=dl_start_time,
                    last_update=last_update,
                    num_connections=num_connections
                )
                if turbo_success and os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 100 * 1024:
                    logger.info(f"✅ OK.ru downloaded at maximum speed via Multi-Stream Turbo: {target_mp4}")
                    return True, target_mp4, os.path.basename(target_mp4)
        except Exception as ok_err:
            logger.warning(f"Direct OK.ru Turbo extraction notice: {ok_err}")

    # 2. محرك yt-dlp المتوازي للبثوث المباشرة وباقي المشغلات (HLS, DASH, m3u8)
    if not YTDLP_AVAILABLE:
        logger.warning("yt-dlp is not installed!")
        return False, None, None

    if custom_name:
        out_template = os.path.join(output_dir, f"{custom_name}.%(ext)s")
    else:
        out_template = os.path.join(output_dir, "%(title).100s.%(ext)s")

    parsed_netloc = urllib.parse.urlparse(video_url).netloc
    parts = parsed_netloc.split(".")
    base_domain = ".".join(parts[-2:]) if len(parts) >= 2 else parsed_netloc
    origin_header = f"{urllib.parse.urlparse(video_url).scheme}://{parsed_netloc}"

    candidate_referers = [
        referer_header if referer_header else origin_header,
        f"https://{base_domain}/",
        None
    ]

    for current_ref in candidate_referers:
        if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            return False, None, None

        status_tracker = {"downloaded": 0, "total": 0}

        def ytdl_progress_hook(d):
            if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                raise Exception("Download cancelled by user")
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                status_tracker["downloaded"] = downloaded
                status_tracker["total"] = total
                asyncio.run_coroutine_threadsafe(
                    progress_bar(
                        downloaded, total, tr(lang, "downloading"),
                        status_msg, dl_start_time, last_update,
                        icon="🎬", task_id=task_id, lang=lang
                    ),
                    loop
                )

        headers = {
            'User-Agent': STEALTH_HEADERS['User-Agent'],
            'Origin': origin_header
        }
        if current_ref:
            headers['Referer'] = current_ref

        ydl_opts = {
            'outtmpl': out_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'http_headers': headers,
            'progress_hooks': [ytdl_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'retries': 5,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'concurrent_fragment_downloads': min(num_connections, 32),
            'buffersize': 1024 * 1024,
            'socket_timeout': 25,
            'geo_bypass': True,
        }

        def run_ydl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                base_name, _ = os.path.splitext(filename)
                mp4_name = f"{base_name}.mp4"
                if os.path.exists(mp4_name):
                    return mp4_name, info.get("title", "Video")
                if os.path.exists(filename):
                    return filename, info.get("title", "Video")
                return None, None

        try:
            final_path, title = await loop.run_in_executor(None, run_ydl)
            if final_path and os.path.exists(final_path):
                return True, final_path, os.path.basename(final_path)
        except Exception as e:
            logger.warning(f"yt-dlp try with ref [{current_ref}] failed: {e}")
            await asyncio.sleep(0.5)

    return False, None, None

async def extract_video_metadata(video_path: str):
    """استخراج أبعاد الفيديو ومدته وتوليد صورة مصغرة (Thumbnail) باستخدام ffmpeg/ffprobe بأمان تام"""
    thumb_path = None
    duration = 0
    width = 0
    height = 0

    if not video_path or not os.path.exists(video_path):
        return None, 0, 0, 0

    # 1. محاولة استخراج المدة والأبعاد عبر ffprobe
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "json", video_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            info = json.loads(stdout.decode(errors="ignore"))
            fmt = info.get("format", {})
            if "duration" in fmt:
                try:
                    duration = int(float(fmt["duration"]))
                except Exception:
                    pass
            streams = info.get("streams", [])
            for s in streams:
                if "width" in s and "height" in s:
                    try:
                        width = int(s["width"])
                        height = int(s["height"])
                        break
                    except Exception:
                        pass
    except (FileNotFoundError, Exception) as e:
        logger.debug(f"ffprobe metadata extraction skipped: {e}")

    # 2. محاولة توليد thumbnail عبر ffmpeg
    try:
        base_name, _ = os.path.splitext(video_path)
        candidate_thumb = f"{base_name}_thumb_{int(time.time())}.jpg"
        time_offset = min(duration // 2, 5) if duration > 0 else 1
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-ss", str(time_offset),
            "-i", video_path, "-vframes", "1",
            "-vf", "scale=320:-1", candidate_thumb
        ]
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if os.path.exists(candidate_thumb) and os.path.getsize(candidate_thumb) > 0:
            thumb_path = candidate_thumb
    except (FileNotFoundError, Exception) as e:
        logger.debug(f"ffmpeg thumb extraction skipped: {e}")

    return thumb_path, duration, width, height

def build_file_caption(filename: str, file_size: int, category_desc: str, icon: str, user_id: int, custom_caption: str = None) -> tuple:
    """بناء كابشن احترافي مع زر الحقوق التلقائي للقناة (Auto-Branding)"""
    st = db_get_user_settings(user_id) if user_id else {}
    if custom_caption:
        caption = custom_caption
    elif not st.get("enable_caption", 1):
        caption = ""
    else:
        channel_tag = st.get("channel_tag", "").strip()
        caption_lines = [
            f"🎮 <b>File:</b> <code>{filename}</code>",
            f"{icon} <b>Category:</b> {category_desc}",
            f"📊 <b>Size:</b> <code>{humanbytes(file_size)}</code>"
        ]
        if channel_tag:
            formatted_channel = f"@{channel_tag.lstrip('@')}" if not channel_tag.startswith("http") else channel_tag
            caption_lines.append(f"👑 <b>Channel:</b> {formatted_channel}")
            caption_lines.append("⚡ <i>Direct Fast Download | تحميل فائق السرعة</i>")
        
        caption = "\n".join(caption_lines)
    
    reply_markup = None
    channel_tag = st.get("channel_tag", "").strip()
    if channel_tag and st.get("channel_button", 1):
        ch_clean = channel_tag.lstrip("@").replace("https://t.me/", "").replace("t.me/", "").strip()
        ch_url = f"https://t.me/{ch_clean}" if not channel_tag.startswith("http") else channel_tag
        ch_btn_text = f"📢 انضم لقناتنا ({channel_tag})" if not channel_tag.startswith("http") else "📢 انضم للقناة الرسمية"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(ch_btn_text, url=ch_url)]])
        
    return caption, reply_markup

async def resilient_send_media(client, chat_id, file_path, caption, is_video, progress_cb=None, thumb=None, duration=0, width=0, height=0, reply_markup=None):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            if is_video:
                kwargs = {
                    "chat_id": chat_id,
                    "video": file_path,
                    "caption": caption,
                    "supports_streaming": True,
                    "progress": progress_cb,
                    "parse_mode": ParseMode.HTML
                }
                if reply_markup:
                    kwargs["reply_markup"] = reply_markup
                if thumb and os.path.exists(thumb):
                    kwargs["thumb"] = thumb
                if duration > 0:
                    kwargs["duration"] = duration
                if width > 0 and height > 0:
                    kwargs["width"] = width
                    kwargs["height"] = height
                return await client.send_video(**kwargs)
            else:
                kwargs = {
                    "chat_id": chat_id,
                    "document": file_path,
                    "caption": caption,
                    "progress": progress_cb,
                    "parse_mode": ParseMode.HTML
                }
                if reply_markup:
                    kwargs["reply_markup"] = reply_markup
                return await client.send_document(**kwargs)
        except FloodWait as fw:
            logger.warning(f"Telegram FloodWait during upload: {fw.value}s - waiting...")
            await asyncio.sleep(fw.value + 1)
        except Exception as e:
            logger.warning(f"Upload attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2.0)

async def process_download_and_upload(raw_url: str, custom_name: str, custom_caption: str, status_msg: Message, user_msg: Message, hop_count: int = 0):
    if hop_count >= 2:
        await status_msg.edit_text("❌ <b>Maximum download redirect limit reached!</b>", parse_mode=ParseMode.HTML)
        return

    file_path = None
    thumb_path = None
    start_time = time.time()
    task_id = f"task_{int(time.time() * 1000)}"
    ACTIVE_TASKS[task_id] = {"cancelled": False}
    user_id = user_msg.from_user.id if user_msg.from_user else 0
    settings = db_get_user_settings(user_id)
    lang = settings["lang"]
    user_threads = settings.get("god_threads", 64)
    
    try:
        direct_url = await unrestrict_direct_link(raw_url)
        parsed_url = urllib.parse.urlparse(direct_url)
        
        custom_cookie = ""
        referer_header = ""
        doc_extracted_title = ""
        if "#" in direct_url:
            base_part, fragment_part = direct_url.split("#", 1)
            direct_url = base_part
            parsed_url = urllib.parse.urlparse(direct_url)
            params = urllib.parse.parse_qs(fragment_part)
            if "ref" in params:
                referer_header = params["ref"][0]
            if "cookie" in params and params["cookie"][0]:
                custom_cookie = f"PHPSESSID={params['cookie'][0]}"
            if "title" in params and params["title"][0]:
                doc_extracted_title = urllib.parse.unquote(params["title"][0]).strip()
                if not custom_name and doc_extracted_title:
                    custom_name = doc_extracted_title

        if not referer_header:
            if "an1.net" in direct_url or "an1.com" in direct_url:
                referer_header = "https://an1.com/"
            elif "documentaryarea.com" in direct_url:
                referer_header = "https://www.documentaryarea.com/"
            elif "devuploads.com" in direct_url:
                referer_header = "https://devuploads.com/"
            else:
                referer_header = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        status_tracker = {"downloaded": 0}
        dl_start_time = time.time()
        last_update = [0]
        download_success = False

        # =========================================================================
        # 1. فحص وتنزيل روابط البث ومشغلات الفيديو المضمنة (m3u8 & Web Video Streams)
        # =========================================================================
        if is_hls_or_video_stream(direct_url) or is_hls_or_video_stream(raw_url):
            target_stream_url = direct_url if is_hls_or_video_stream(direct_url) else raw_url
            logger.info(f"🎬 HLS / Video Stream detected: {target_stream_url}")
            await status_msg.edit_text(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎬 <b>OMNIPOTENT HLS & Video Stream Engine:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Extracting Stream & Converting to MP4 1080p...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML
            )
            v_ok, v_path, v_name = await download_video_or_m3u8(
                video_url=target_stream_url,
                output_dir=DOWNLOAD_DIR,
                custom_name=custom_name,
                referer_header=referer_header,
                status_msg=status_msg,
                task_id=task_id,
                lang=lang,
                dl_start_time=dl_start_time,
                last_update=last_update,
                num_connections=user_threads
            )
            if v_ok and v_path and os.path.exists(v_path):
                file_path = v_path
                filename = clean_and_rename_filename(v_name, user_id=user_id)
                if task_id in ACTIVE_TASKS:
                    ACTIVE_TASKS[task_id]["filename"] = filename
                icon, category_desc, is_video_type = get_god_category(filename)
                is_video_type = True
                download_success = True
            else:
                await status_msg.edit_text(
                    "❌ <b>Stream Extraction Failed:</b>\n"
                    "<code>Server returned 403 Forbidden or Stream Expired.</code>\n\n"
                    "💡 <i>Try sending the movie page URL directly or another player server!</i>",
                    parse_mode=ParseMode.HTML
                )
                return

        # =========================================================================
        # 2. تشغيل محرك التنزيل المتوازي الفائق (Multi-Stream Turbo) للروابط المقيدة فقط (<1MB/s)
        # =========================================================================
        if not download_success and is_speed_throttled_url(direct_url):
            try:
                headers = {**STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
                if custom_cookie:
                    headers["Cookie"] = custom_cookie
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as init_session:
                    async with init_session.get(direct_url, headers=headers, allow_redirects=True) as head_resp:
                        if head_resp.status in (200, 206):
                            content_len = head_resp.headers.get("Content-Length")
                            total_size_probe = 0
                            cr = head_resp.headers.get("Content-Range", "")
                            if "/" in cr:
                                total_size_probe = int(cr.split("/")[1])
                            elif content_len and content_len.isdigit():
                                total_size_probe = int(content_len)
                            
                            extracted_filename = smart_extract_filename(direct_url, head_resp.headers)
                            _, ext = os.path.splitext(extracted_filename)
                            raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                            filename = clean_and_rename_filename(raw_target_name, user_id=user_id)
                            if task_id in ACTIVE_TASKS:
                                ACTIVE_TASKS[task_id]["filename"] = filename
                            icon, category_desc, is_video_type = get_god_category(filename)
                            file_path = os.path.join(DOWNLOAD_DIR, filename)

                            logger.info(f"⚡ Launching Multi-Stream Turbo Downloader ({user_threads}x) for throttled link: {direct_url} (Size: {humanbytes(total_size_probe)})...")
                            info_card = (
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🚀 <b>Multi-Stream Turbo Downloader ({user_threads}x):</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📄 <b>File:</b> <code>{filename}</code>\n"
                                f"{icon} <b>Category:</b> {category_desc}\n"
                                f"📊 <b>Size:</b> <code>{humanbytes(total_size_probe)}</code>\n"
                                f"⚡ <b>Bypassing Host Speed Cap Active</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                            )
                            await status_msg.edit_text(info_card, reply_markup=make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                            turbo_ok = await download_multi_stream_turbo(
                                direct_url=direct_url,
                                file_path=file_path,
                                total_size=total_size_probe,
                                headers=headers,
                                status_msg=status_msg,
                                task_id=task_id,
                                lang=lang,
                                dl_start_time=dl_start_time,
                                last_update=last_update,
                                num_connections=user_threads
                            )
                            if turbo_ok:
                                download_success = True
            except Exception as turbo_err:
                logger.warning(f"Turbo download probe/fallback: {turbo_err}")

        profiles = [
            ("chrome124", referer_header),
            ("chrome120", "https://www.google.com/"),
            ("safari15_5", direct_url)
        ]

        if not download_success and CURL_CFFI_AVAILABLE:
            for target_prof, target_ref in profiles:
                if download_success or ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    break

                max_stalled_retries = 5
                for retry_idx in range(max_stalled_retries):
                    if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        break

                    headers = {**STEALTH_HEADERS, "Referer": target_ref}
                    if custom_cookie:
                        headers["Cookie"] = custom_cookie
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
                            
                            raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                            filename = clean_and_rename_filename(raw_target_name, user_id=user_id)
                            if task_id in ACTIVE_TASKS:
                                ACTIVE_TASKS[task_id]["filename"] = filename
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
                                f"🚀 <b>Auto-Unrestrict Web Page Active</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                            )
                            await status_msg.edit_text(info_card, reply_markup=make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                            mode = "a+b" if status_tracker["downloaded"] > 0 else "wb"
                            last_chunk_time = time.time()
                            stalled = False

                            with open(file_path, mode) as f:
                                if status_tracker["downloaded"] > 0:
                                    f.seek(status_tracker["downloaded"])
                                
                                async for chunk in resp.aiter_content(512 * 1024):
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
                                    
                                    if (time.time() - last_chunk_time) > 15.0:
                                        logger.warning(f"⚠️ Stream stalled for 15s. Auto-Resuming from byte {status_tracker['downloaded']}...")
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
            if custom_cookie:
                headers["Cookie"] = custom_cookie
            async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                async with session.get(direct_url, headers=headers, allow_redirects=True) as response:
                    if response.status not in (200, 206):
                        await status_msg.edit_text(f"❌ <b>URL Error: Server responded with status {response.status}</b>", parse_mode=ParseMode.HTML)
                        return
                    
                    content_length = response.headers.get("Content-Length")
                    total_size = int(content_length) if content_length and content_length.isdigit() else 0
                    
                    extracted_filename = smart_extract_filename(direct_url, response.headers)
                    _, ext = os.path.splitext(extracted_filename)
                    raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                    filename = clean_and_rename_filename(raw_target_name, user_id=user_id)
                    if task_id in ACTIVE_TASKS:
                        ACTIVE_TASKS[task_id]["filename"] = filename
                    icon, category_desc, is_video_type = get_god_category(filename)
                    file_path = os.path.join(DOWNLOAD_DIR, filename)

                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(512 * 1024):
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
                    download_success = True
        
        actual_file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0

        if not file_path or not os.path.exists(file_path) or actual_file_size == 0:
            await status_msg.edit_text(
                "❌ <b>Download Failed:</b>\n"
                "<code>The server was unable to retrieve data from this host.</code>\n\n"
                "💡 <i>The link may be expired, IP-locked, or blocked by host firewall.</i>",
                parse_mode=ParseMode.HTML
            )
            return

        # =========================================================================
        # فحص التوقيع البنائي المزدوج مع دعم محرك System CURL الخارق
        # =========================================================================
        is_binary, html_sample = is_valid_binary_file(file_path)
        if not is_binary and file_path and os.path.exists(file_path):
            os.remove(file_path)
            
            # محاولة استخدام المحرك الخارق (System CURL Engine) لتجاوز حماية الجدار الناري/Cloudflare
            logger.info(f"⚡ Invoking System CURL Engine for {direct_url}...")
            curl_cmd = [
                "curl", "-s", "-L",
                "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                direct_url, "-o", file_path
            ]
            if referer_header:
                curl_cmd.extend(["-H", f"Referer: {referer_header}"])

            try:
                proc = await asyncio.create_subprocess_exec(*curl_cmd)
                await proc.communicate()
            except FileNotFoundError:
                logger.warning("System curl executable not found in PATH")
            except Exception as curl_err:
                logger.warning(f"CURL engine error: {curl_err}")

            is_binary, html_sample = is_valid_binary_file(file_path)

        if not is_binary and file_path and os.path.exists(file_path):
            os.remove(file_path)
            real_url = extract_real_download_link_from_html(html_sample, raw_url)
            
            if real_url and real_url.split('#')[0] != raw_url.split('#')[0]:
                logger.info(f"🔗 Real direct URL extracted from HTML: {real_url}")
                await process_download_and_upload(real_url, custom_name, custom_caption, status_msg, user_msg, hop_count=hop_count+1)
                return
            else:
                page_title = ""
                m_t = re.search(r'<title>(.*?)</title>', html_sample, re.IGNORECASE | re.DOTALL)
                if m_t:
                    page_title = re.sub(r'\s+', ' ', m_t.group(1)).strip()[:100]
                err_detail = f"\n📄 <b>Page Title:</b> <code>{page_title}</code>" if page_title else ""
                await status_msg.edit_text(
                    f"❌ <b>URL is an HTML webpage, not a direct file link!</b>{err_detail}\n\n"
                    f"💡 <i>Make sure the link is a valid direct link and not expired or IP-locked.</i>",
                    parse_mode=ParseMode.HTML
                )
                return

        actual_file_size = os.path.getsize(file_path)

        BOT_LIMIT_BYTES = 1950 * 1024 * 1024      # 1.95 GB الحد الأقصى المطلق للبوت لتفادي خطأ 2000 MiB
        SPLIT_CHUNK_BYTES = 1900 * 1024 * 1024    # 1.90 GB

        CHANNEL_ID = parse_chat_id(os.environ.get("CHANNEL_ID", ""))
        uploader = get_uploader_client()
        is_premium_active = (user_bot is not None) and getattr(user_bot, "is_connected", False) and (uploader == user_bot)

        # فحص إمكانية رفع الملف ككتلة واحدة (حتى 4GB) عبر حساب الـ Premium
        if actual_file_size > BOT_LIMIT_BYTES:
            if is_premium_active and actual_file_size <= (3950 * 1024 * 1024):
                # رفع الملف بالكامل كملف واحد ضخم عبر حساب الـ Premium
                await status_msg.edit_text(
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👑 <b>Uploading full {humanbytes(actual_file_size)} via Telegram Premium Account (No Splitting)...</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    parse_mode=ParseMode.HTML
                )
                up_start_time = time.time()
                last_update = [0]
                
                async def pyrogram_progress_prem(current, total):
                    if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        return
                    await progress_bar(
                        current, total, "👑 Premium Uploading", status_msg, up_start_time, last_update, icon="⚡", task_id=task_id, lang=lang
                    )

                caption, brand_markup = build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)
                
                target_chat = CHANNEL_ID if CHANNEL_ID else "me"
                is_vid = is_video_type and settings["upload_mode"] != "doc"
                duration, width, height = 0, 0, 0
                if is_vid and settings.get("enable_thumbs", 1):
                    thumb_path, duration, width, height = await extract_video_metadata(file_path)
                try:
                    await resilient_send_media(uploader, target_chat, file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)
                except Exception as prem_upload_err:
                    logger.warning(f"Direct premium upload target error, trying 'me': {prem_upload_err}")
                    await resilient_send_media(uploader, "me", file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)

                total_time_spent = round(time.time() - start_time)
                avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
                db_add_history(user_id, filename, actual_file_size, category_desc)
                await status_msg.delete()

                dest_text = f"القناة ({CHANNEL_ID})" if CHANNEL_ID else "الرسائل المحفوظة (Saved Messages)"
                success_card = (
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👑 <b>تم رفع الملف كاملاً بـ Telegram Premium بنجاح!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{tr(lang, 'file_name')} <code>{filename}</code>\n"
                    f"{icon} {tr(lang, 'category')} {category_desc}\n"
                    f"{tr(lang, 'final_size')} <code>{humanbytes(actual_file_size)} (ملف واحد كامل)</code>\n"
                    f"📍 <b>مكان الإرسال:</b> <code>{dest_text}</code>\n"
                    f"{tr(lang, 'total_time')} <code>{time_formatter(total_time_spent)}</code>\n"
                    f"{tr(lang, 'avg_speed')} <code>{humanbytes(avg_speed)}/s</code> 🔥🌌\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
                return
            else:
                # إذا لم يكن البريميوم مفعلاً -> تقسيم الملف لتفادي الانهيار
                num_parts = math.ceil(actual_file_size / SPLIT_CHUNK_BYTES)
                await status_msg.edit_text(
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✂️ <b>OMNIPOTENT Splitter: Splitting giant file ({humanbytes(actual_file_size)}) into {num_parts} parts...</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    parse_mode=ParseMode.HTML
                )

                part_number = 1
                ext = os.path.splitext(filename)[1]
                with open(file_path, "rb") as src_file:
                    while True:
                        if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                            return
                        chunk_data = src_file.read(SPLIT_CHUNK_BYTES)
                        if not chunk_data:
                            break
                        part_filename = f"{os.path.splitext(filename)[0]}.part{part_number:03d}{ext}"
                        part_filepath = os.path.join(DOWNLOAD_DIR, part_filename)
                        with open(part_filepath, "wb") as part_file:
                            part_file.write(chunk_data)

                        # إرسال الجزء للمستخدم في الشات (يظهر دائماً وبشكل مؤكد)
                        await user_msg.reply_document(
                            document=part_filepath,
                            caption=f"🧩 <b>Part {part_number}/{num_parts}</b>\n📄 <code>{part_filename}</code>",
                            parse_mode=ParseMode.HTML
                        )

                        if os.path.exists(part_filepath): os.remove(part_filepath)
                        part_number += 1

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
                    f"{tr(lang, 'final_size')} <code>{humanbytes(actual_file_size)} ({num_parts} Parts)</code>\n"
                    f"{tr(lang, 'total_time')} <code>{time_formatter(total_time_spent)}</code>\n"
                    f"{tr(lang, 'avg_speed')} <code>{humanbytes(avg_speed)}/s</code> 🔥🌌\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
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

        caption, brand_markup = build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)

        if ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            await status_msg.edit_text("🛑 <b>Upload cancelled!</b>", parse_mode=ParseMode.HTML)
            return

        CHANNEL_ID = parse_chat_id(os.environ.get("CHANNEL_ID", ""))
        force_video = False if settings["upload_mode"] == "doc" else is_video_type
        
        duration, width, height = 0, 0, 0
        if force_video and settings.get("enable_thumbs", 1):
            thumb_path, duration, width, height = await extract_video_metadata(file_path)

        # 1. إرسال الملف فوراً ومباشرة للمستخدم عبر البوت
        await resilient_send_media(bot, user_msg.chat.id, file_path, caption, force_video, pyrogram_progress, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)

        # 2. النشر التلقائي في القناة (مثل @APKBlitz) إذا تم تحديد CHANNEL_ID في البيئة
        if CHANNEL_ID:
            try:
                uploader = get_uploader_client()
                if force_video:
                    kwargs = {
                        "chat_id": CHANNEL_ID,
                        "video": file_path,
                        "caption": caption,
                        "supports_streaming": True,
                        "parse_mode": ParseMode.HTML,
                        "reply_markup": brand_markup
                    }
                    if thumb_path and os.path.exists(thumb_path): kwargs["thumb"] = thumb_path
                    if duration > 0: kwargs["duration"] = duration
                    if width > 0 and height > 0:
                        kwargs["width"] = width
                        kwargs["height"] = height
                    await uploader.send_video(**kwargs)
                else:
                    await uploader.send_document(chat_id=CHANNEL_ID, document=file_path, caption=caption, reply_markup=brand_markup, parse_mode=ParseMode.HTML)
            except Exception as ch_err:
                logger.warning(f"Channel upload notice: {ch_err}")
            
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
    except MessageNotModified:
        pass
    except RPCError as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            await status_msg.edit_text(f"❌ <b>Telegram Upload Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Unexpected Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        ACTIVE_TASKS.pop(task_id, None)
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        gc.collect()

def cleanup_temp_dir():
    try:
        if os.path.exists(DOWNLOAD_DIR):
            for f in os.listdir(DOWNLOAD_DIR):
                fp = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Cleanup temp notice: {e}")

# ==========================================
# 13. نقطة البداية وتشغيل البوت (Main Entry Point)
# ==========================================
async def main():
    if not API_ID or not API_HASH or not BOT_TOKEN:
        logger.error("❌ API_ID, API_HASH, or BOT_TOKEN missing!")
        sys.exit(1)

    cleanup_temp_dir()
    await start_web_server()
    asyncio.create_task(queue_worker())

    logger.info("Starting Pyrogram Client with Bilingual OMNIPOTENT OVERLORD ENGINE...")
    await bot.start()
    
    if user_bot:
        try:
            await user_bot.start()
            user_me = await user_bot.get_me()
            logger.info("==================================================")
            logger.info(f"🌟 TELEGRAM PREMIUM USERBOT ACTIVE: @{user_me.username} ({user_me.id})")
            logger.info(f"🚀 4GB SINGLE FILE UPLOAD & PREMIUM SPEED PRIORITY ENABLED!")
            logger.info("==================================================")
        except Exception as u_err:
            logger.error(f"⚠️ Premium UserBot failed to start: {u_err}")

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
            BotCommand("stats", "📊 Engine Stats / إحصائيات المحرك"),
            BotCommand("broadcast", "📢 Broadcast message / إذاعة عامة (Admin)"),
            BotCommand("dashboard", "📊 Web Live Dashboard / مراقبة الويب (Admin)"),
            BotCommand("set_prefix", "🏷️ Set filename prefix / بادئة الاسم"),
            BotCommand("set_suffix", "🏷️ Set filename suffix / لاحقة الاسم"),
            BotCommand("replace", "🔄 Replace text in filename / استبدال نص"),
            BotCommand("replacements", "📋 List text replace rules / قائمة القواعد")
        ])
    except Exception as e:
        logger.warning(f"Set commands notice: {e}")

    await idle()
    if user_bot and getattr(user_bot, "is_connected", False):
        await user_bot.stop()
    await bot.stop()

if __name__ == "__main__":
    try:
        bot.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
