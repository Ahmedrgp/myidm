import asyncio
import html
import json
import logging
import math
import os
import shutil
import sys
import time

from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import myidm  # noqa: F401
from myidm import apk_inspect
from myidm import clients
from myidm import config as cfg
from myidm import db
from myidm import dupguard
from myidm import keyboards
from myidm import state
from myidm import texts
from myidm import utils

logger = logging.getLogger("bot.upload")
_self = sys.modules[__name__]


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
    st = db.db_get_user_settings(user_id) if user_id else {}
    if custom_caption:
        caption = custom_caption
    elif not st.get("enable_caption", 1):
        caption = ""
    else:
        channel_tag = st.get("channel_tag", "").strip()
        caption_lines = [
            f"🎮 <b>File:</b> <code>{filename}</code>",
            f"{icon} <b>Category:</b> {category_desc}",
            f"📊 <b>Size:</b> <code>{utils.humanbytes(file_size)}</code>"
        ]
        if channel_tag:
            formatted_channel = f"@{channel_tag.lstrip('@')}" if not channel_tag.startswith("http") else channel_tag
            caption_lines.append(f"📢 <b>Channel:</b> {formatted_channel}")

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


async def process_single_local_file_upload(
    file_path: str,
    filename: str,
    actual_file_size: int,
    status_msg: Message,
    user_msg: Message,
    user_id: int,
    start_time: float,
    task_id: str,
    custom_caption: str = "",
    skip_dup_check: bool = False,
    precomputed_apk_info: dict | None = None,
    pending_id: int | None = None,
    url_key: str = ""
):
    settings = db.db_get_user_settings(user_id)
    lang = settings["lang"]
    filename = utils.clean_and_rename_filename(filename, user_id=user_id)
    if task_id in state.ACTIVE_TASKS:
        state.ACTIVE_TASKS[task_id]["filename"] = filename
    icon, category_desc, is_video_type = utils.get_god_category(filename)
    force_video = False if settings["upload_mode"] == "doc" else is_video_type

    # Duplicate check for APK family
    is_apk_family = (filename or "").lower().endswith((".apk", ".xapk", ".apks"))
    if is_apk_family and not skip_dup_check:
        if not precomputed_apk_info:
            loop = asyncio.get_running_loop()
            precomputed_apk_info = await loop.run_in_executor(None, apk_inspect.inspect_apk, file_path)
        if precomputed_apk_info:
            pkg = precomputed_apk_info.get("package")
            vcode = precomputed_apk_info.get("version_code")
            if pkg and vcode is not None:
                dup_record = db.db_check_apk_duplicate(pkg, vcode)
                if dup_record:
                    os.makedirs(cfg.PENDING_DIR, exist_ok=True)
                    dest_pending_name = f"pending_{int(time.time()*1000)}_{os.path.basename(file_path)}"
                    dest_pending_path = os.path.join(cfg.PENDING_DIR, dest_pending_name)
                    shutil.move(file_path, dest_pending_path)
                    new_pending_id = db.db_add_pending_download(
                        user_id=user_id,
                        chat_id=user_msg.chat.id,
                        file_path=dest_pending_path,
                        filename=filename,
                        custom_caption=custom_caption,
                        package=pkg,
                        version_name=str(precomputed_apk_info.get("version_name") or ""),
                        version_code=vcode,
                        size=actual_file_size,
                        status="pending",
                        inspection_json=json.dumps(precomputed_apk_info),
                        flow_type="torrent"
                    )
                    warn_text = dupguard.format_duplicate_warning_card(precomputed_apk_info, dup_record, lang=lang)
                    kb = keyboards.make_duplicate_keyboard(new_pending_id, lang=lang)
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    await user_msg.reply_text(warn_text, reply_markup=kb, parse_mode=ParseMode.HTML)
                    return
            else:
                logger.info(f"APK inspection degraded (pkg={pkg}, vcode={vcode}), proceeding without duplicate warning")

    BOT_LIMIT_BYTES = 1950 * 1024 * 1024
    SPLIT_CHUNK_BYTES = 1900 * 1024 * 1024
    uploader = clients.get_uploader_client()
    is_premium_active = (clients.user_bot is not None) and getattr(clients.user_bot, "is_connected", False) and (uploader == clients.user_bot)
    CHANNEL_ID = utils.parse_chat_id(os.environ.get("CHANNEL_ID", ""))

    if is_apk_family and not precomputed_apk_info and file_path and os.path.exists(file_path):
        loop = asyncio.get_running_loop()
        precomputed_apk_info = await loop.run_in_executor(None, apk_inspect.inspect_apk, file_path)

    if actual_file_size > BOT_LIMIT_BYTES:
        if is_premium_active and actual_file_size <= (3950 * 1024 * 1024):
            # Premium upload
            await keyboards.safe_edit_text(
                status_msg,
                f"📤 <b>{'جاري الرفع عبر Telegram Premium...' if lang == 'ar' else f'Uploading {utils.humanbytes(actual_file_size)} via Telegram Premium...'}</b>",
                parse_mode=ParseMode.HTML
            )
            up_start_time = time.time()
            last_update = [0]

            async def pyrogram_progress_prem(current, total):
                if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    return
                await keyboards.progress_bar(
                    current, total, ("رفع Premium" if lang == "ar" else "Premium upload"), status_msg, up_start_time, last_update, icon="📤", task_id=task_id, lang=lang
                )

            caption, brand_markup = _self.build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)
            target_chat = CHANNEL_ID if CHANNEL_ID else "me"
            is_vid = is_video_type and settings["upload_mode"] != "doc"
            thumb_path, duration, width, height = None, 0, 0, 0
            if is_vid and settings.get("enable_thumbs", 1):
                thumb_path, duration, width, height = await _self.extract_video_metadata(file_path)
            sent_msg = None
            try:
                try:
                    sent_msg = await _self.resilient_send_media(uploader, target_chat, file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)
                except Exception as prem_upload_err:
                    logger.warning(f"Direct premium upload target error, trying 'me': {prem_upload_err}")
                    sent_msg = await _self.resilient_send_media(uploader, "me", file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)
            finally:
                if thumb_path and os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except Exception:
                        pass

            total_time_spent = round(time.time() - start_time)
            avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
            db.db_add_history(user_id, filename, actual_file_size, category_desc)
            if url_key and sent_msg and hasattr(sent_msg, "id") and isinstance(sent_msg.id, int) and not isinstance(sent_msg.id, bool):
                deliv_chat = sent_msg.chat.id if hasattr(sent_msg, "chat") and sent_msg.chat else (target_chat if isinstance(target_chat, int) else user_msg.chat.id)
                apk_pkg = precomputed_apk_info.get("package") if (is_apk_family and precomputed_apk_info) else None
                apk_vc = precomputed_apk_info.get("version_code") if (is_apk_family and precomputed_apk_info) else None
                db.db_record_delivery(user_id, url_key, filename, actual_file_size, deliv_chat, [sent_msg.id], apk_pkg, apk_vc)
            await status_msg.delete()

            dest_text = f"القناة ({CHANNEL_ID})" if CHANNEL_ID else "الرسائل المحفوظة (Saved Messages)"
            prem_title = "<b>تم الرفع عبر Telegram Premium</b>" if lang == "ar" else "<b>Uploaded via Telegram Premium</b>"
            dest_lbl = "مكان الإرسال:" if lang == "ar" else "Destination:"
            success_card = (
                f"{prem_title}\n"
                f"{texts.tr(lang, 'file_name')} <code>{filename}</code>\n"
                f"{icon} {texts.tr(lang, 'category')} {category_desc}\n"
                f"{texts.tr(lang, 'final_size')} <code>{utils.humanbytes(actual_file_size)}</code>\n"
                f"📍 <b>{dest_lbl}</b> <code>{dest_text}</code>\n"
                f"{texts.tr(lang, 'total_time')} <code>{utils.time_formatter(total_time_spent)}</code>\n"
                f"{texts.tr(lang, 'avg_speed')} <code>{utils.humanbytes(avg_speed)}/s</code>"
            )
            await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
            await apk_inspect.handle_apk_inspection_card(file_path, filename, user_id, user_msg, lang, precomputed_info=precomputed_apk_info)
            if pending_id:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                db.db_update_pending_status(pending_id, "done")
            return
        else:
            # Splitting check
            ok_split, needed_s, free_s, reserve_s = utils.check_disk_space_for_split(cfg.DOWNLOAD_DIR, SPLIT_CHUNK_BYTES)
            if not ok_split:
                logger.error(f"Disk check failed before split: needed={needed_s}, free={free_s}, reserve={reserve_s}")
                needed_mb = f"{needed_s / (1024*1024):.1f} MB"
                free_mb = f"{free_s / (1024*1024):.1f} MB"
                reserve_mb = f"{reserve_s / (1024*1024):.1f} MB"
                err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
                await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
                return

            num_parts = math.ceil(actual_file_size / SPLIT_CHUNK_BYTES)
            await keyboards.safe_edit_text(
                status_msg,
                f"✂️ <b>{'تقسيم الملف إلى ' + str(num_parts) + ' أجزاء...' if lang == 'ar' else f'Splitting file into {num_parts} parts...'}</b>",
                parse_mode=ParseMode.HTML
            )
            part_number = 1
            deliv_part_ids = []
            ext = os.path.splitext(filename)[1]
            with open(file_path, "rb") as src_file:
                while True:
                    if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        return
                    chunk_data = src_file.read(SPLIT_CHUNK_BYTES)
                    if not chunk_data:
                        break
                    part_filename = f"{os.path.splitext(filename)[0]}.part{part_number:03d}{ext}"
                    part_filepath = os.path.join(cfg.DOWNLOAD_DIR, part_filename)
                    with open(part_filepath, "wb") as part_file:
                        part_file.write(chunk_data)
                    part_msg = await user_msg.reply_document(
                        document=part_filepath,
                        caption=f"🧩 <b>Part {part_number}/{num_parts}</b>\n📄 <code>{part_filename}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    if part_msg and hasattr(part_msg, "id") and isinstance(part_msg.id, int) and not isinstance(part_msg.id, bool):
                        deliv_part_ids.append(part_msg.id)
                    if os.path.exists(part_filepath):
                        os.remove(part_filepath)
                    part_number += 1
            total_time_spent = round(time.time() - start_time)
            avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
            db.db_add_history(user_id, filename, actual_file_size, category_desc)
            if url_key and deliv_part_ids:
                apk_pkg = precomputed_apk_info.get("package") if (is_apk_family and precomputed_apk_info) else None
                apk_vc = precomputed_apk_info.get("version_code") if (is_apk_family and precomputed_apk_info) else None
                db.db_record_delivery(user_id, url_key, filename, actual_file_size, user_msg.chat.id, deliv_part_ids, apk_pkg, apk_vc)
            await status_msg.delete()
            task_ssl_unverified = state.ACTIVE_TASKS.get(task_id, {}).get("ssl_unverified", False)
            extra_ssl_line = f"\n{cfg.TLS_VERIFICATION_SKIPPED_NOTICE}" if task_ssl_unverified else ""
            success_card = (
                f"{texts.tr(lang, 'success_title')}\n"
                f"{texts.tr(lang, 'file_name')} <code>{filename}</code>\n"
                f"{icon} {texts.tr(lang, 'category')} {category_desc}\n"
                f"{texts.tr(lang, 'final_size')} <code>{utils.humanbytes(actual_file_size)} ({num_parts} Parts)</code>\n"
                f"{texts.tr(lang, 'total_time')} <code>{utils.time_formatter(total_time_spent)}</code>\n"
                f"{texts.tr(lang, 'avg_speed')} <code>{utils.humanbytes(avg_speed)}/s</code>"
                f"{extra_ssl_line}"
            )
            await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
            await apk_inspect.handle_apk_inspection_card(file_path, filename, user_id, user_msg, lang, precomputed_info=precomputed_apk_info)
            if pending_id:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                db.db_update_pending_status(pending_id, "done")
            return

    await keyboards.safe_edit_text(status_msg, f"📤 <b>{texts.tr(lang, 'uploading')}</b>", parse_mode=ParseMode.HTML)
    up_start_time = time.time()
    last_update = [0]

    async def pyrogram_progress(current, total):
        await keyboards.progress_bar(current, total, texts.tr(lang, "uploading"), status_msg, up_start_time, last_update, icon="📤", task_id=task_id, lang=lang)

    caption, brand_markup = _self.build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)

    thumb_path = None
    duration, width, height = 0, 0, 0
    if force_video and settings.get("enable_thumbs", 1):
        thumb_path, duration, width, height = await _self.extract_video_metadata(file_path)

    sent_msg = None
    try:
        sent_msg = await _self.resilient_send_media(clients.bot, user_msg.chat.id, file_path, caption, force_video, pyrogram_progress, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)
        if CHANNEL_ID:
            try:
                uploader = clients.get_uploader_client()
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
    finally:
        if thumb_path and os.path.exists(thumb_path):
            try: os.remove(thumb_path)
            except Exception: pass

    total_time_spent = round(time.time() - start_time)
    avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
    db.db_add_history(user_id, filename, actual_file_size, category_desc)
    if url_key and sent_msg and hasattr(sent_msg, "id") and isinstance(sent_msg.id, int) and not isinstance(sent_msg.id, bool):
        apk_pkg = precomputed_apk_info.get("package") if (is_apk_family and precomputed_apk_info) else None
        apk_vc = precomputed_apk_info.get("version_code") if (is_apk_family and precomputed_apk_info) else None
        db.db_record_delivery(user_id, url_key, filename, actual_file_size, user_msg.chat.id, [sent_msg.id], apk_pkg, apk_vc)
    await status_msg.delete()
    task_ssl_unverified = state.ACTIVE_TASKS.get(task_id, {}).get("ssl_unverified", False)
    extra_ssl_line = f"\n{cfg.TLS_VERIFICATION_SKIPPED_NOTICE}" if task_ssl_unverified else ""

    success_card = (
        f"{texts.tr(lang, 'success_title')}\n"
        f"{texts.tr(lang, 'file_name')} <code>{filename}</code>\n"
        f"{icon} {texts.tr(lang, 'category')} {category_desc}\n"
        f"{texts.tr(lang, 'final_size')} <code>{utils.humanbytes(actual_file_size)}</code>\n"
        f"{texts.tr(lang, 'total_time')} <code>{utils.time_formatter(total_time_spent)}</code>\n"
        f"{texts.tr(lang, 'avg_speed')} <code>{utils.humanbytes(avg_speed)}/s</code>"
        f"{extra_ssl_line}"
    )
    await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
    await apk_inspect.handle_apk_inspection_card(file_path, filename, user_id, user_msg, lang, precomputed_info=precomputed_apk_info)
    if pending_id:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        db.db_update_pending_status(pending_id, "done")


