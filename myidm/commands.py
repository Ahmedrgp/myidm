import asyncio
import logging
import sys
import time
import urllib.parse

import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import myidm  # noqa: F401
from myidm import config as cfg
from myidm import db
from myidm import keyboards
from myidm import resolvers
from myidm import state
from myidm import texts
from myidm import utils

logger = logging.getLogger("bot.commands")
_self = sys.modules[__name__]


# ==========================================
# 9. معالجات الرسائل والأوامر المزدوجة
# ==========================================
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        await message.reply_text("⛔ <b>عذراً، هذا البوت خاص ومخصص للاستخدام الشخصي للمالك فقط.</b>", parse_mode=ParseMode.HTML)
        return
    db.db_add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    st = db.db_get_user_settings(user_id)
    sender = message.from_user.first_name if message.from_user else 'Master'
    is_admin_user = cfg.is_admin(user_id)
    
    welcome_text = texts.tr(st["lang"], "welcome", name=sender)
    try:
        await message.reply_text(welcome_text, reply_markup=keyboards.make_start_keyboard(st["lang"], is_admin=is_admin_user), parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await message.reply_text(welcome_text, reply_markup=keyboards.make_start_keyboard(st["lang"], is_admin=is_admin_user), parse_mode=ParseMode.HTML)


async def god_panel_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
    g_stats = db.db_get_global_stats()
    
    god_card = texts.tr(st["lang"], "god_panel", threads=st['god_threads'], files=g_stats['files'], bytes=utils.humanbytes(g_stats['bytes']))
    try:
        await message.reply_text(god_card, reply_markup=keyboards.make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await message.reply_text(god_card, reply_markup=keyboards.make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)


async def probe_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("❌ URL required: <code>/probe URL</code>", parse_mode=ParseMode.HTML)
        return
    
    raw_url = args[1].strip()
    status_msg = await message.reply_text("🔎 <b>Inspecting URL / جاري الفحص...</b>", parse_mode=ParseMode.HTML)
    
    try:
        direct_url = await resolvers.unrestrict_direct_link(raw_url)
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

        if cfg.CURL_CFFI_AVAILABLE:
            headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
            if custom_cookie:
                headers["Cookie"] = custom_cookie
            async with cfg.CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                resp = await session.get(direct_url, headers=headers, stream=True)
                status = resp.status_code
                clen = resp.headers.get("Content-Length") or resp.headers.get("content-length") or ""
                crange = resp.headers.get("Content-Range") or resp.headers.get("content-range") or ""
                if "/" in crange:
                    clen = crange.split("/")[1].strip()
                if not clen:
                    clen = "N/A"
                ctype = resp.headers.get("Content-Type") or resp.headers.get("content-type") or "N/A"
                fname = utils.smart_extract_filename(direct_url, resp.headers)
        else:
            timeout = aiohttp.ClientTimeout(total=15, sock_connect=10)
            headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
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
                    fname = utils.smart_extract_filename(direct_url, resp.headers)

        icon, category, _ = utils.get_god_category(fname)
        size_str = utils.humanbytes(int(clen)) if clen.isdigit() else clen
        
        # DEF-13: Hardcoded "OK" after HTTP status preserved verbatim per owner ruling (IBC-03 excluded)
        probe_card = (
            f"🔎 <b>Probe Report:</b>\n"
            f"📄 <b>File:</b> <code>{fname}</code>\n"
            f"{icon} <b>Category:</b> <code>{category}</code>\n"
            f"📊 <b>Size:</b> <code>{size_str}</code>\n"
            f"🌐 <b>HTTP Code:</b> <code>{status} OK</code>\n"
            f"🏷️ <b>Type:</b> <code>{ctype}</code>"
        )
        await status_msg.edit_text(probe_card, parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Probe Failed / فشل الفحص:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)


async def settings_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
    await message.reply_text(
        texts.tr(st["lang"], "settings_title"),
        reply_markup=keyboards.make_settings_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )


async def help_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
    await message.reply_text(texts.tr(st["lang"], "help_text"), reply_markup=keyboards.make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)


async def stats_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
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
    await message.reply_text(stats_text, reply_markup=keyboards.make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)


async def history_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    st = db.db_get_user_settings(user_id)
    history_list = db.db_get_history(user_id, limit=10)
    
    if not history_list:
        text = "📜 <b>No download history found / لا يوجد سجل تحميلات بعد.</b>"
    else:
        text = "📜 <b>Latest Downloads / أحدث التحميلات:</b>\n"
        for i, (fname, fsize, fcat, fts) in enumerate(history_list, 1):
            t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(fts))
            text += f"{i}. 📄 <code>{fname}</code>\n   🏷️ {fcat} | 📊 {utils.humanbytes(fsize)} | ⏱️ {t_str}\n\n"
        text = text.rstrip()

    await message.reply_text(text, reply_markup=keyboards.make_back_keyboard(st["lang"]), parse_mode=ParseMode.HTML)


async def broadcast_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
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
    user_ids = db.db_get_all_user_ids()
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
        f"📢 <b>نتيجة الإذاعة:</b>\n"
        f"👥 <b>المستخدمون:</b> <code>{total_users}</code>\n"
        f"✅ <b>تم الإرسال:</b> <code>{success_count}</code>\n"
        f"❌ <b>فشل:</b> <code>{failed_count}</code>"
    )
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML)


