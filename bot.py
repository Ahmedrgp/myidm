import asyncio
import os
import sys
import json
import time
import math
import re
import gc
import zipfile
import urllib.parse
import html
import hashlib
import shutil
import struct
import datetime
import ssl
import aiohttp
from aiohttp import web
from zoneinfo import ZoneInfo
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs7
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, RPCError, MessageNotModified

import myidm
from myidm import config as cfg
from myidm import state
from myidm import texts
from myidm import db
from myidm import utils
from myidm import clients
from myidm import keyboards
from myidm import validation
from myidm import dupguard
from myidm import apk_inspect
from myidm import resolvers
from myidm import upload
from myidm import downloads
from myidm import fwdcache
from myidm import commands
from myidm import callbacks
from myidm import intake
from myidm import dashboard

# Transitional Phase 1-5 re-exports for un-moved code in bot.py and un-migrated tests
_safe_ok_parse_json = myidm._safe_ok_parse_json
logger = cfg.logger
psutil = cfg.psutil
PSUTIL_AVAILABLE = cfg.PSUTIL_AVAILABLE
CurlAsyncSession = cfg.CurlAsyncSession
CURL_CFFI_AVAILABLE = cfg.CURL_CFFI_AVAILABLE
TorrentDownloader = cfg.TorrentDownloader
TORRENTP_AVAILABLE = cfg.TORRENTP_AVAILABLE
yt_dlp = cfg.yt_dlp
YTDLP_AVAILABLE = cfg.YTDLP_AVAILABLE
API_ID = cfg.API_ID
API_HASH = cfg.API_HASH
BOT_TOKEN = cfg.BOT_TOKEN
PORT = cfg.PORT
ADMIN_IDS = cfg.ADMIN_IDS
ADMIN_ID = cfg.ADMIN_ID
is_admin = cfg.is_admin
_owner_filter = cfg._owner_filter
owner_filter = cfg.owner_filter
USER_SESSION_STRING = cfg.USER_SESSION_STRING
MAX_SINGLE_FILE_SIZE = cfg.MAX_SINGLE_FILE_SIZE
SPLIT_PART_SIZE = cfg.SPLIT_PART_SIZE
BASE_TMP = cfg.BASE_TMP
START_TIME = cfg.START_TIME
STEALTH_HEADERS = cfg.STEALTH_HEADERS
TLS_VERIFICATION_SKIPPED_NOTICE = cfg.TLS_VERIFICATION_SKIPPED_NOTICE

ACTIVE_TASKS = state.ACTIVE_TASKS
request_queue = state.request_queue

TEXTS = texts.TEXTS
tr = texts.tr

ALLOWED_USER_SETTINGS = db.ALLOWED_USER_SETTINGS
get_or_create_dashboard_secret = db.get_or_create_dashboard_secret
init_db = db.init_db
db_add_user = db.db_add_user
db_get_user_settings = db.db_get_user_settings
db_add_replacement = db.db_add_replacement
db_get_user_replacements = db.db_get_user_replacements
db_clear_user_replacements = db.db_clear_user_replacements
db_get_total_users_count = db.db_get_total_users_count
db_update_user_setting = db.db_update_user_setting
db_add_history = db.db_add_history
db_get_history = db.db_get_history
db_add_apk_inspection = db.db_add_apk_inspection
db_get_last_inspection_for_package = db.db_get_last_inspection_for_package
db_check_apk_duplicate = db.db_check_apk_duplicate
db_add_pending_download = db.db_add_pending_download
db_get_pending_download = db.db_get_pending_download
db_update_pending_status = db.db_update_pending_status
db_record_delivery = db.db_record_delivery
db_get_delivery = db.db_get_delivery
db_get_delivery_by_id = db.db_get_delivery_by_id
db_delete_delivery = db.db_delete_delivery
db_get_apk_inspection = db.db_get_apk_inspection
cleanup_expired_pending_downloads = db.cleanup_expired_pending_downloads
db_get_all_user_ids = db.db_get_all_user_ids
db_get_global_stats = db.db_get_global_stats

humanbytes = utils.humanbytes
time_formatter = utils.time_formatter
format_cairo_time = utils.format_cairo_time
get_god_category = utils.get_god_category
sanitize_filename = utils.sanitize_filename
clean_and_rename_filename = utils.clean_and_rename_filename
smart_extract_filename = utils.smart_extract_filename
parse_chat_id = utils.parse_chat_id
check_disk_space = utils.check_disk_space
check_disk_space_for_split = utils.check_disk_space_for_split

make_start_keyboard = keyboards.make_start_keyboard
make_settings_keyboard = keyboards.make_settings_keyboard
make_brand_keyboard = keyboards.make_brand_keyboard
make_back_keyboard = keyboards.make_back_keyboard
make_cancel_keyboard = keyboards.make_cancel_keyboard
make_duplicate_keyboard = keyboards.make_duplicate_keyboard
progress_bar = keyboards.progress_bar
safe_edit_text = keyboards.safe_edit_text

