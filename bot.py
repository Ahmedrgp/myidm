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
# 4. خادم الويب للإنعاش (aiohttp Web Server)
# ==========================================
async def handle_health_check(request):
    return web.Response(text="⚡ OMNIPOTENT OVERLORD ENGINE - ABSOLUTE POWER 100%")

DASHBOARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ OMNIPOTENT OVERLORD | Live Monitor & Dashboard</title>
    <style>
        :root {
            --bg-base: #090d16;
            --bg-card: #111827;
            --border: #1f293d;
            --cyan: #00f0ff;
            --purple: #8b5cf6;
            --green: #10b981;
            --red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg-base); color: var(--text-main); min-height: 100vh; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
        .logo-box { display: flex; align-items: center; gap: 12px; }
        .logo-icon { font-size: 28px; filter: drop-shadow(0 0 10px rgba(0,240,255,0.6)); }
        .logo-title { font-size: 22px; font-weight: 800; background: linear-gradient(135deg, #00f0ff, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .status-badge { display: inline-flex; align-items: center; gap: 8px; background: rgba(16, 185, 129, 0.15); color: var(--green); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); }
        .status-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; margin-bottom: 24px; }
        .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 20px; position: relative; overflow: hidden; transition: transform 0.2s, border-color 0.2s; }
        .card:hover { transform: translateY(-2px); border-color: rgba(0,240,255,0.3); }
        .card-title { font-size: 13px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .card-value { font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 8px; }
        .card-sub { font-size: 12px; color: var(--text-muted); }
        .progress-bar-bg { width: 100%; height: 6px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; margin-top: 10px; }
        .progress-bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
        .fill-cyan { background: linear-gradient(90deg, #00f0ff, #3b82f6); }
        .fill-purple { background: linear-gradient(90deg, #8b5cf6, #ec4899); }
        .fill-green { background: linear-gradient(90deg, #10b981, #00f0ff); }
        .fill-orange { background: linear-gradient(90deg, #f59e0b, #ef4444); }
        .chart-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 22px; margin-bottom: 24px; }
        .chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .chart-legend { display: flex; gap: 16px; font-size: 13px; }
        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-color { width: 12px; height: 12px; border-radius: 3px; }
        canvas { width: 100%; height: 200px; display: block; border-radius: 8px; }
        .tasks-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 22px; }
        .table-wrap { overflow-x: auto; margin-top: 14px; }
        table { width: 100%; border-collapse: collapse; text-align: right; font-size: 14px; }
        th { padding: 12px 16px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--border); font-size: 13px; }
        td { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.04); vertical-align: middle; }
        .empty-tasks { text-align: center; padding: 36px 16px; color: var(--text-muted); font-size: 14px; }
        .btn-cancel-task { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
        .btn-cancel-task:hover { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="logo-box">
                <span class="logo-icon">⚡</span>
                <div>
                    <h1 class="logo-title">OMNIPOTENT OVERLORD ENGINE</h1>
                    <div style="font-size: 12px; color: var(--text-muted);">نظام المراقبة الحية والتحكم في الخادم والمهام</div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div class="status-badge"><span class="status-dot"></span> متصل ويعمل بنشاط</div>
                <div id="uptime_disp" style="font-size: 13px; color: var(--text-muted);">تشغيل: 0s</div>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="card-title"><span>استهلاك المعالج (CPU)</span><span>⚡</span></div>
                <div class="card-value" id="cpu_val">0.0%</div>
                <div class="card-sub" id="cpu_sub">معدل التحميل الحقيقي</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-cyan" id="cpu_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>الذاكرة العشوائية (RAM)</span><span>🧠</span></div>
                <div class="card-value" id="ram_val">0 MB</div>
                <div class="card-sub" id="ram_sub">المستخدم من الإجمالي</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-purple" id="ram_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>المساحة التخزينية (Disk)</span><span>💾</span></div>
                <div class="card-value" id="disk_val">0 GB</div>
                <div class="card-sub" id="disk_sub">المساحة المتوفرة</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-green" id="disk_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>المهام وطابور المعالجة</span><span>⏳</span></div>
                <div class="card-value" id="tasks_val">0 / 0</div>
                <div class="card-sub" id="tasks_sub">0 مهام نشطة | 0 في الانتظار</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill fill-orange" id="tasks_bar" style="width: 0%;"></div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>البيانات المعالجة التراكمية</span><span>📊</span></div>
                <div class="card-value" id="data_val">0 B</div>
                <div class="card-sub" id="files_sub">0 ملفات مكتملة بالكامل</div>
            </div>
            <div class="card">
                <div class="card-title"><span>المستخدمون المسجلون</span><span>👥</span></div>
                <div class="card-value" id="users_val">0</div>
                <div class="card-sub">قاعدة بيانات SQLite المحلية</div>
            </div>
        </div>

        <div class="chart-card">
            <div class="chart-header">
                <div style="font-size: 15px; font-weight: 700;">📈 مخطط الأداء الحي والضغط اللحظي (Live Telemetry)</div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-color" style="background: var(--cyan);"></div><span>المعالج (CPU %)</span></div>
                    <div class="legend-item"><div class="legend-color" style="background: var(--purple);"></div><span>الذاكرة (RAM %)</span></div>
                </div>
            </div>
            <canvas id="liveChart"></canvas>
        </div>

        <div class="tasks-card">
            <div style="font-size: 15px; font-weight: 700; margin-bottom: 6px;">🚀 المهام الجارية في الوقت الفعلي (Active Tasks)</div>
            <div style="font-size: 13px; color: var(--text-muted);">جميع عمليات التحميل والرفع المباشر والتورينت الجارية الآن:</div>
            <div class="table-wrap">
                <table id="tasksTable">
                    <thead>
                        <tr>
                            <th>معرف المهمة (Task ID)</th>
                            <th>الملف / المصدر</th>
                            <th>التقدم</th>
                            <th>السرعة</th>
                            <th>الحالة</th>
                            <th>إجراء</th>
                        </tr>
                    </thead>
                    <tbody id="tasksBody">
                        <tr><td colspan="6" class="empty-tasks">⚡ لا توجد أي مهام تحميل أو رفع جارية حالياً (السيرفر في وضع الاستعداد).</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const SECRET_KEY = "__SECRET_KEY__";
        const cpuHistory = new Array(30).fill(0);
        const ramHistory = new Array(30).fill(0);

        const canvas = document.getElementById('liveChart');
        const ctx = canvas.getContext('2d');

        function resizeCanvas() {
            canvas.width = canvas.parentElement.clientWidth - 44;
            canvas.height = 200;
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        function drawChart() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Grid lines
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.lineWidth = 1;
            for (let y = 0; y <= 100; y += 25) {
                const py = canvas.height - (y / 100) * canvas.height;
                ctx.beginPath();
                ctx.moveTo(0, py);
                ctx.lineTo(canvas.width, py);
                ctx.stroke();
            }

            function drawLine(data, color) {
                ctx.beginPath();
                const step = canvas.width / (data.length - 1);
                data.forEach((val, i) => {
                    const x = i * step;
                    const y = canvas.height - (val / 100) * canvas.height;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.strokeStyle = color;
                ctx.lineWidth = 2.5;
                ctx.stroke();
            }

            drawLine(cpuHistory, '#00f0ff');
            drawLine(ramHistory, '#a855f7');
        }

        async function fetchStats() {
            try {
                const res = await fetch(`/api/dashboard/stats?key=${SECRET_KEY}`);
                if (!res.ok) return;
                const d = await res.json();

                document.getElementById('cpu_val').innerText = d.cpu_percent + '%';
                document.getElementById('cpu_bar').style.width = Math.min(d.cpu_percent, 100) + '%';

                document.getElementById('ram_val').innerText = d.ram_used_mb + ' MB';
                document.getElementById('ram_sub').innerText = `${d.ram_used_mb} MB من ${d.ram_total_mb} MB (${d.ram_percent}%)`;
                document.getElementById('ram_bar').style.width = Math.min(d.ram_percent, 100) + '%';

                document.getElementById('disk_val').innerText = d.disk_free_gb + ' GB';
                document.getElementById('disk_sub').innerText = `${d.disk_used_gb} GB مستخدم من ${d.disk_total_gb} GB (${d.disk_percent}%)`;
                document.getElementById('disk_bar').style.width = Math.min(d.disk_percent, 100) + '%';

                document.getElementById('tasks_val').innerText = `${d.active_tasks_count} / ${d.queue_size}`;
                document.getElementById('tasks_sub').innerText = `${d.active_tasks_count} مهام نشطة | ${d.queue_size} في الانتظار`;
                document.getElementById('tasks_bar').style.width = Math.min((d.active_tasks_count + d.queue_size) * 20, 100) + '%';

                document.getElementById('data_val').innerText = d.total_bytes_human;
                document.getElementById('files_sub').innerText = `${d.total_files} ملفات مكتملة بالكامل`;
                document.getElementById('users_val').innerText = d.total_users;
                document.getElementById('uptime_disp').innerText = 'تشغيل: ' + d.uptime_formatted;

                cpuHistory.shift();
                cpuHistory.push(d.cpu_percent);
                ramHistory.shift();
                ramHistory.push(d.ram_percent);
                drawChart();

                const tbody = document.getElementById('tasksBody');
                if (!d.active_tasks || d.active_tasks.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="empty-tasks">⚡ لا توجد أي مهام تحميل أو رفع جارية حالياً (السيرفر في وضع الاستعداد).</td></tr>';
                } else {
                    let html = '';
                    d.active_tasks.forEach(t => {
                        html += `<tr>
                            <td><code>${t.task_id}</code></td>
                            <td><b>${t.filename}</b></td>
                            <td>
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <div style="flex:1; height:6px; background:rgba(255,255,255,0.1); border-radius:3px;">
                                        <div style="width:${t.progress}%; height:100%; background:var(--cyan); border-radius:3px;"></div>
                                    </div>
                                    <span>${t.progress}%</span>
                                </div>
                            </td>
                            <td><span style="color:var(--cyan); font-weight:600;">${t.speed}</span></td>
                            <td><span style="color:${t.cancelled ? 'var(--red)' : 'var(--green)'}; font-weight:600;">${t.cancelled ? 'ملغاة' : 'نشطة'}</span></td>
                            <td><button class="btn-cancel-task" onclick="cancelTask('${t.task_id}')">🛑 إلغاء</button></td>
                        </tr>`;
                    });
                    tbody.innerHTML = html;
                }
            } catch (err) {
                console.error("Dashboard poll error:", err);
            }
        }

        async function cancelTask(taskId) {
            if (!confirm(`هل أنت متأكد من إلغاء المهمة ${taskId}؟`)) return;
            try {
                await fetch(`/api/dashboard/cancel?key=${SECRET_KEY}&task_id=${taskId}`, { method: 'POST' });
                fetchStats();
            } catch(e) {}
        }

        setInterval(fetchStats, 2000);
        fetchStats();
    </script>
</body>
</html>
"""

async def handle_dashboard_view(request):
    key = request.query.get("key", "")
    if key != db.DASHBOARD_SECRET:
        return web.Response(
            text="""<!DOCTYPE html><html><head><meta charset="utf-8"><title>403 Access Denied</title>
            <style>body{background:#0a0e17;color:#ef4444;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
            .card{background:#111827;padding:30px;border-radius:12px;border:1px solid #ef4444;text-align:center;}
            h1{margin:0 0 10px;font-size:24px;}p{color:#9ca3af;font-size:14px;}</style></head>
            <body><div class="card"><h1>⛔ 403 Forbidden</h1><p>Invalid or missing dashboard security key.</p></div></body></html>""",
            status=403,
            content_type="text/html"
        )
    return web.Response(text=DASHBOARD_HTML_TEMPLATE.replace("__SECRET_KEY__", db.DASHBOARD_SECRET), content_type="text/html")

async def handle_dashboard_stats_api(request):
    key = request.query.get("key", "")
    if key != db.DASHBOARD_SECRET:
        return web.json_response({"error": "unauthorized"}, status=403)

    cpu = psutil.cpu_percent(interval=None) if PSUTIL_AVAILABLE else 0.0
    vmem = psutil.virtual_memory() if PSUTIL_AVAILABLE else None
    ram_used = round(vmem.used / (1024 * 1024)) if vmem else 0
    ram_total = round(vmem.total / (1024 * 1024)) if vmem else 0
    ram_percent = vmem.percent if vmem else 0.0

    disk = shutil.disk_usage(cfg.DOWNLOAD_DIR)
    disk_free_gb = round(disk.free / (1024**3), 1)
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round((disk.total - disk.free) / (1024**3), 1)
    disk_percent = round((disk.total - disk.free) / disk.total * 100, 1)
    reserve_bytes = int(cfg.DISK_MIN_FREE_GB * (1024 ** 3))
    disk_low = bool(disk.free < reserve_bytes * 2)

    uptime_sec = int(time.time() - START_TIME)
    g_stats = db_get_global_stats()
    total_users = db_get_total_users_count()

    tasks_data = []
    for tid, tinfo in list(state.ACTIVE_TASKS.items()):
        tasks_data.append({
            "task_id": tid,
            "cancelled": tinfo.get("cancelled", False),
            "filename": tinfo.get("filename", "Active Job"),
            "progress": tinfo.get("progress", 0),
            "speed": tinfo.get("speed", "0 B/s")
        })

    return web.json_response({
        "status": "online",
        "cpu_percent": cpu,
        "ram_used_mb": ram_used,
        "ram_total_mb": ram_total,
        "ram_percent": ram_percent,
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_percent": disk_percent,
        "disk_low": disk_low,
        "uptime_seconds": uptime_sec,
        "uptime_formatted": time_formatter(uptime_sec),
        "active_tasks_count": len(state.ACTIVE_TASKS),
        "queue_size": state.request_queue.qsize(),
        "total_users": total_users,
        "total_files": g_stats.get("files", 0),
        "total_bytes": g_stats.get("bytes", 0),
        "total_bytes_human": humanbytes(g_stats.get("bytes", 0)),
        "active_tasks": tasks_data
    })

async def handle_dashboard_cancel_task_api(request):
    key = request.query.get("key", "")
    if key != db.DASHBOARD_SECRET:
        return web.json_response({"error": "unauthorized"}, status=403)
    tid = request.query.get("task_id", "")
    if tid in state.ACTIVE_TASKS:
        state.ACTIVE_TASKS[tid]["cancelled"] = True
        return web.json_response({"success": True, "task_id": tid, "status": "cancelled"})
    return web.json_response({"success": False, "error": "not_found"})

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/dashboard", handle_dashboard_view)
    app.router.add_get("/api/dashboard/stats", handle_dashboard_stats_api)
    app.router.add_post("/api/dashboard/cancel", handle_dashboard_cancel_task_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 خادم الويب الشغّال (OMNIPOTENT ENGINE) يعمل على المنفذ: {PORT}")

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
    await start_web_server()
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