async def run_approved_pending_upload(pending_id: int, original_msg: Message):
    row = db.db_get_pending_download(pending_id)
    if not row:
        return
    fpath = row["file_path"]
    fname = row["filename"]
    uid = row["user_id"]
    custom_caption = row.get("custom_caption", "")
    settings = db.db_get_user_settings(uid)
    lang = settings["lang"]

    if not fpath or not os.path.exists(fpath):
        db.db_update_pending_status(pending_id, "expired")
        await original_msg.reply_text(texts.tr(lang, "dup_file_missing_alert"), parse_mode=ParseMode.HTML)
        return

    fsize = os.path.getsize(fpath)
    precomputed = None
    if row.get("inspection_json"):
        try:
            precomputed = json.loads(row["inspection_json"])
        except Exception:
            pass

    url_key = row.get("url_key", "")
    if not url_key and precomputed and isinstance(precomputed, dict):
        url_key = precomputed.get("url_key", "")

    status_msg = await original_msg.reply_text(
        f"📤 <b>{texts.tr(lang, 'uploading')}</b>",
        parse_mode=ParseMode.HTML
    )
    task_id = f"task_{int(time.time() * 1000)}"
    state.ACTIVE_TASKS[task_id] = {"cancelled": False}
    start_time = time.time()

    try:
        await _self.process_single_local_file_upload(
            file_path=fpath,
            filename=fname,
            actual_file_size=fsize,
            status_msg=status_msg,
            user_msg=original_msg,
            user_id=uid,
            start_time=start_time,
            task_id=task_id,
            custom_caption=custom_caption,
            skip_dup_check=True,
            precomputed_apk_info=precomputed,
            pending_id=pending_id,
            url_key=url_key
        )
    except Exception as e:
        logger.error(f"Error uploading approved pending download {pending_id}: {e}", exc_info=True)
        try:
            await keyboards.safe_edit_text(status_msg, f"❌ <b>Upload Error:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
