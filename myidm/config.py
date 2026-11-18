import os
import time
import logging
import tempfile
from dotenv import load_dotenv

import myidm
from pyrogram import filters

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CurlAsyncSession = None
    CURL_CFFI_AVAILABLE = False

try:
    from torrentp import TorrentDownloader
    TORRENTP_AVAILABLE = True
except ImportError:
    TorrentDownloader = None
    TORRENTP_AVAILABLE = False

yt_dlp = myidm.yt_dlp
YTDLP_AVAILABLE = myidm.YTDLP_AVAILABLE

load_dotenv()

# ==========================================
# 1. إعدادات OMNIPOTENT OVERLORD ENGINE ⚡🌌👑
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bot")

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

# DEF-03: Dead constant preserved verbatim per owner ruling (IBC-05 excluded)
ADMIN_ID = 1594244556

def is_admin(user_id: int) -> bool:
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS

# DEF-02: Dead filter preserved verbatim per owner ruling (IBC-05 excluded)
def _owner_filter(_, __, message):
    if not ADMIN_IDS:
        return True
    uid = message.from_user.id if message.from_user else 0
    return uid in ADMIN_IDS

owner_filter = filters.create(_owner_filter, name="OwnerFilter")

USER_SESSION_STRING = (os.environ.get("USER_SESSION_STRING", "") or os.environ.get("PREMIUM_SESSION", "")).strip().strip("'\"")

# DEF-03: Dead constants preserved verbatim per owner ruling (IBC-05 excluded)
if USER_SESSION_STRING:
    MAX_SINGLE_FILE_SIZE = 4000 * 1024 * 1024  # 4,000 MB (~4 GB Telegram Premium Limit)
    SPLIT_PART_SIZE = 3950 * 1024 * 1024      # 3.95 GB
else:
    MAX_SINGLE_FILE_SIZE = 2000 * 1024 * 1024  # 2,000 MB (~2 GB Bot Limit)
    SPLIT_PART_SIZE = 1950 * 1024 * 1024      # 1.95 GB

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "bot_database.db")
PENDING_DIR = os.path.join(DATA_DIR, "pending_downloads")
os.makedirs(PENDING_DIR, exist_ok=True)

DISK_MIN_FREE_GB = float(os.environ.get("DISK_MIN_FREE_GB", "2"))

BASE_TMP = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
DOWNLOAD_DIR = os.path.join(BASE_TMP, "ctele_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
START_TIME = time.time()

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

TLS_VERIFICATION_SKIPPED_NOTICE = "🔓 تم تجاوز التحقق من الشهادة لهذا المضيف (سلسلة شهادة ناقصة) / TLS verification skipped for this host (broken certificate chain)"