async def set_prefix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("🏷️ <b>الاستخدام:</b> <code>/set_prefix [بادئة الاسم]</code>\nمثال: <code>/set_prefix @MyChannel -</code>", parse_mode=ParseMode.HTML)
        return
    new_prefix = args[1].strip()
    db.db_update_user_setting(user_id, "custom_prefix", new_prefix)
    await message.reply_text(f"✅ <b>تم ضبط البادئة المخصصة بنجاح:</b> <code>{new_prefix}</code>", parse_mode=ParseMode.HTML)


async def clear_prefix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    db.db_update_user_setting(user_id, "custom_prefix", "")
    await message.reply_text("✅ <b>تم حذف البادئة المخصصة بنجاح.</b>", parse_mode=ParseMode.HTML)


async def set_suffix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("🏷️ <b>الاستخدام:</b> <code>/set_suffix [لاحقة الاسم]</code>\nمثال: <code>/set_suffix - @MyChannel</code>", parse_mode=ParseMode.HTML)
        return
    new_suffix = args[1].strip()
    db.db_update_user_setting(user_id, "custom_suffix", new_suffix)
    await message.reply_text(f"✅ <b>تم ضبط اللاحقة المخصصة بنجاح:</b> <code>{new_suffix}</code>", parse_mode=ParseMode.HTML)


async def clear_suffix_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    db.db_update_user_setting(user_id, "custom_suffix", "")
    await message.reply_text("✅ <b>تم حذف اللاحقة المخصصة بنجاح.</b>", parse_mode=ParseMode.HTML)


async def replace_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
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
    db.db_add_replacement(user_id, find_txt, replace_txt)
    action_text = "بحذفه" if not replace_txt else f"بـ <code>{replace_txt}</code>"
    await message.reply_text(f"✅ <b>تمت إضافة قاعدة الاستبدال:</b> استبدال <code>{find_txt}</code> {action_text}", parse_mode=ParseMode.HTML)


