import datetime
import html
import logging
from zoneinfo import ZoneInfo

import myidm  # noqa: F401
from myidm import utils

logger = logging.getLogger("bot.fwdcache")


def format_fwdcache_note(filename: str, total_size: int, created_at: int) -> str:
    try:
        tz = ZoneInfo("Africa/Cairo")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=3))
    dt = datetime.datetime.fromtimestamp(created_at, tz=tz)
    date_str = dt.strftime("%Y-%m-%d %H:%M")
    size_str = utils.humanbytes(total_size)
    return (
        f"↪️ <b>أعدت توجيه الملف اللي نزّلته قبل كده بدل إعادة التحميل / Forwarded your earlier download instead of re-downloading</b>\n"
        f"📄 <b>الملف / File:</b> <code>{html.escape(filename or '')}</code>\n"
        f"📦 <b>الحجم / Size:</b> <code>{size_str}</code>\n"
        f"🕒 <b>تاريخ التحميل / Downloaded at:</b> <code>{date_str}</code> (Cairo Time)"
    )

def is_message_not_found_error(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    cls_name = exc.__class__.__name__
    if cls_name == "MessageIdInvalid":
        return True
    try:
        from pyrogram.errors import MessageIdInvalid
        if isinstance(exc, MessageIdInvalid):
            return True
    except ImportError:
        pass
    msg_str = str(exc).lower()
    if (
        "message_id_invalid" in msg_str
        or "message to forward not found" in msg_str
        or "message id invalid" in msg_str
        or "message_not_found" in msg_str
    ):
        return True
    return False
