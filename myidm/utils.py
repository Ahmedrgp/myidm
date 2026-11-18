import os
import re
import time
import shutil
import logging
import datetime
import urllib.parse
from zoneinfo import ZoneInfo

from myidm import config as cfg
from myidm import db

logger = logging.getLogger("bot.utils")

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

def format_cairo_time(epoch_time: float) -> str:
    try:
        tz = ZoneInfo("Africa/Cairo")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=3))
    dt = datetime.datetime.fromtimestamp(epoch_time, tz=tz)
    return dt.strftime("%Y-%m-%d %H:%M Cairo")

def get_god_category(filename: str) -> tuple:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.3gp', '.wmv'):
        return "🎬", "Video", True
    elif ext in ('.mp3', '.m4a', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma'):
        return "🎵", "Audio", False
    elif ext in ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'):
        return "📦", "Archive", False
    elif ext in ('.apk', '.xapk', '.apks', '.exe', '.msi', '.py', '.js', '.html'):
        return "📱", "Software", False
    elif ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'):
        return "🖼️", "Image", False
    elif ext in ('.pdf', '.docx', '.doc', '.txt', '.epub'):
        return "📄", "Document", False
    else:
        return "📁", "General", False

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
    
    st = db.db_get_user_settings(user_id) if user_id else {}
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
            rules = db.db_get_user_replacements(user_id)
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

def check_disk_space(path: str, needed_bytes: int | None = None) -> tuple[bool, int, int, int]:
    """
    Checks if there is enough free disk space on the filesystem of `path`.
    Returns (ok: bool, needed_bytes: int, free_bytes: int, reserve_bytes: int).
    Rule:
    - If needed_bytes is known (> 0): require free >= needed_bytes * 1.25 + reserve.
    - If needed_bytes is unknown or <= 0: require free >= reserve * 2.
    """
    reserve_bytes = int(cfg.DISK_MIN_FREE_GB * (1024 ** 3))
    try:
        check_dir = path
        while check_dir and not os.path.exists(check_dir):
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break
            check_dir = parent
        if not check_dir or not os.path.exists(check_dir):
            check_dir = "."
        usage = shutil.disk_usage(check_dir)
        free_bytes = usage.free
    except Exception as e:
        logger.warning(f"disk_usage check failed for {path}: {e}")
        free_bytes = 0

    if needed_bytes is not None and needed_bytes > 0:
        req_free = int(needed_bytes * 1.25) + reserve_bytes
        ok = free_bytes >= req_free
    else:
        req_free = reserve_bytes * 2
        ok = free_bytes >= req_free

    return ok, (needed_bytes or 0), free_bytes, reserve_bytes

def check_disk_space_for_split(path: str, piece_size: int) -> tuple[bool, int, int, int]:
    """
    Checks disk space before splitting a file.
    Rule: require free >= piece_size + reserve.
    """
    reserve_bytes = int(cfg.DISK_MIN_FREE_GB * (1024 ** 3))
    try:
        check_dir = path if os.path.exists(path) else (os.path.dirname(path) or ".")
        usage = shutil.disk_usage(check_dir)
        free_bytes = usage.free
    except Exception as e:
        logger.warning(f"disk_usage split check failed for {path}: {e}")
        free_bytes = 0
    ok = free_bytes >= (piece_size + reserve_bytes)
    return ok, piece_size, free_bytes, reserve_bytes
