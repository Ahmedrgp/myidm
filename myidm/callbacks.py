import asyncio
import logging
import os
import sys
import time

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import myidm  # noqa: F401
from myidm import config as cfg
from myidm import db
from myidm import fwdcache
from myidm import keyboards
from myidm import state
from myidm import texts
from myidm import upload
from myidm import utils

logger = logging.getLogger("bot.callbacks")
_self = sys.modules[__name__]
tr = texts.tr


async def callback_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        user_id = query.from_user.id if query.from_user else 0
        if not cfg.is_admin(user_id):
            await query.answer("⛔ ليس لديك صلاحية لاستخدام هذا البوت.", show_alert=True)
            return
        st = db.db_get_user_settings(user_id)
        lang = st["lang"]
        
        if data.startswith("cancel_"):
            task_id = data.split("cancel_", 1)[1]
            if task_id in state.ACTIVE_TASKS:
                state.ACTIVE_TASKS[task_id]["cancelled"] = True
                await query.answer("🛑 Task cancelled / تم الإلغاء...", show_alert=True)
            else:
                await query.answer("⚠️ Task already completed.", show_alert=True)
            return

        if data.startswith("dup_go_"):
            pending_id_str = data.split("dup_go_", 1)[1]
            try:
                pending_id = int(pending_id_str)
            except ValueError:
                await query.answer("Invalid ID", show_alert=True)
                return
            row = db.db_get_pending_download(pending_id)
            if not row:
                await query.answer(tr(lang, "dup_expired_alert"), show_alert=True)
                return
            if row["status"] == "done":
                await query.answer(tr(lang, "dup_already_done_alert"), show_alert=True)
                return
            if row["status"] == "cancelled":
                await query.answer(tr(lang, "dup_already_cancelled_alert"), show_alert=True)
                return
            if row["status"] == "expired":
                await query.answer(tr(lang, "dup_expired_alert"), show_alert=True)
                return
            fpath = row["file_path"]
            if not fpath or not os.path.exists(fpath):
                db.db_update_pending_status(pending_id, "expired")
                await query.answer(tr(lang, "dup_file_missing_alert"), show_alert=True)
                return

            db.db_update_pending_status(pending_id, "approved")
            await query.answer()
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            asyncio.create_task(upload.run_approved_pending_upload(pending_id, query.message))
            return

        # DEF-15: Missing expired guard in dup_no_ preserved verbatim per owner ruling (IBC-03 excluded)
        if data.startswith("dup_no_"):
            pending_id_str = data.split("dup_no_", 1)[1]
            try:
                pending_id = int(pending_id_str)
            except ValueError:
                await query.answer("Invalid ID", show_alert=True)
                return
            row = db.db_get_pending_download(pending_id)
            if not row:
                await query.answer(tr(lang, "dup_expired_alert"), show_alert=True)
                return
            if row["status"] == "cancelled":
                await query.answer(tr(lang, "dup_already_cancelled_alert"), show_alert=True)
                return
            if row["status"] == "done":
                await query.answer(tr(lang, "dup_already_done_alert"), show_alert=True)
                return
            fpath = row["file_path"]
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception as e:
                    logger.warning(f"Error deleting pending file {fpath}: {e}")
            db.db_update_pending_status(pending_id, "cancelled")
            await query.answer()
            try:
                await query.message.edit_text(tr(lang, "dup_cancelled_notice"), parse_mode=ParseMode.HTML)
            except Exception:
                pass
            return

        if data.startswith("fwd_fresh_"):
            delivery_id_str = data.split("fwd_fresh_", 1)[1]
            try:
                delivery_id = int(delivery_id_str)
            except ValueError:
                await query.answer("Invalid ID", show_alert=True)
                return
            delivery = db.db_get_delivery_by_id(delivery_id)
            if not delivery:
                await query.answer("Record not found / السجل غير موجود", show_alert=True)
                return
            await query.answer()
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            status_msg = await query.message.reply_text(
                "⏳ <b>جاري معالجة الرابط... / Processing link...</b>",
                parse_mode=ParseMode.HTML
            )
            asyncio.create_task(fwdcache.run_fresh_download(delivery_id, query.message, status_msg=status_msg, forced_user_id=delivery["user_id"]))
            return

        if data == "toggle_lang":
            new_lang = "en" if lang == "ar" else "ar"
            db.db_update_user_setting(user_id, "lang", new_lang)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer("Language updated! / تم تغيير اللغة!", show_alert=True)
            return

        elif data == "toggle_mode":
            new_mode = "doc" if st["upload_mode"] == "auto" else "auto"
            db.db_update_user_setting(user_id, "upload_mode", new_mode)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer("Upload mode toggled!")
            return

        elif data == "toggle_threads":
            thread_modes = [16, 32, 64]
            curr_idx = thread_modes.index(st["god_threads"]) if st["god_threads"] in thread_modes else 0
            new_threads = thread_modes[(curr_idx + 1) % len(thread_modes)]
            db.db_update_user_setting(user_id, "god_threads", new_threads)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer(f"Threads updated to {new_threads}x!")
            return

        elif data == "toggle_caption":
            new_val = 0 if st.get("enable_caption", 1) else 1
            db.db_update_user_setting(user_id, "enable_caption", new_val)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer("Caption preference updated!")
            return

        elif data == "toggle_thumbs":
            new_val = 0 if st.get("enable_thumbs", 1) else 1
            db.db_update_user_setting(user_id, "enable_thumbs", new_val)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer("Thumbnail preference updated!")
            return

        elif data == "toggle_cleantags":
            new_val = 0 if st.get("clean_tags", 1) else 1
            db.db_update_user_setting(user_id, "clean_tags", new_val)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_settings_keyboard(user_id))
            await query.answer("Tag cleaner updated / تم تحديث تفضيل تنظيف الوسوم!")
            return

        elif data == "btn_open_brand":
            st = db.db_get_user_settings(user_id)
            cur_brand = st.get("channel_tag") or "غير محدد ❌"
            await query.message.edit_text(
                f"<b>إدارة حقوق القناة:</b>\n"
                f"📢 <b>القناة الحالية:</b> <code>{cur_brand}</code>\n\n"
                f"💡 <b>التعيين:</b> <code>/brand @اسم_قناتك</code>\n"
                f"💡 <b>الحذف:</b> <code>/clear_brand</code>",
                reply_markup=keyboards.make_brand_keyboard(user_id),
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
            db.db_update_user_setting(user_id, "brand_position", new_pos)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_brand_keyboard(user_id))
            await query.answer(f"تم تغيير موضع الاسم إلى: {new_pos}!")
            return

        elif data == "toggle_brand_btn":
            new_val = 0 if st.get("channel_button", 1) else 1
            db.db_update_user_setting(user_id, "channel_button", new_val)
            await query.message.edit_reply_markup(reply_markup=keyboards.make_brand_keyboard(user_id))
            await query.answer("تم تحديث حالة زر القناة التفاعلي!")
            return

        elif data == "btn_clear_brand":
            db.db_update_user_setting(user_id, "channel_tag", "")
            await query.message.edit_reply_markup(reply_markup=keyboards.make_brand_keyboard(user_id))
            await query.answer("تم حذف وسم القناة!", show_alert=True)
            return

        elif data == "btn_settings":
            await query.message.edit_text(
                tr(st["lang"], "settings_title"),
                reply_markup=keyboards.make_settings_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
            return

        if data == "btn_start":
            sender = query.from_user.first_name if query.from_user else 'Master'
            is_admin_user = cfg.is_admin(user_id)
            await query.message.edit_text(tr(lang, "welcome", name=sender), reply_markup=keyboards.make_start_keyboard(lang, is_admin=is_admin_user), parse_mode=ParseMode.HTML)

        elif data == "btn_admin_panel":
            # DEF-06: Redundant admin check preserved verbatim per owner ruling (OQ-3 / IBC-05)
            if not cfg.is_admin(user_id):
                await query.answer("⛔ هذا القسم مخصص لمالك البوت فقط!", show_alert=True)
                return
            g_stats = db.db_get_global_stats()
            queue_size = state.request_queue.qsize()
            uptime_sec = int(time.time() - cfg.START_TIME)
            admin_card = (
                f"<b>لوحة المسؤول (Admin)</b>\n"
                f"👥 <b>المستخدمون:</b> <code>{g_stats['users']}</code>\n"
                f"📄 <b>إجمالي الملفات:</b> <code>{g_stats['files']}</code>\n"
                f"📊 <b>إجمالي البيانات:</b> <code>{utils.humanbytes(g_stats['bytes'])}</code>\n"
                f"⏳ <b>طابور الانتظار:</b> <code>{queue_size}</code>\n"
                f"⏱️ <b>مدة التشغيل:</b> <code>{utils.time_formatter(uptime_sec)}</code>\n\n"
                f"📢 <b>للإذاعة:</b> <code>/broadcast النص</code>"
            )
            admin_kbd = InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]
            ])
            await query.message.edit_text(admin_card, reply_markup=admin_kbd, parse_mode=ParseMode.HTML)

        elif data == "btn_god_panel":
            g_stats = db.db_get_global_stats()
            god_card = tr(lang, "god_panel", threads=st['god_threads'], files=g_stats['files'], bytes=utils.humanbytes(g_stats['bytes']))
            await query.message.edit_text(god_card, reply_markup=keyboards.make_back_keyboard(lang), parse_mode=ParseMode.HTML)

        elif data == "btn_probe_info":
            await query.message.edit_text(tr(lang, "probe_info"), reply_markup=keyboards.make_back_keyboard(lang), parse_mode=ParseMode.HTML)

        # DEF-06: Unreachable duplicate btn_settings branch preserved verbatim per owner ruling (OQ-3)
        elif data == "btn_settings":
            await query.message.edit_text(
                tr(lang, "settings_title"),
                reply_markup=keyboards.make_settings_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
        
        # DEF-07: Orphan btn_help branch preserved verbatim per owner ruling (OQ-3)
        elif data == "btn_help":
            await query.message.edit_text(tr(lang, "help_text"), reply_markup=keyboards.make_back_keyboard(lang), parse_mode=ParseMode.HTML)

        elif data == "btn_history":
            history_list = db.db_get_history(user_id, limit=10)
            if not history_list:
                text = "📜 <b>No download history found / لا يوجد سجل تحميلات بعد.</b>"
            else:
                text = "📜 <b>Latest Downloads / أحدث التحميلات:</b>\n"
                for i, (fname, fsize, fcat, fts) in enumerate(history_list, 1):
                    t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(fts))
                    text += f"{i}. 📄 <code>{fname}</code>\n   🏷️ {fcat} | 📊 {utils.humanbytes(fsize)} | ⏱️ {t_str}\n\n"
                text = text.rstrip()
            await query.message.edit_text(text, reply_markup=keyboards.make_back_keyboard(lang), parse_mode=ParseMode.HTML)

        elif data == "btn_stats":
            g_stats = db.db_get_global_stats()
            queue_size = state.request_queue.qsize()
            uptime_sec = int(time.time() - cfg.START_TIME)
            stats_text = (
                f"📊 <b>الإحصائيات / Stats:</b>\n"
                f"⏱️ <b>Uptime:</b> <code>{utils.time_formatter(uptime_sec)}</code>\n"
                f"📄 <b>Total Files:</b> <code>{g_stats['files']}</code>\n"
                f"📊 <b>Total Bytes:</b> <code>{utils.humanbytes(g_stats['bytes'])}</code>\n"
                f"⏳ <b>Queue Size:</b> <code>{queue_size}</code>"
            )
            await query.message.edit_text(stats_text, reply_markup=keyboards.make_back_keyboard(lang), parse_mode=ParseMode.HTML)

        await query.answer()
    except MessageNotModified:
        try:
            await query.answer()
        except Exception:
            pass
    except Exception as cb_err:
        logger.warning(f"Callback query handler notice: {cb_err}")


def register_callback_handlers(client: Client) -> None:
    if getattr(client, "_myidm_callbacks_registered", False):
        return
    client.on_callback_query()(_self.callback_handler)
    setattr(client, "_myidm_callbacks_registered", True)
