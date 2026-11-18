import datetime
import html
import logging
import sys
import time
from zoneinfo import ZoneInfo

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import myidm  # noqa: F401
from myidm import apk_inspect
from myidm import clients
from myidm import db
from myidm import downloads
from myidm import utils

logger = logging.getLogger("bot.fwdcache")
_self = sys.modules[__name__]


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


async def handle_url_intake(
    url: str,
    custom_name: str,
    custom_caption: str,
    status_msg: Message,
    user_msg: Message,
    force_fresh: bool = False,
    client: Client | None = None
):
    url_key = (url or "").strip()
    user_id = user_msg.from_user.id if (user_msg and user_msg.from_user and not getattr(user_msg.from_user, "is_bot", False)) else (user_msg.chat.id if user_msg and user_msg.chat else 0)

    if not force_fresh and url_key and user_id:
        delivery = db.db_get_delivery(user_id, url_key)
        if delivery:
            target_client = client or clients.bot
            try:
                await target_client.forward_messages(
                    chat_id=user_msg.chat.id,
                    from_chat_id=delivery["chat_id"],
                    message_ids=delivery["message_ids"]
                )
            except Exception as fwd_err:
                if _self.is_message_not_found_error(fwd_err):
                    logger.warning(
                        f"Forward failed for delivery id={delivery['id']} ({fwd_err}). "
                        f"Deleting stale row and falling back to fresh download."
                    )
                    db.db_delete_delivery(delivery["id"])
                    await downloads.process_download_and_upload(url, custom_name, custom_caption, status_msg, user_msg)
                    return
                else:
                    # DEF-09: Re-raises non-MessageIdInvalid forward errors per owner ruling (IBC-03 excluded)
                    raise fwd_err

            note_text = _self.format_fwdcache_note(
                filename=delivery.get("filename") or "",
                total_size=delivery.get("total_size") or 0,
                created_at=delivery.get("created_at") or int(time.time())
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬇️ نزّله من جديد", callback_data=f"fwd_fresh_{delivery['id']}")]
            ])
            await user_msg.reply_text(note_text, reply_markup=markup, parse_mode=ParseMode.HTML)

            pkg = delivery.get("package")
            vc = delivery.get("version_code")
            if pkg and vc is not None:
                insp = db.db_get_apk_inspection(pkg, vc)
                if insp:
                    insp_info = {
                        "package": insp.get("package"),
                        "version_name": insp.get("version_name"),
                        "version_code": insp.get("version_code"),
                        "size_bytes": insp.get("size"),
                        "file_sha256": insp.get("file_sha256"),
                        "cert_sha256": insp.get("cert_sha256"),
                        "checked_at": insp.get("checked_at"),
                        "min_sdk": insp.get("min_sdk"),
                        "target_sdk": insp.get("target_sdk")
                    }
                    block_text = apk_inspect.format_blitzverify_block(insp_info)
                    if block_text:
                        await user_msg.reply_text(block_text, parse_mode=ParseMode.MARKDOWN)

            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            return

    await downloads.process_download_and_upload(url, custom_name, custom_caption, status_msg, user_msg)


async def run_fresh_download(delivery_id: int, user_msg: Message, status_msg: Message | None = None, forced_user_id: int | None = None):
    # DEF-15: Preserved verbatim without extra status_msg error wrapper per owner ruling (IBC-03 excluded)
    delivery = db.db_get_delivery_by_id(delivery_id)
    if not delivery:
        return False
    if not status_msg:
        status_msg = await user_msg.reply_text(
            "⏳ <b>جاري معالجة الرابط... / Processing link...</b>",
            parse_mode=ParseMode.HTML
        )
    uid = forced_user_id or delivery.get("user_id")
    await downloads.process_download_and_upload(
        raw_url=delivery["url_key"],
        custom_name="",
        custom_caption="",
        status_msg=status_msg,
        user_msg=user_msg,
        forced_user_id=uid
    )
    return True