is_valid_binary_file = validation.is_valid_binary_file
extract_video_embed_from_html = validation.extract_video_embed_from_html
extract_real_download_link_from_html = validation.extract_real_download_link_from_html
is_cert_verification_error = validation.is_cert_verification_error

format_duplicate_warning_card = dupguard.format_duplicate_warning_card

compute_file_sha256 = apk_inspect.compute_file_sha256
format_dn = apk_inspect.format_dn
parse_axml = apk_inspect.parse_axml
extract_v1_cert = apk_inspect.extract_v1_cert
extract_v2_v3_cert = apk_inspect.extract_v2_v3_cert
inspect_apk = apk_inspect.inspect_apk
format_apk_inspection_card = apk_inspect.format_apk_inspection_card
format_signer_change_warning = apk_inspect.format_signer_change_warning
format_blitzverify_block = apk_inspect.format_blitzverify_block
handle_apk_inspection_card = apk_inspect.handle_apk_inspection_card

extract_video_metadata = upload.extract_video_metadata
build_file_caption = upload.build_file_caption
resilient_send_media = upload.resilient_send_media
process_single_local_file_upload = upload.process_single_local_file_upload
run_approved_pending_upload = upload.run_approved_pending_upload

unrestrict_terabox = resolvers.unrestrict_terabox
unrestrict_1fichier = resolvers.unrestrict_1fichier
unrestrict_mega = resolvers.unrestrict_mega
unrestrict_direct_link = resolvers.unrestrict_direct_link
is_hls_or_video_stream = resolvers.is_hls_or_video_stream
get_ok_direct_mp4 = resolvers.get_ok_direct_mp4

process_torrent_download = downloads.process_torrent_download
process_zip_bundle = downloads.process_zip_bundle
is_speed_throttled_url = downloads.is_speed_throttled_url
download_multi_stream_turbo = downloads.download_multi_stream_turbo
download_video_or_m3u8 = downloads.download_video_or_m3u8
process_download_and_upload = downloads.process_download_and_upload
cleanup_temp_dir = downloads.cleanup_temp_dir

format_fwdcache_note = fwdcache.format_fwdcache_note
is_message_not_found_error = fwdcache.is_message_not_found_error
handle_url_intake = fwdcache.handle_url_intake
run_fresh_download = fwdcache.run_fresh_download

start_handler = commands.start_handler
god_panel_handler = commands.god_panel_handler
probe_command_handler = commands.probe_command_handler
settings_command_handler = commands.settings_command_handler
help_command_handler = commands.help_command_handler
stats_command_handler = commands.stats_command_handler
history_command_handler = commands.history_command_handler
broadcast_command_handler = commands.broadcast_command_handler
set_prefix_handler = commands.set_prefix_handler
clear_prefix_handler = commands.clear_prefix_handler
set_suffix_handler = commands.set_suffix_handler
clear_suffix_handler = commands.clear_suffix_handler
replace_command_handler = commands.replace_command_handler
list_replacements_handler = commands.list_replacements_handler
clear_replacements_handler = commands.clear_replacements_handler
brand_command_handler = commands.brand_command_handler
clear_brand_handler = commands.clear_brand_handler

callback_handler = callbacks.callback_handler

handle_document_torrent = intake.handle_document_torrent
handle_all_messages = intake.handle_all_messages
handle_queued_task = intake.handle_queued_task
queue_worker = intake.queue_worker

_DYNAMIC_CFG_ATTRS = frozenset({"DATA_DIR", "DB_FILE", "PENDING_DIR", "DOWNLOAD_DIR", "DISK_MIN_FREE_GB"})


def __getattr__(name: str):
    if name in _DYNAMIC_CFG_ATTRS:
        return getattr(cfg, name)
    if name == "DASHBOARD_SECRET":
        return db.DASHBOARD_SECRET
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# ==========================================
# 5. إعداد عميل Pyrogram الفائق (16 Workers & Multi-DC Parallel Transfers)
# ==========================================
bot = Client(
    "downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=cfg.DATA_DIR,
    workers=16
)

user_bot = None
if USER_SESSION_STRING:
    user_bot = Client(
        "premium_user_uploader",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING,
        workdir=cfg.DATA_DIR,
        workers=16
    )

clients.register_clients(bot, user_bot)
get_uploader_client = clients.get_uploader_client

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
            cleanup_expired_pending_downloads()
            downloads.cleanup_temp_dir(max_age_hours=6.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error in background_cleaner_worker: {e}")

# ==========================================
# 13. نقطة البداية وتشغيل البوت (Main Entry Point)
# ==========================================
async def main():
    if not API_ID or not API_HASH or not BOT_TOKEN:
        logger.error("❌ API_ID, API_HASH, or BOT_TOKEN missing!")
        sys.exit(1)

    downloads.cleanup_temp_dir(max_age_hours=6.0)
    cleanup_expired_pending_downloads()
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

if __name__ == "__main__":
    try:
        bot.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
