import asyncio
import gc
import logging
import os
import re
import sys
import time

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

import myidm  # noqa: F401
from myidm import config as cfg
from myidm import db
from myidm import downloads
from myidm import fwdcache
from myidm import state

logger = logging.getLogger("bot.intake")
_self = sys.modules[__name__]


# ==========================================
# 10. استقبال وتجهيز المستندات والتورينت (.torrent Document)
# ==========================================
async def handle_document_torrent(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    if user_id:
        db.db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")

    # DEF-15: Non-.torrent documents ignored silently per owner ruling (IBC-03 excluded)
    doc = message.document
    if doc and doc.file_name and doc.file_name.lower().endswith(".torrent"):
        status_msg = await message.reply_text("🧲 <b>Downloading .torrent file & initializing Torrent Engine...</b>", parse_mode=ParseMode.HTML)
        torrent_file = await message.download(file_name=os.path.join(cfg.DOWNLOAD_DIR, doc.file_name))
        await state.request_queue.put(("torrent", torrent_file, status_msg, message))


# ==========================================
# 11. استقبال الروابط الفورية والتورينت المغناطيسي (Magnet Links)
# ==========================================
async def handle_all_messages(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    if user_id:
        db.db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")

    # DEF-15: Messages older than 300s dropped silently per owner ruling (IBC-03 excluded)
    msg_time = message.date.timestamp() if message.date else 0
    if msg_time and (time.time() - msg_time) > 300:
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        return

    if text.startswith("/"):
        return

    # التورينت المغناطيسي (Magnet Links)
    if "magnet:?" in text:
        magnet_match = re.search(r'magnet:\?[^\s]+', text)
        if magnet_match:
            magnet_url = magnet_match.group(0)
            status_msg = await message.reply_text("🧲 <b>جاري الاتصال بالتورينت... / Connecting to peers...</b>", parse_mode=ParseMode.HTML)
            await state.request_queue.put(("torrent", magnet_url, status_msg, message))
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
        await state.request_queue.put(("zip_bundle", valid_requests, status_msg, message))
        return

    if len(valid_requests) > 1:
        await message.reply_text(
            f"📥 <b>تمت إضافة {len(valid_requests)} رابط إلى قائمة الانتظار / Added {len(valid_requests)} URLs to queue</b>",
            parse_mode=ParseMode.HTML
        )

    for item in valid_requests:
        url, custom_name, custom_caption = item
        queue_pos = state.request_queue.qsize() + 1
        
        if queue_pos > 1:
            status_msg = await message.reply_text(
                f"⏳ <b>في قائمة الانتظار #{queue_pos-1} / Queue position #{queue_pos-1}</b>\n"
                f"📄 <code>{url[:45]}...</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            status_msg = await message.reply_text(
                "⏳ <b>جاري معالجة الرابط... / Processing link...</b>",
                parse_mode=ParseMode.HTML
            )

        await state.request_queue.put(("single", (url, custom_name, custom_caption), status_msg, message))


async def handle_queued_task(task_data):
    task_type = task_data[0]
    try:
        if task_type == "torrent":
            _, torrent_src, status_msg, user_msg = task_data
            await downloads.process_torrent_download(torrent_src, status_msg, user_msg)
        elif task_type == "zip_bundle":
            _, valid_requests, status_msg, user_msg = task_data
            await downloads.process_zip_bundle(valid_requests, status_msg, user_msg)
        else:
            _, (url, custom_name, custom_caption), status_msg, user_msg = task_data
            await fwdcache.handle_url_intake(url, custom_name, custom_caption, status_msg, user_msg)
    except Exception as e:
        logger.exception(f"Task error: {e}")
    finally:
        state.request_queue.task_done()
        gc.collect()


async def queue_worker():
    # DEF-25.2 / OQ-4: Concurrent asyncio.create_task dispatch preserved verbatim per owner ruling
    while True:
        task_data = await state.request_queue.get()
        asyncio.create_task(_self.handle_queued_task(task_data))


def register_intake_handlers(client: Client) -> None:
    if getattr(client, "_myidm_intake_registered", False):
        return
    client.on_message(filters.document & ~filters.service)(_self.handle_document_torrent)
    client.on_message((filters.text | filters.caption) & ~filters.service)(_self.handle_all_messages)
    setattr(client, "_myidm_intake_registered", True)
