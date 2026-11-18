import asyncio
import logging
import math
import sys
import time

from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import myidm  # noqa: F401
from myidm import db
from myidm import texts
from myidm import utils

logger = logging.getLogger("bot.keyboards")
_self = sys.modules[__name__]


def make_start_keyboard(lang: str = "ar", is_admin: bool = False):
    buttons = [
        [
            InlineKeyboardButton(texts.tr(lang, "btn_panel"), callback_data="btn_god_panel"),
            InlineKeyboardButton(texts.tr(lang, "btn_history"), callback_data="btn_history")
        ],
        [
            InlineKeyboardButton(texts.tr(lang, "btn_settings"), callback_data="btn_settings"),
            InlineKeyboardButton(texts.tr(lang, "btn_probe"), callback_data="btn_probe_info")
        ],
        [
            InlineKeyboardButton(texts.tr(lang, "btn_stats"), callback_data="btn_stats")
        ]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("لوحة المسؤول (Admin Panel)", callback_data="btn_admin_panel")])
    return InlineKeyboardMarkup(buttons)


def make_settings_keyboard(user_id: int):
    st = db.db_get_user_settings(user_id)
    lang = st["lang"]
    mode_str = texts.tr(lang, "btn_mode_auto") if st["upload_mode"] == "auto" else texts.tr(lang, "btn_mode_doc")
    threads_str = texts.tr(lang, "btn_threads", threads=st['god_threads'])
    lang_btn_str = "🌐 اللغة: 🇸🇦 العربية" if lang == "ar" else "🌐 Language: 🇺🇸 English"
    caption_str = texts.tr(lang, "btn_caption_on") if st.get("enable_caption", 1) else texts.tr(lang, "btn_caption_off")
    thumbs_str = texts.tr(lang, "btn_thumbs_on") if st.get("enable_thumbs", 1) else texts.tr(lang, "btn_thumbs_off")
    clean_str = texts.tr(lang, "btn_cleantags_on") if st.get("clean_tags", 1) else texts.tr(lang, "btn_cleantags_off")

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang_btn_str, callback_data="toggle_lang")],
        [InlineKeyboardButton(mode_str, callback_data="toggle_mode")],
        [InlineKeyboardButton(threads_str, callback_data="toggle_threads")],
        [InlineKeyboardButton(caption_str, callback_data="toggle_caption"), InlineKeyboardButton(thumbs_str, callback_data="toggle_thumbs")],
        [InlineKeyboardButton(clean_str, callback_data="toggle_cleantags")],
        [InlineKeyboardButton("حقوق القناة (Branding)", callback_data="btn_open_brand")],
        [InlineKeyboardButton(texts.tr(lang, "btn_back"), callback_data="btn_start")]
    ])


def make_brand_keyboard(user_id: int):
    st = db.db_get_user_settings(user_id)
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
        [InlineKeyboardButton(texts.tr(lang, "btn_back"), callback_data="btn_start")]
    ])


def make_cancel_keyboard(task_id: str, lang: str = "ar"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(texts.tr(lang, "btn_cancel"), callback_data=f"cancel_{task_id}")]
    ])


def make_duplicate_keyboard(pending_id: int, lang: str = "ar") -> InlineKeyboardMarkup:
    btn_go = "✅ نزّله تاني" if lang == "ar" else "✅ Download anyway"
    btn_no = "🛑 إلغاء" if lang == "ar" else "🛑 Cancel"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(btn_go, callback_data=f"dup_go_{pending_id}"),
            InlineKeyboardButton(btn_no, callback_data=f"dup_no_{pending_id}")
        ]
    ])


async def progress_bar(current: int, total: int, status_text: str, message: Message, start_time: float, last_update: list, icon: str = "⬇️", task_id: str = None, lang: str = "ar"):
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

    total_str = utils.humanbytes(total) if total else "..."
    perc_str = f"{round(percentage, 1)}%" if total else "N/A"
    eta_str = utils.time_formatter(time_to_completion) if total else "..."

    header = f"{icon} <b>{status_text}</b>" if icon and icon not in ("🌌", "⚡", "👑", "🚀", "🔥") else f"<b>{status_text}</b>"
    text = (
        f"{header}\n"
        f"<code>{bar}</code> <b>{perc_str}</b>\n\n"
        f"{texts.tr(lang, 'transfer_rate')} <code>{utils.humanbytes(speed)}/s</code>\n"
        f"{texts.tr(lang, 'processed_size')} <code>{utils.humanbytes(current)}</code> / <code>{total_str}</code>\n"
        f"{texts.tr(lang, 'eta')} <code>{eta_str}</code>"
    )

    reply_markup = _self.make_cancel_keyboard(task_id, lang=lang) if task_id else None

    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except (RPCError, MessageNotModified):
        pass


async def safe_edit_text(message: Message | None, text: str, *args, **kwargs) -> Message | None:
    """
    Safely edits a Telegram message text, swallowing MessageNotModified
    so that no-op or identical-text status edits never crash or abort execution.
    """
    if message is None:
        return None
    try:
        return await message.edit_text(text, *args, **kwargs)
    except MessageNotModified:
        logger.debug(f"MessageNotModified swallowed on edit_text for message {getattr(message, 'id', None)}")
        return message
