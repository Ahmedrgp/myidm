import asyncio
import logging
import sys

from pyrogram import Client, idle
from pyrogram.utils import loops
from pyrogram.types import BotCommand

import myidm  # noqa: F401
from myidm import callbacks
from myidm import clients
from myidm import commands
from myidm import config as cfg
from myidm import dashboard
from myidm import db
from myidm import downloads
from myidm import intake

logger = logging.getLogger("bot.app")

# ==========================================
# 5. إعداد عميل Pyrogram الفائق (16 Workers & Multi-DC Parallel Transfers)
# ==========================================
bot = Client(
    "downloader_bot",
    api_id=cfg.API_ID,
    api_hash=cfg.API_HASH,
    bot_token=cfg.BOT_TOKEN,
    workdir=cfg.DATA_DIR,
    workers=16
)

user_bot = None
if cfg.USER_SESSION_STRING:
    user_bot = Client(
        "premium_user_uploader",
        api_id=cfg.API_ID,
        api_hash=cfg.API_HASH,
        session_string=cfg.USER_SESSION_STRING,
        workdir=cfg.DATA_DIR,
        workers=16
    )

clients.register_clients(bot, user_bot)

commands.register_command_handlers(bot)
callbacks.register_callback_handlers(bot)
intake.register_intake_handlers(bot)


async def background_cleaner_worker():
    """
    Periodic hourly background cleaner:
    - Cleans expired pending_downloads older than 24 hours
    - Cleans DOWNLOAD_DIR orphan files older than 6 hours
    """
    while True:
        try:
            await asyncio.sleep(3600)
            db.cleanup_expired_pending_downloads()
            downloads.cleanup_temp_dir(max_age_hours=6.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error in background_cleaner_worker: {e}")


# ==========================================
# 13. نقطة البداية وتشغيل البوت (Main Entry Point)
# ==========================================
async def main():
    if not cfg.API_ID or not cfg.API_HASH or not cfg.BOT_TOKEN:
        logger.error("❌ API_ID, API_HASH, or BOT_TOKEN missing!")
        sys.exit(1)

    downloads.cleanup_temp_dir(max_age_hours=6.0)
    db.cleanup_expired_pending_downloads()
    await dashboard.start_web_server()
    asyncio.create_task(intake.queue_worker())
    asyncio.create_task(background_cleaner_worker())

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
            BotCommand("start", "Main Menu / القائمة الرئيسية"),
            BotCommand("omnipotent", "Control Panel / لوحة التحكم"),
            BotCommand("probe", "🔎 Inspect Direct URL / فحص الرابط"),
            BotCommand("settings", "⚙️ Language & Settings / الإعدادات واللغة"),
            BotCommand("help", "📜 Usage Guide / دليل الاستخدام"),
            BotCommand("history", "📜 History / سجل التحميلات"),
            BotCommand("stats", "📊 Engine Stats / إحصائيات المحرك"),
            BotCommand("broadcast", "📢 Broadcast message / إذاعة عامة (Admin)"),
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


def run():
    try:
        loops.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