async def list_replacements_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    rules = db.db_get_user_replacements(user_id)
    st = db.db_get_user_settings(user_id)
    clean_state = "✅ مفعل" if st.get("clean_tags", 1) else "❌ معطل"
    prefix = st.get("custom_prefix", "") or "لا يوجد"
    suffix = st.get("custom_suffix", "") or "لا يوجد"
    
    text = (
        f"🛠️ <b>إعدادات تسمية الملفات:</b>\n"
        f"🧹 <b>تنظيف الوسوم:</b> <code>{clean_state}</code>\n"
        f"🏷️ <b>البادئة:</b> <code>{prefix}</code>\n"
        f"🏷️ <b>اللاحقة:</b> <code>{suffix}</code>\n\n"
        f"📋 <b>قواعد الاستبدال ({len(rules)}):</b>\n"
    )
    if not rules:
        text += "<i>لا توجد قواعد استبدال مخصصة بعد.</i>\n"
    else:
        for i, (f_txt, r_txt) in enumerate(rules, 1):
            repl_disp = f"'{r_txt}'" if r_txt else "[حذف]"
            text += f"{i}. <code>{f_txt}</code> ➔ <code>{repl_disp}</code>\n"
    text += (
        f"\n💡 <i>لحذف جميع القواعد: <code>/clear_replacements</code></i>"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def clear_replacements_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    db.db_clear_user_replacements(user_id)
    await message.reply_text("✅ <b>تم مسح جميع قواعد استبدال النصوص الخاصة بك بنجاح.</b>", parse_mode=ParseMode.HTML)


async def brand_command_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        new_brand = args[1].strip()
        if not new_brand.startswith("@") and not new_brand.startswith("http"):
            new_brand = f"@{new_brand}"
        db.db_update_user_setting(user_id, "channel_tag", new_brand)
        # DEF-14: Hardcoded confirmation summary preserved verbatim per owner ruling (IBC-03 excluded)
        await message.reply_text(
            f"<b>تم تفعيل حقوق القناة:</b>\n"
            f"📢 <b>القناة:</b> <code>{new_brand}</code>\n"
            f"🏷️ <b>الموضع:</b> <code>في النهاية (Suffix)</code>\n"
            f"🔘 <b>الزر التفاعلي:</b> <code>مفعل ✅</code>\n"
            f"📝 <b>الكابشن:</b> <code>مفعل ✅</code>\n\n"
            f"💡 لإدارة الخيارات: <code>/brand</code>",
            reply_markup=keyboards.make_brand_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
        return
    
    st = db.db_get_user_settings(user_id)
    cur_brand = st.get("channel_tag") or "غير محدد ❌"
    await message.reply_text(
        f"<b>إدارة حقوق القناة:</b>\n"
        f"📢 <b>القناة الحالية:</b> <code>{cur_brand}</code>\n\n"
        f"💡 <b>التعيين:</b> <code>/brand @اسم_قناتك</code>\n"
        f"💡 <b>الحذف:</b> <code>/clear_brand</code>",
        reply_markup=keyboards.make_brand_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )


async def clear_brand_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not cfg.is_admin(user_id):
        return
    db.db_update_user_setting(user_id, "channel_tag", "")
    await message.reply_text("✅ <b>تم حذف حقوق القناة التلقائية بنجاح. ستنزل الملفات بدون وسم القناة.</b>", parse_mode=ParseMode.HTML)


def register_command_handlers(client: Client) -> None:
    if getattr(client, "_myidm_commands_registered", False):
        return
    client.on_message(filters.command("start"))(_self.start_handler)
    client.on_message(filters.command("god") | filters.command("godmode") | filters.command("omnipotent"))(_self.god_panel_handler)
    client.on_message(filters.command("probe"))(_self.probe_command_handler)
    client.on_message(filters.command("settings") | filters.command("lang"))(_self.settings_command_handler)
    client.on_message(filters.command("help"))(_self.help_command_handler)
    client.on_message(filters.command("stats"))(_self.stats_command_handler)
    client.on_message(filters.command("history"))(_self.history_command_handler)
    client.on_message(filters.command("broadcast"))(_self.broadcast_command_handler)
    client.on_message(filters.command(["set_prefix", "prefix"]))(_self.set_prefix_handler)
    client.on_message(filters.command(["clear_prefix", "cleanprefix"]))(_self.clear_prefix_handler)
    client.on_message(filters.command(["set_suffix", "suffix"]))(_self.set_suffix_handler)
    client.on_message(filters.command(["clear_suffix", "cleansuffix"]))(_self.clear_suffix_handler)
    client.on_message(filters.command("replace"))(_self.replace_command_handler)
    client.on_message(filters.command(["replacements", "rules"]))(_self.list_replacements_handler)
    client.on_message(filters.command("clear_replacements"))(_self.clear_replacements_handler)
    client.on_message(filters.command(["brand", "branding", "set_brand", "set_channel", "channel"]))(_self.brand_command_handler)
    client.on_message(filters.command(["clear_brand", "clear_channel"]))(_self.clear_brand_handler)
    setattr(client, "_myidm_commands_registered", True)
