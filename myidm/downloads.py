import asyncio
import gc
import json
import logging
import math
import os
import re
import shutil
import sys
import time
import urllib.parse
import zipfile

import aiohttp
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import Message

import myidm  # noqa: F401
from myidm import apk_inspect
from myidm import clients
from myidm import config as cfg
from myidm import db
from myidm import dupguard
from myidm import keyboards
from myidm import resolvers
from myidm import state
from myidm import texts
from myidm import upload
from myidm import utils
from myidm import validation

logger = logging.getLogger("bot.downloads")
_self = sys.modules[__name__]


# ==========================================
# 12. معالجة وتنزيل ملفات التورينت (Torrent & Magnet Downloader Engine)
# ==========================================
async def process_torrent_download(torrent_src: str, status_msg: Message, user_msg: Message):
    user_id = user_msg.from_user.id if user_msg.from_user else 0
    st = db.db_get_user_settings(user_id)
    lang = st["lang"]

    if not cfg.TORRENTP_AVAILABLE:
        await keyboards.safe_edit_text(status_msg, "❌ <b>Torrent engine module missing (torrentp)!</b>", parse_mode=ParseMode.HTML)
        return

    task_id = f"task_{int(time.time() * 1000)}"
    state.ACTIVE_TASKS[task_id] = {"cancelled": False}
    start_time = time.time()
    
    await keyboards.safe_edit_text(
        status_msg,
        f"🧲 <b>{texts.tr(lang, 'torrent_connecting')}</b>",
        reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang),
        parse_mode=ParseMode.HTML
    )

    try:
        ok_disk, _, free_d, reserve_d = utils.check_disk_space(cfg.DOWNLOAD_DIR, None)
        if not ok_disk:
            logger.error(f"Torrent disk check failed: free={free_d}, reserve={reserve_d}")
            needed_mb = "غير محدد" if lang == "ar" else "Unknown"
            free_mb = f"{free_d / (1024*1024):.1f} MB"
            reserve_mb = f"{reserve_d / (1024*1024):.1f} MB"
            err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
            await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
            return

        downloader = cfg.TorrentDownloader(torrent_src, save_path=cfg.DOWNLOAD_DIR)
        dl_task = asyncio.create_task(downloader.start_download())
        
        while not dl_task.done():
            if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                downloader.stop_download()
                dl_task.cancel()
                await keyboards.safe_edit_text(status_msg, "🛑 <b>Torrent task cancelled!</b>", parse_mode=ParseMode.HTML)
                return
            await asyncio.sleep(2.0)

        await dl_task
        
        downloaded_items = []
        for root, dirs, files in os.walk(cfg.DOWNLOAD_DIR):
            for file in files:
                fpath = os.path.join(root, file)
                if os.path.getmtime(fpath) >= start_time and not file.endswith(".torrent"):
                    downloaded_items.append(fpath)

        if not downloaded_items:
            await keyboards.safe_edit_text(status_msg, "❌ <b>No downloaded files found from Torrent!</b>", parse_mode=ParseMode.HTML)
            return

        for fpath in downloaded_items:
            fname = os.path.basename(fpath)
            fsize = os.path.getsize(fpath)
            await upload.process_single_local_file_upload(fpath, fname, fsize, status_msg, user_msg, user_id, start_time, task_id, url_key=torrent_src)

    except Exception as e:
        await keyboards.safe_edit_text(status_msg, f"❌ <b>Torrent Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        state.ACTIVE_TASKS.pop(task_id, None)
        gc.collect()

async def process_zip_bundle(valid_requests: list, status_msg: Message, user_msg: Message):
    zip_filename = f"bundle_{int(time.time())}.zip"
    zip_filepath = os.path.join(cfg.DOWNLOAD_DIR, zip_filename)
    downloaded_files = []
    bundle_uid = user_msg.from_user.id if user_msg.from_user else 0
    st = db.db_get_user_settings(bundle_uid)
    lang = st["lang"]
    ok_disk, _, free_d, reserve_d = utils.check_disk_space(cfg.DOWNLOAD_DIR, None)
    if not ok_disk:
        logger.error(f"Zip bundle disk check failed: free={free_d}, reserve={reserve_d}")
        needed_mb = "غير محدد" if lang == "ar" else "Unknown"
        free_mb = f"{free_d / (1024*1024):.1f} MB"
        reserve_mb = f"{reserve_d / (1024*1024):.1f} MB"
        err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
        await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
        return
    
    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for idx, (raw_url, cname, _) in enumerate(valid_requests, 1):
                await keyboards.safe_edit_text(status_msg, f"📦 <b>Downloading file {idx}/{len(valid_requests)} for ZIP bundle...</b>", parse_mode=ParseMode.HTML)
                direct_url = await resolvers.unrestrict_direct_link(raw_url)
                parsed_url = urllib.parse.urlparse(direct_url)
                referer_header = "https://an1.com/" if ("an1.net" in direct_url or "an1.com" in direct_url) else f"{parsed_url.scheme}://{parsed_url.netloc}/"
                
                if cfg.CURL_CFFI_AVAILABLE:
                    headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header}
                    async with cfg.CurlAsyncSession(impersonate="chrome124", allow_redirects=True) as session:
                        resp = await session.get(direct_url, headers=headers, stream=True)
                        raw_fn = cname or utils.smart_extract_filename(direct_url, resp.headers)
                        fname = utils.clean_and_rename_filename(raw_fn, user_id=bundle_uid)
                        base_fn, ext_fn = os.path.splitext(fname)
                        counter = 1
                        temp_fpath = os.path.join(cfg.DOWNLOAD_DIR, fname)
                        while temp_fpath in downloaded_files or os.path.exists(temp_fpath):
                            fname = f"{base_fn}_{counter}{ext_fn}"
                            temp_fpath = os.path.join(cfg.DOWNLOAD_DIR, fname)
                            counter += 1
                        with open(temp_fpath, "wb") as f:
                            async for chunk in resp.aiter_content(1024 * 1024):
                                if chunk: f.write(chunk)
                        zip_file.write(temp_fpath, arcname=fname)
                        downloaded_files.append(temp_fpath)
                else:
                    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
                    headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header}
                    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                        async with session.get(direct_url, headers=headers, allow_redirects=True) as resp:
                            if resp.status == 200:
                                raw_fn = cname or utils.smart_extract_filename(direct_url, resp.headers)
                                fname = utils.clean_and_rename_filename(raw_fn, user_id=bundle_uid)
                                base_fn, ext_fn = os.path.splitext(fname)
                                counter = 1
                                temp_fpath = os.path.join(cfg.DOWNLOAD_DIR, fname)
                                while temp_fpath in downloaded_files or os.path.exists(temp_fpath):
                                    fname = f"{base_fn}_{counter}{ext_fn}"
                                    temp_fpath = os.path.join(cfg.DOWNLOAD_DIR, fname)
                                    counter += 1
                                with open(temp_fpath, "wb") as f:
                                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                                        if chunk: f.write(chunk)
                                zip_file.write(temp_fpath, arcname=fname)
                                downloaded_files.append(temp_fpath)
        
        zip_size = os.path.getsize(zip_filepath)
        await keyboards.safe_edit_text(status_msg, "📤 <b>ZIP Bundle created! Uploading to Telegram...</b>", parse_mode=ParseMode.HTML)
        
        await user_msg.reply_document(
            document=zip_filepath,
            caption=f"📦 <b>ZIP Bundle ({len(downloaded_files)} files)</b>\n📊 <b>Size:</b> <code>{utils.humanbytes(zip_size)}</code>",
            parse_mode=ParseMode.HTML
        )
        await status_msg.delete()
    except Exception as e:
        await keyboards.safe_edit_text(status_msg, f"❌ <b>ZIP bundle failed:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        for fpath in downloaded_files:
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        if os.path.exists(zip_filepath):
            try: os.remove(zip_filepath)
            except Exception: pass
        gc.collect()

def is_speed_throttled_url(url: str) -> bool:
    """فحص ما إذا كان الرابط يخضع لسقف سرعة محدد من السيرفر (أقل من 1 ميجابايت)"""
    url_lower = url.lower()
    throttled_params = ["max=", "speed=", "limit=", "rate=", "throttle=", "capped="]
    if any(param in url_lower for param in throttled_params):
        return True
    
    throttled_domains = [
        "upfiles.download", "upfiles.com", "uploadhaven.com",
        "rapidgator.net", "1fichier.com", "filerio.in", "dropgalaxy.in",
        "katfile.com", "turbobit.net", "nitroflare.com", "pixeldrain.com",
        "downet.net", "akwam"
    ]
    parsed_netloc = urllib.parse.urlparse(url).netloc.lower()
    if any(domain in parsed_netloc for domain in throttled_domains):
        return True
        
    return False

async def download_multi_stream_turbo(
    direct_url: str,
    file_path: str,
    total_size: int,
    headers: dict,
    status_msg: Message,
    task_id: str,
    lang: str,
    dl_start_time: float,
    last_update: list,
    num_connections: int = 64
) -> bool:
    """محرك تنزيل ديناميكي فائق مع تسريع نهاية التحميل (Dynamic Micro-Blocks & End-Game Hedging) لمنع أي تباطؤ عند 99%"""
    if total_size <= 0:
        return False

    # كتل متوازنة ديناميكياً (512KB - 2MB) لضمان أقصى سرعة نقل وتفادي التباطؤ
    if total_size > 1024 * 1024 * 1024:
        concurrency = min(num_connections, 64)
        block_size = 2 * 1024 * 1024
    elif total_size > 200 * 1024 * 1024:
        concurrency = min(num_connections, 48)
        block_size = 1024 * 1024
    else:
        concurrency = min(num_connections, 32)
        block_size = 512 * 1024

    blocks = []
    current_byte = 0
    b_id = 0
    while current_byte < total_size:
        end_byte = min(current_byte + block_size - 1, total_size - 1)
        blocks.append((b_id, current_byte, end_byte))
        b_id += 1
        current_byte = end_byte + 1

    total_blocks_count = len(blocks)
    block_queue = asyncio.Queue()
    for b in blocks:
        block_queue.put_nowait(b)

    status_tracker = {"downloaded": 0}
    completed_blocks = set()
    in_flight = {}
    lock = asyncio.Lock()

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.seek(total_size - 1)
            f.write(b"\0")
    except Exception as e:
        logger.warning(f"Pre-allocate failed: {e}")
        return False

    try:
        file_handle = open(file_path, "r+b")
    except Exception as e:
        logger.warning(f"Failed to open file handle: {e}")
        return False

    async def fetch_block(b_id: int, start_byte: int, end_byte: int, session: aiohttp.ClientSession):
        if b_id in completed_blocks or state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            return False
        
        req_headers = {**headers, "Range": f"bytes={start_byte}-{end_byte}"}
        expected_len = end_byte - start_byte + 1
        
        try:
            b_timeout = aiohttp.ClientTimeout(total=15, sock_connect=5, sock_read=10)
            async with session.get(direct_url, headers=req_headers, timeout=b_timeout, allow_redirects=True, ssl=False) as resp:
                if resp.status == 206:
                    block_data = await resp.read()
                    if len(block_data) == expected_len and b_id not in completed_blocks:
                        async with lock:
                            if b_id not in completed_blocks:
                                file_handle.seek(start_byte)
                                file_handle.write(block_data)
                                completed_blocks.add(b_id)
                                in_flight.pop(b_id, None)
                                status_tracker["downloaded"] += len(block_data)
                                
                        await keyboards.progress_bar(
                            status_tracker["downloaded"],
                            total_size,
                            (f"تنزيل ({concurrency}x)" if lang == "ar" else f"Downloading ({concurrency}x)"),
                            status_msg,
                            dl_start_time,
                            last_update,
                            icon="⬇️",
                            task_id=task_id,
                            lang=lang
                        )
                        return True
                elif resp.status == 429:
                    await asyncio.sleep(0.5)
        except Exception:
            pass
        return False

    async def worker_loop(worker_id: int, session: aiohttp.ClientSession):
        while len(completed_blocks) < total_blocks_count:
            if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                return False

            b_id = -1
            start_byte = 0
            end_byte = 0

            try:
                b_id, start_byte, end_byte = block_queue.get_nowait()
            except asyncio.QueueEmpty:
                candidate = None
                now = time.time()
                for pending_id, (p_start, p_end, p_time) in list(in_flight.items()):
                    if pending_id not in completed_blocks:
                        if candidate is None or p_time < candidate[3]:
                            candidate = (pending_id, p_start, p_end, p_time)

                if candidate:
                    b_id, start_byte, end_byte, _ = candidate
                else:
                    await asyncio.sleep(0.05)
                    continue

            if b_id in completed_blocks:
                continue

            in_flight[b_id] = (start_byte, end_byte, time.time())
            success = await fetch_block(b_id, start_byte, end_byte, session)

            if not success and b_id not in completed_blocks:
                await block_queue.put((b_id, start_byte, end_byte))
                await asyncio.sleep(0.1)

        return True

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=20)
    connector = aiohttp.TCPConnector(limit=concurrency + 20, limit_per_host=concurrency + 10, keepalive_timeout=30, ssl=False)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            workers = [asyncio.create_task(worker_loop(i, session)) for i in range(concurrency)]
            
            while len(completed_blocks) < total_blocks_count:
                if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    for w in workers:
                        w.cancel()
                    return False
                await asyncio.sleep(0.1)

            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
    finally:
        try:
            file_handle.flush()
            file_handle.close()
        except Exception:
            pass

    if os.path.exists(file_path) and os.path.getsize(file_path) == total_size:
        logger.info(f"✅ Turbo with End-Game Hedging finished {file_path} ({utils.humanbytes(total_size)}) instantly to 100%!")
        return True

    return False

async def download_video_or_m3u8(
    video_url: str,
    output_dir: str,
    custom_name: str,
    referer_header: str,
    status_msg: Message,
    task_id: str,
    lang: str,
    dl_start_time: float,
    last_update: list,
    num_connections: int = 64
) -> tuple:
    """تحميل روابط البث m3u8 ومشغلات الفيديو المضمنة وتحويلها إلى MP4 1080p عالية الجودة بأقصى سرعة"""
    loop = asyncio.get_running_loop()

    # تطبيع رابط ok.ru لاستخدام videoembed وتجنب بطء صفحة الويب
    m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/)(\d+)', video_url)
    if m_ok:
        video_url = f"https://ok.ru/videoembed/{m_ok.group(1)}"

    # 1. تفعيل محرك التيربو الخارق فائق السرعة لمقاطع OK.ru لتفادي بطء DASH
    if "ok.ru" in video_url or "odnoklassniki.ru" in video_url:
        try:
            logger.info("🚀 OK.ru detected! Resolving high-speed progressive MP4...")
            direct_mp4_url, ok_title, total_file_size = await resolvers.get_ok_direct_mp4(video_url)
            if direct_mp4_url and total_file_size > 0:
                if custom_name:
                    v_title = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
                else:
                    v_title = ok_title or f"video_{int(time.time())}"
                v_title = re.sub(r'[\\/*?:"<>|]', '', v_title).strip()
                target_mp4 = os.path.join(output_dir, f"{v_title}.mp4")
                
                dl_headers = {
                    "User-Agent": cfg.STEALTH_HEADERS["User-Agent"],
                    "Referer": "https://ok.ru/"
                }
                
                logger.info(f"⚡ Launching Multi-Stream Turbo ({num_connections}x) for OK.ru ({utils.humanbytes(total_file_size)})...")
                try:
                    await status_msg.edit_text(
                        f"🎬 <b>{'تنزيل فيديو' if lang == 'ar' else 'Video stream'} ({num_connections}x)</b>\n"
                        f"📄 <b>{'العنوان' if lang == 'ar' else 'Title'}:</b> <code>{v_title}</code>\n"
                        f"📊 <b>{'الحجم' if lang == 'ar' else 'Size'}:</b> <code>{utils.humanbytes(total_file_size)}</code>",
                        reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang),
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

                turbo_success = await _self.download_multi_stream_turbo(
                    direct_url=direct_mp4_url,
                    file_path=target_mp4,
                    total_size=total_file_size,
                    headers=dl_headers,
                    status_msg=status_msg,
                    task_id=task_id,
                    lang=lang,
                    dl_start_time=dl_start_time,
                    last_update=last_update,
                    num_connections=num_connections
                )
                if turbo_success and os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 100 * 1024:
                    logger.info(f"✅ OK.ru downloaded at maximum speed via Multi-Stream Turbo: {target_mp4}")
                    return True, target_mp4, os.path.basename(target_mp4)
        except Exception as ok_err:
            logger.warning(f"Direct OK.ru Turbo extraction notice: {ok_err}")

    # 2. محرك yt-dlp المتوازي للبثوث المباشرة وباقي المشغلات (HLS, DASH, m3u8)
    if not cfg.YTDLP_AVAILABLE:
        logger.warning("yt-dlp is not installed!")
        return False, None, None

    if custom_name:
        out_template = os.path.join(output_dir, f"{custom_name}.%(ext)s")
    else:
        out_template = os.path.join(output_dir, "%(title).100s.%(ext)s")

    parsed_netloc = urllib.parse.urlparse(video_url).netloc
    parts = parsed_netloc.split(".")
    base_domain = ".".join(parts[-2:]) if len(parts) >= 2 else parsed_netloc
    origin_header = f"{urllib.parse.urlparse(video_url).scheme}://{parsed_netloc}"

    candidate_referers = [
        referer_header if referer_header else origin_header,
        f"https://{base_domain}/",
        None
    ]

    for current_ref in candidate_referers:
        if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            return False, None, None

        status_tracker = {"downloaded": 0, "total": 0}

        def ytdl_progress_hook(d):
            if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                raise Exception("Download cancelled by user")
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                status_tracker["downloaded"] = downloaded
                status_tracker["total"] = total
                asyncio.run_coroutine_threadsafe(
                    keyboards.progress_bar(
                        downloaded, total, texts.tr(lang, "downloading"),
                        status_msg, dl_start_time, last_update,
                        icon="🎬", task_id=task_id, lang=lang
                    ),
                    loop
                )

        headers = {
            'User-Agent': cfg.STEALTH_HEADERS['User-Agent'],
            'Origin': origin_header
        }
        if current_ref:
            headers['Referer'] = current_ref

        ydl_opts = {
            'outtmpl': out_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'http_headers': headers,
            'progress_hooks': [ytdl_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'retries': 5,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'concurrent_fragment_downloads': min(num_connections, 32),
            'buffersize': 1024 * 1024,
            'socket_timeout': 25,
            'geo_bypass': True,
        }

        def run_ydl():
            with cfg.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                base_name, _ = os.path.splitext(filename)
                mp4_name = f"{base_name}.mp4"
                if os.path.exists(mp4_name):
                    return mp4_name, info.get("title", "Video")
                if os.path.exists(filename):
                    return filename, info.get("title", "Video")
                return None, None

        try:
            final_path, title = await loop.run_in_executor(None, run_ydl)
            if final_path and os.path.exists(final_path):
                return True, final_path, os.path.basename(final_path)
        except Exception as e:
            logger.warning(f"yt-dlp try with ref [{current_ref}] failed: {e}")
            await asyncio.sleep(0.5)

    return False, None, None

async def process_download_and_upload(
    raw_url: str,
    custom_name: str,
    custom_caption: str,
    status_msg: Message,
    user_msg: Message,
    hop_count: int = 0,
    original_raw_url: str | None = None,
    forced_user_id: int | None = None
):
    if hop_count >= 2:
        await keyboards.safe_edit_text(status_msg, "❌ <b>Maximum download redirect limit reached!</b>", parse_mode=ParseMode.HTML)
        return

    file_path = None
    thumb_path = None
    start_time = time.time()
    task_id = f"task_{int(time.time() * 1000)}"
    state.ACTIVE_TASKS[task_id] = {"cancelled": False, "ssl_unverified": False}
    user_id = forced_user_id if forced_user_id is not None else (user_msg.from_user.id if (user_msg.from_user and not getattr(user_msg.from_user, "is_bot", False)) else (user_msg.chat.id if user_msg.chat else 0))
    settings = db.db_get_user_settings(user_id)
    lang = settings["lang"]
    user_threads = settings.get("god_threads", 64)
    url_key = (original_raw_url or raw_url or "").strip()
    
    try:
        direct_url = await resolvers.unrestrict_direct_link(raw_url)
        parsed_url = urllib.parse.urlparse(direct_url)
        
        custom_cookie = ""
        referer_header = ""
        doc_extracted_title = ""
        if "#" in direct_url:
            base_part, fragment_part = direct_url.split("#", 1)
            direct_url = base_part
            parsed_url = urllib.parse.urlparse(direct_url)
            params = urllib.parse.parse_qs(fragment_part)
            if "ref" in params:
                referer_header = params["ref"][0]
            if "cookie" in params and params["cookie"][0]:
                custom_cookie = f"PHPSESSID={params['cookie'][0]}"
            if "title" in params and params["title"][0]:
                doc_extracted_title = urllib.parse.unquote(params["title"][0]).strip()
                if not custom_name and doc_extracted_title:
                    custom_name = doc_extracted_title

        if not referer_header:
            if "an1.net" in direct_url or "an1.com" in direct_url:
                referer_header = "https://an1.com/"
            elif "documentaryarea.com" in direct_url:
                referer_header = "https://www.documentaryarea.com/"
            elif "devuploads.com" in direct_url:
                referer_header = "https://devuploads.com/"
            else:
                referer_header = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        status_tracker = {"downloaded": 0}
        dl_start_time = time.time()
        last_update = [0]
        download_success = False
        ssl_unverified_used = False

        ok_init, _, free_init, reserve_init = utils.check_disk_space(cfg.DOWNLOAD_DIR, None)
        if not ok_init:
            logger.error(f"Initial disk check failed: free={free_init}, reserve={reserve_init}")
            needed_mb = "غير محدد" if lang == "ar" else "Unknown"
            free_mb = f"{free_init / (1024*1024):.1f} MB"
            reserve_mb = f"{reserve_init / (1024*1024):.1f} MB"
            err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
            await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
            return

        # =========================================================================
        # 1. فحص وتنزيل روابط البث ومشغلات الفيديو المضمنة (m3u8 & Web Video Streams)
        # =========================================================================
        if resolvers.is_hls_or_video_stream(direct_url) or resolvers.is_hls_or_video_stream(raw_url):
            target_stream_url = direct_url if resolvers.is_hls_or_video_stream(direct_url) else raw_url
            logger.info(f"🎬 HLS / Video Stream detected: {target_stream_url}")
            await keyboards.safe_edit_text(
                status_msg,
                f"🎬 <b>{'جاري معالجة البث وتحويله إلى MP4...' if lang == 'ar' else 'Processing video stream to MP4...'}</b>",
                parse_mode=ParseMode.HTML
            )
            v_ok, v_path, v_name = await _self.download_video_or_m3u8(
                video_url=target_stream_url,
                output_dir=cfg.DOWNLOAD_DIR,
                custom_name=custom_name,
                referer_header=referer_header,
                status_msg=status_msg,
                task_id=task_id,
                lang=lang,
                dl_start_time=dl_start_time,
                last_update=last_update,
                num_connections=user_threads
            )
            if v_ok and v_path and os.path.exists(v_path):
                file_path = v_path
                filename = utils.clean_and_rename_filename(v_name, user_id=user_id)
                if task_id in state.ACTIVE_TASKS:
                    state.ACTIVE_TASKS[task_id]["filename"] = filename
                icon, category_desc, is_video_type = utils.get_god_category(filename)
                is_video_type = True
                download_success = True
            else:
                await keyboards.safe_edit_text(
                    status_msg,
                    "❌ <b>Stream Extraction Failed:</b>\n"
                    "<code>Server returned 403 Forbidden or Stream Expired.</code>\n\n"
                    "💡 <i>Try sending the movie page URL directly or another player server!</i>",
                    parse_mode=ParseMode.HTML
                )
                return

        # =========================================================================
        # 2. تشغيل محرك التنزيل المتوازي الفائق (Multi-Stream Turbo) للروابط المقيدة فقط (<1MB/s)
        # =========================================================================
        if not download_success and _self.is_speed_throttled_url(direct_url):
            try:
                headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header, "Range": "bytes=0-1024"}
                if custom_cookie:
                    headers["Cookie"] = custom_cookie
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as init_session:
                    async with init_session.get(direct_url, headers=headers, allow_redirects=True) as head_resp:
                        if head_resp.status in (200, 206):
                            content_len = head_resp.headers.get("Content-Length")
                            total_size_probe = 0
                            cr = head_resp.headers.get("Content-Range", "")
                            if "/" in cr:
                                total_size_probe = int(cr.split("/")[1])
                            elif content_len and content_len.isdigit():
                                total_size_probe = int(content_len)
                            
                            extracted_filename = utils.smart_extract_filename(direct_url, head_resp.headers)
                            _, ext = os.path.splitext(extracted_filename)
                            raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                            filename = utils.clean_and_rename_filename(raw_target_name, user_id=user_id)
                            if task_id in state.ACTIVE_TASKS:
                                state.ACTIVE_TASKS[task_id]["filename"] = filename
                            icon, category_desc, is_video_type = utils.get_god_category(filename)
                            file_path = os.path.join(cfg.DOWNLOAD_DIR, filename)

                            logger.info(f"⚡ Launching Multi-Stream Turbo Downloader ({user_threads}x) for throttled link: {direct_url} (Size: {utils.humanbytes(total_size_probe)})...")
                            info_card = (
                                f"⬇️ <b>{'تنزيل' if lang == 'ar' else 'Downloading'} ({user_threads}x)</b>\n"
                                f"📄 <b>{'الملف' if lang == 'ar' else 'File'}:</b> <code>{filename}</code>\n"
                                f"{icon} <b>{'النوع' if lang == 'ar' else 'Category'}:</b> {category_desc}\n"
                                f"📊 <b>{'الحجم' if lang == 'ar' else 'Size'}:</b> <code>{utils.humanbytes(total_size_probe)}</code>"
                            )
                            await keyboards.safe_edit_text(status_msg, info_card, reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                            turbo_ok = await _self.download_multi_stream_turbo(
                                direct_url=direct_url,
                                file_path=file_path,
                                total_size=total_size_probe,
                                headers=headers,
                                status_msg=status_msg,
                                task_id=task_id,
                                lang=lang,
                                dl_start_time=dl_start_time,
                                last_update=last_update,
                                num_connections=user_threads
                            )
                            if turbo_ok:
                                download_success = True
            except Exception as turbo_err:
                if validation.is_cert_verification_error(turbo_err) and not ssl_unverified_used:
                    host_name = parsed_url.netloc or parsed_url.hostname or direct_url
                    logger.warning(
                        f"TLS certificate verification failed for host {host_name} ({turbo_err}). "
                        f"Retrying once with TLS verification disabled."
                    )
                    ssl_unverified_used = True
                    if task_id in state.ACTIVE_TASKS:
                        state.ACTIVE_TASKS[task_id]["ssl_unverified"] = True
                    try:
                        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as init_session:
                            async with init_session.get(direct_url, headers=headers, allow_redirects=True, ssl=False) as head_resp:
                                if head_resp.status in (200, 206):
                                    content_len = head_resp.headers.get("Content-Length")
                                    total_size_probe = 0
                                    cr = head_resp.headers.get("Content-Range", "")
                                    if "/" in cr:
                                        total_size_probe = int(cr.split("/")[1])
                                    elif content_len and content_len.isdigit():
                                        total_size_probe = int(content_len)
                                    
                                    extracted_filename = utils.smart_extract_filename(direct_url, head_resp.headers)
                                    _, ext = os.path.splitext(extracted_filename)
                                    raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                                    filename = utils.clean_and_rename_filename(raw_target_name, user_id=user_id)
                                    if task_id in state.ACTIVE_TASKS:
                                        state.ACTIVE_TASKS[task_id]["filename"] = filename
                                    icon, category_desc, is_video_type = utils.get_god_category(filename)
                                    file_path = os.path.join(cfg.DOWNLOAD_DIR, filename)

                                    info_card = (
                                        f"⬇️ <b>{'تنزيل' if lang == 'ar' else 'Downloading'} ({user_threads}x)</b>\n"
                                        f"📄 <b>{'الملف' if lang == 'ar' else 'File'}:</b> <code>{filename}</code>\n"
                                        f"{icon} <b>{'النوع' if lang == 'ar' else 'Category'}:</b> {category_desc}\n"
                                        f"📊 <b>{'الحجم' if lang == 'ar' else 'Size'}:</b> <code>{utils.humanbytes(total_size_probe)}</code>"
                                    )
                                    await keyboards.safe_edit_text(status_msg, info_card, reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                                    turbo_ok = await _self.download_multi_stream_turbo(
                                        direct_url=direct_url,
                                        file_path=file_path,
                                        total_size=total_size_probe,
                                        headers=headers,
                                        status_msg=status_msg,
                                        task_id=task_id,
                                        lang=lang,
                                        dl_start_time=dl_start_time,
                                        last_update=last_update,
                                        num_connections=user_threads
                                    )
                                    if turbo_ok:
                                        download_success = True
                    except Exception as retry_turbo_err:
                        logger.warning(f"Unverified turbo download probe retry failed: {retry_turbo_err}")
                else:
                    logger.warning(f"Turbo download probe/fallback: {turbo_err}")

        profiles = [
            ("chrome124", referer_header),
            ("chrome120", "https://www.google.com/"),
            ("safari15_5", direct_url)
        ]

        if not download_success and cfg.CURL_CFFI_AVAILABLE:
            for target_prof, target_ref in profiles:
                if download_success or state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                    break

                max_stalled_retries = 5
                for retry_idx in range(max_stalled_retries):
                    if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                        break

                    headers = {**cfg.STEALTH_HEADERS, "Referer": target_ref}
                    if custom_cookie:
                        headers["Cookie"] = custom_cookie
                    if status_tracker["downloaded"] > 0:
                        headers["Range"] = f"bytes={status_tracker['downloaded']}-"

                    try:
                        async with cfg.CurlAsyncSession(impersonate=target_prof, allow_redirects=True) as session:
                            resp = await session.get(direct_url, headers=headers, stream=True)
                            
                            if resp.status_code not in (200, 206, 301, 302, 307, 308):
                                break

                            content_length = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                            total_size = int(content_length) if content_length and content_length.isdigit() else 0

                            if resp.status_code == 206 and total_size:
                                total_size += status_tracker["downloaded"]

                            extracted_filename = utils.smart_extract_filename(direct_url, resp.headers)
                            _, ext = os.path.splitext(extracted_filename)
                            
                            raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                            filename = utils.clean_and_rename_filename(raw_target_name, user_id=user_id)
                            if task_id in state.ACTIVE_TASKS:
                                state.ACTIVE_TASKS[task_id]["filename"] = filename
                            icon, category_desc, is_video_type = utils.get_god_category(filename)
                            file_path = os.path.join(cfg.DOWNLOAD_DIR, filename)

                            size_disp = utils.humanbytes(total_size) if total_size else "..."
                            info_card = (
                                f"⬇️ <b>{'بدء التنزيل' if lang == 'ar' else 'Starting download'}</b>\n"
                                f"📄 <b>{'الملف' if lang == 'ar' else 'File'}:</b> <code>{filename}</code>\n"
                                f"{icon} <b>{'النوع' if lang == 'ar' else 'Category'}:</b> {category_desc}\n"
                                f"📊 <b>{'الحجم' if lang == 'ar' else 'Size'}:</b> <code>{size_disp}</code>"
                            )
                            await keyboards.safe_edit_text(status_msg, info_card, reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                            mode = "a+b" if status_tracker["downloaded"] > 0 else "wb"
                            last_chunk_time = time.time()
                            stalled = False

                            if status_tracker["downloaded"] == 0:
                                ok_disk, needed_d, free_d, reserve_d = utils.check_disk_space(cfg.DOWNLOAD_DIR, total_size if total_size > 0 else None)
                                if not ok_disk:
                                    logger.error(f"Disk check failed before write: needed={needed_d}, free={free_d}, reserve={reserve_d}")
                                    needed_mb = f"{needed_d / (1024*1024):.1f} MB" if needed_d > 0 else ("غير محدد" if lang == "ar" else "Unknown")
                                    free_mb = f"{free_d / (1024*1024):.1f} MB"
                                    reserve_mb = f"{reserve_d / (1024*1024):.1f} MB"
                                    err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
                                    await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
                                    return

                            with open(file_path, mode) as f:
                                if status_tracker["downloaded"] > 0:
                                    f.seek(status_tracker["downloaded"])
                                
                                async for chunk in resp.aiter_content(512 * 1024):
                                    if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                                        await keyboards.safe_edit_text(status_msg, "🛑 <b>Download cancelled!</b>", parse_mode=ParseMode.HTML)
                                        return
                                    if chunk:
                                        f.write(chunk)
                                        status_tracker["downloaded"] += len(chunk)
                                        last_chunk_time = time.time()
                                        
                                        await keyboards.progress_bar(
                                            status_tracker["downloaded"],
                                            total_size,
                                            texts.tr(lang, "downloading"),
                                            status_msg,
                                            dl_start_time,
                                            last_update,
                                            icon="⬇️",
                                            task_id=task_id,
                                            lang=lang
                                        )
                                    
                                    if (time.time() - last_chunk_time) > 15.0:
                                        logger.warning(f"⚠️ Stream stalled for 15s. Auto-Resuming from byte {status_tracker['downloaded']}...")
                                        stalled = True
                                        break

                            if not stalled:
                                download_success = True
                                break

                    except Exception as ex:
                        if validation.is_cert_verification_error(ex) and not ssl_unverified_used:
                            host_name = parsed_url.netloc or parsed_url.hostname or direct_url
                            logger.warning(
                                f"TLS certificate verification failed for host {host_name} ({ex}). "
                                f"Retrying once with TLS verification disabled."
                            )
                            ssl_unverified_used = True
                            if task_id in state.ACTIVE_TASKS:
                                state.ACTIVE_TASKS[task_id]["ssl_unverified"] = True
                            if file_path and os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                except Exception:
                                    pass
                            status_tracker["downloaded"] = 0
                            try:
                                async with cfg.CurlAsyncSession(impersonate=target_prof, allow_redirects=True, verify=False) as unverified_session:
                                    resp = await unverified_session.get(direct_url, headers=headers, stream=True)
                                    if resp.status_code in (200, 206, 301, 302, 307, 308):
                                        content_length = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                                        total_size = int(content_length) if content_length and content_length.isdigit() else 0
                                        if resp.status_code == 206 and total_size:
                                            total_size += status_tracker["downloaded"]

                                        extracted_filename = utils.smart_extract_filename(direct_url, resp.headers)
                                        _, ext = os.path.splitext(extracted_filename)
                                        raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                                        filename = utils.clean_and_rename_filename(raw_target_name, user_id=user_id)
                                        if task_id in state.ACTIVE_TASKS:
                                            state.ACTIVE_TASKS[task_id]["filename"] = filename
                                        icon, category_desc, is_video_type = utils.get_god_category(filename)
                                        file_path = os.path.join(cfg.DOWNLOAD_DIR, filename)

                                        size_disp = utils.humanbytes(total_size) if total_size else "..."
                                        info_card = (
                                            f"⬇️ <b>{'بدء التنزيل' if lang == 'ar' else 'Starting download'}</b>\n"
                                            f"📄 <b>{'الملف' if lang == 'ar' else 'File'}:</b> <code>{filename}</code>\n"
                                            f"{icon} <b>{'النوع' if lang == 'ar' else 'Category'}:</b> {category_desc}\n"
                                            f"📊 <b>{'الحجم' if lang == 'ar' else 'Size'}:</b> <code>{size_disp}</code>"
                                        )
                                        await keyboards.safe_edit_text(status_msg, info_card, reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)

                                        mode = "a+b" if status_tracker["downloaded"] > 0 else "wb"
                                        last_chunk_time = time.time()
                                        stalled = False

                                        if status_tracker["downloaded"] == 0:
                                            ok_disk, needed_d, free_d, reserve_d = utils.check_disk_space(cfg.DOWNLOAD_DIR, total_size if total_size > 0 else None)
                                            if not ok_disk:
                                                logger.error(f"Disk check failed before write: needed={needed_d}, free={free_d}, reserve={reserve_d}")
                                                needed_mb = f"{needed_d / (1024*1024):.1f} MB" if needed_d > 0 else ("غير محدد" if lang == "ar" else "Unknown")
                                                free_mb = f"{free_d / (1024*1024):.1f} MB"
                                                reserve_mb = f"{reserve_d / (1024*1024):.1f} MB"
                                                err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
                                                await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
                                                return

                                        with open(file_path, mode) as f:
                                            if status_tracker["downloaded"] > 0:
                                                f.seek(status_tracker["downloaded"])
                                            
                                            async for chunk in resp.aiter_content(512 * 1024):
                                                if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                                                    await keyboards.safe_edit_text(status_msg, "🛑 <b>Download cancelled!</b>", parse_mode=ParseMode.HTML)
                                                    return
                                                if chunk:
                                                    f.write(chunk)
                                                    status_tracker["downloaded"] += len(chunk)
                                                    last_chunk_time = time.time()
                                                    
                                                    await keyboards.progress_bar(
                                                        status_tracker["downloaded"],
                                                        total_size,
                                                        texts.tr(lang, "downloading"),
                                                        status_msg,
                                                        dl_start_time,
                                                        last_update,
                                                        icon="⬇️",
                                                        task_id=task_id,
                                                        lang=lang
                                                    )
                                                
                                                if (time.time() - last_chunk_time) > 15.0:
                                                    logger.warning(f"⚠️ Stream stalled for 15s. Auto-Resuming from byte {status_tracker['downloaded']}...")
                                                    stalled = True
                                                    break

                                        if not stalled:
                                            download_success = True
                                            break
                            except Exception as unverified_curl_err:
                                logger.warning(f"Unverified curl_cffi retry failed: {unverified_curl_err}")
                            break
                        else:
                            logger.warning(f"Connection retry {retry_idx} error: {ex}")
                            await asyncio.sleep(1.0)

        if not download_success and not state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
            headers = {**cfg.STEALTH_HEADERS, "Referer": referer_header}
            if custom_cookie:
                headers["Cookie"] = custom_cookie

            async def _perform_aiohttp_download(ssl_disabled: bool = False):
                nonlocal file_path, filename, icon, category_desc, is_video_type, download_success
                connector = aiohttp.TCPConnector(ssl=False) if ssl_disabled else aiohttp.TCPConnector()
                req_ssl = False if ssl_disabled else None
                async with aiohttp.ClientSession(connector=connector, timeout=timeout, auto_decompress=False) as session:
                    async with session.get(direct_url, headers=headers, allow_redirects=True, ssl=req_ssl) as response:
                        if response.status not in (200, 206):
                            await keyboards.safe_edit_text(status_msg, f"❌ <b>URL Error: Server responded with status {response.status}</b>", parse_mode=ParseMode.HTML)
                            return
                        
                        content_length = response.headers.get("Content-Length")
                        total_size = int(content_length) if content_length and content_length.isdigit() else 0
                        
                        extracted_filename = utils.smart_extract_filename(direct_url, response.headers)
                        _, ext = os.path.splitext(extracted_filename)
                        raw_target_name = f"{custom_name}{ext}" if custom_name and ext and not custom_name.lower().endswith(ext.lower()) else (custom_name or extracted_filename)
                        filename = utils.clean_and_rename_filename(raw_target_name, user_id=user_id)
                        if task_id in state.ACTIVE_TASKS:
                            state.ACTIVE_TASKS[task_id]["filename"] = filename
                        icon, category_desc, is_video_type = utils.get_god_category(filename)
                        file_path = os.path.join(cfg.DOWNLOAD_DIR, filename)

                        ok_disk, needed_d, free_d, reserve_d = utils.check_disk_space(cfg.DOWNLOAD_DIR, total_size if total_size > 0 else None)
                        if not ok_disk:
                            logger.error(f"Disk check failed before write: needed={needed_d}, free={free_d}, reserve={reserve_d}")
                            needed_mb = f"{needed_d / (1024*1024):.1f} MB" if needed_d > 0 else ("غير محدد" if lang == "ar" else "Unknown")
                            free_mb = f"{free_d / (1024*1024):.1f} MB"
                            reserve_mb = f"{reserve_d / (1024*1024):.1f} MB"
                            err_msg = texts.tr(lang, "disk_low_error").format(needed=needed_mb, free=free_mb, reserve=reserve_mb)
                            await keyboards.safe_edit_text(status_msg, err_msg, parse_mode=ParseMode.HTML)
                            return

                        with open(file_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(512 * 1024):
                                if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                                    await keyboards.safe_edit_text(status_msg, "🛑 <b>Download cancelled!</b>", parse_mode=ParseMode.HTML)
                                    return

                                if chunk:
                                    f.write(chunk)
                                    status_tracker["downloaded"] += len(chunk)
                                    await keyboards.progress_bar(
                                        status_tracker["downloaded"],
                                        total_size,
                                        texts.tr(lang, "downloading"),
                                        status_msg,
                                        dl_start_time,
                                        last_update,
                                        icon="⬇️",
                                        task_id=task_id,
                                        lang=lang
                                    )
                        download_success = True

            try:
                await _perform_aiohttp_download(ssl_disabled=False)
            except Exception as e:
                if validation.is_cert_verification_error(e) and not ssl_unverified_used:
                    host_name = parsed_url.netloc or parsed_url.hostname or direct_url
                    logger.warning(
                        f"TLS certificate verification failed for host {host_name} ({e}). "
                        f"Retrying once with TLS verification disabled."
                    )
                    ssl_unverified_used = True
                    if task_id in state.ACTIVE_TASKS:
                        state.ACTIVE_TASKS[task_id]["ssl_unverified"] = True
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                    status_tracker["downloaded"] = 0
                    await _perform_aiohttp_download(ssl_disabled=True)
                else:
                    raise e
        
        actual_file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0

        if not file_path or not os.path.exists(file_path) or actual_file_size == 0:
            if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                return
            await keyboards.safe_edit_text(
                status_msg,
                "❌ <b>Download Failed:</b>\n"
                "<code>The server was unable to retrieve data from this host.</code>\n\n"
                "💡 <i>The link may be expired, IP-locked, or blocked by host firewall.</i>",
                parse_mode=ParseMode.HTML
            )
            return

        # =========================================================================
        # فحص التوقيع البنائي المزدوج مع دعم محرك System CURL الخارق
        # =========================================================================
        is_binary, html_sample = validation.is_valid_binary_file(file_path)
        if not is_binary and file_path and os.path.exists(file_path):
            os.remove(file_path)
            
            # محاولة استخدام المحرك الخارق (System CURL Engine) لتجاوز حماية الجدار الناري/Cloudflare
            logger.info(f"⚡ Invoking System CURL Engine for {direct_url}...")
            curl_cmd = [
                "curl", "-s", "-L",
                "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                direct_url, "-o", file_path
            ]
            if ssl_unverified_used:
                curl_cmd.append("-k")
            if referer_header:
                curl_cmd.extend(["-H", f"Referer: {referer_header}"])

            try:
                proc = await asyncio.create_subprocess_exec(*curl_cmd)
                await proc.communicate()
            except FileNotFoundError:
                logger.warning("System curl executable not found in PATH")
            except Exception as curl_err:
                logger.warning(f"CURL engine error: {curl_err}")

            is_binary, html_sample = validation.is_valid_binary_file(file_path)

        if not is_binary and file_path and os.path.exists(file_path):
            os.remove(file_path)
            real_url = validation.extract_real_download_link_from_html(html_sample, raw_url)
            
            if real_url and real_url.split('#')[0] != raw_url.split('#')[0]:
                logger.info(f"🔗 Real direct URL extracted from HTML: {real_url}")
                await _self.process_download_and_upload(real_url, custom_name, custom_caption, status_msg, user_msg, hop_count=hop_count+1, original_raw_url=url_key, forced_user_id=user_id)
                return
            else:
                page_title = ""
                m_t = re.search(r'<title>(.*?)</title>', html_sample, re.IGNORECASE | re.DOTALL)
                if m_t:
                    page_title = re.sub(r'\s+', ' ', m_t.group(1)).strip()[:100]
                err_detail = f"\n📄 <b>Page Title:</b> <code>{page_title}</code>" if page_title else ""
                await keyboards.safe_edit_text(
                    status_msg,
                    f"❌ <b>URL is an HTML webpage, not a direct file link!</b>{err_detail}\n\n"
                    f"💡 <i>Make sure the link is a valid direct link and not expired or IP-locked.</i>",
                    parse_mode=ParseMode.HTML
                )
                return

        actual_file_size = os.path.getsize(file_path)

        # Duplicate detection for APK-family files
        is_apk_family = (filename or "").lower().endswith((".apk", ".xapk", ".apks"))
        precomputed_apk_info = None
        if is_apk_family:
            loop = asyncio.get_running_loop()
            apk_info = await loop.run_in_executor(None, apk_inspect.inspect_apk, file_path)
            if apk_info:
                precomputed_apk_info = apk_info
                pkg = apk_info.get("package")
                vcode = apk_info.get("version_code")
                if pkg and vcode is not None:
                    dup_record = db.db_check_apk_duplicate(pkg, vcode)
                    if dup_record:
                        os.makedirs(cfg.PENDING_DIR, exist_ok=True)
                        dest_pending_name = f"pending_{int(time.time()*1000)}_{os.path.basename(file_path)}"
                        dest_pending_path = os.path.join(cfg.PENDING_DIR, dest_pending_name)
                        shutil.move(file_path, dest_pending_path)
                        pending_fpath = dest_pending_path
                        file_path = None

                        pending_id = db.db_add_pending_download(
                            user_id=user_id,
                            chat_id=user_msg.chat.id,
                            file_path=pending_fpath,
                            filename=filename,
                            custom_caption=custom_caption,
                            package=pkg,
                            version_name=str(apk_info.get("version_name") or ""),
                            version_code=vcode,
                            size=actual_file_size,
                            status="pending",
                            inspection_json=json.dumps(apk_info),
                            flow_type="direct",
                            url_key=url_key
                        )
                        warn_text = dupguard.format_duplicate_warning_card(apk_info, dup_record, lang=lang)
                        kb = keyboards.make_duplicate_keyboard(pending_id, lang=lang)
                        try:
                            await status_msg.delete()
                        except Exception:
                            pass
                        await user_msg.reply_text(warn_text, reply_markup=kb, parse_mode=ParseMode.HTML)
                        return
                else:
                    logger.info(f"APK inspection degraded (pkg={pkg}, vcode={vcode}), proceeding without duplicate block")

        BOT_LIMIT_BYTES = 1950 * 1024 * 1024      # 1.95 GB الحد الأقصى المطلق للبوت لتفادي خطأ 2000 MiB
        SPLIT_CHUNK_BYTES = 1900 * 1024 * 1024    # 1.90 GB

        CHANNEL_ID = utils.parse_chat_id(os.environ.get("CHANNEL_ID", ""))
        uploader = clients.get_uploader_client()
        is_premium_active = (clients.user_bot is not None) and getattr(clients.user_bot, "is_connected", False) and (uploader == clients.user_bot)

        # فحص إمكانية رفع الملف ككتلة واحدة (حتى 4GB) عبر حساب الـ Premium
        if actual_file_size > BOT_LIMIT_BYTES:
            if is_premium_active and actual_file_size <= (3950 * 1024 * 1024):
                # رفع الملف بالكامل كملف واحد ضخم عبر حساب الـ Premium
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

                caption, brand_markup = upload.build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)
                
                target_chat = CHANNEL_ID if CHANNEL_ID else "me"
                is_vid = is_video_type and settings["upload_mode"] != "doc"
                duration, width, height = 0, 0, 0
                if is_vid and settings.get("enable_thumbs", 1):
                    thumb_path, duration, width, height = await upload.extract_video_metadata(file_path)
                sent_msg = None
                try:
                    sent_msg = await upload.resilient_send_media(uploader, target_chat, file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)
                except Exception as prem_upload_err:
                    logger.warning(f"Direct premium upload target error, trying 'me': {prem_upload_err}")
                    sent_msg = await upload.resilient_send_media(uploader, "me", file_path, caption, is_vid, pyrogram_progress_prem, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)

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
                extra_ssl_line = f"\n{cfg.TLS_VERIFICATION_SKIPPED_NOTICE}" if ssl_unverified_used else ""
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
                    f"{extra_ssl_line}"
                )
                await user_msg.reply_text(success_card, parse_mode=ParseMode.HTML)
                await apk_inspect.handle_apk_inspection_card(file_path, filename, user_id, user_msg, lang, precomputed_info=precomputed_apk_info)
                return
            else:
                # إذا لم يكن البريميوم مفعلاً -> تقسيم الملف لتفادي الانهيار
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

                        # إرسال الجزء للمستخدم في الشات (يظهر دائماً وبشكل مؤكد)
                        part_msg = await user_msg.reply_document(
                            document=part_filepath,
                            caption=f"🧩 <b>Part {part_number}/{num_parts}</b>\n📄 <code>{part_filename}</code>",
                            parse_mode=ParseMode.HTML
                        )
                        if part_msg and hasattr(part_msg, "id") and isinstance(part_msg.id, int) and not isinstance(part_msg.id, bool):
                            deliv_part_ids.append(part_msg.id)

                        if os.path.exists(part_filepath): os.remove(part_filepath)
                        part_number += 1

                total_time_spent = round(time.time() - start_time)
                avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
                db.db_add_history(user_id, filename, actual_file_size, category_desc)
                if url_key and deliv_part_ids:
                    apk_pkg = precomputed_apk_info.get("package") if (is_apk_family and precomputed_apk_info) else None
                    apk_vc = precomputed_apk_info.get("version_code") if (is_apk_family and precomputed_apk_info) else None
                    db.db_record_delivery(user_id, url_key, filename, actual_file_size, user_msg.chat.id, deliv_part_ids, apk_pkg, apk_vc)
                await status_msg.delete()

                extra_ssl_line = f"\n{cfg.TLS_VERIFICATION_SKIPPED_NOTICE}" if ssl_unverified_used else ""
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
                return

        await keyboards.safe_edit_text(status_msg, f"📤 <b>{texts.tr(lang, 'uploading')}</b>", reply_markup=keyboards.make_cancel_keyboard(task_id, lang=lang), parse_mode=ParseMode.HTML)
        up_start_time = time.time()
        last_update = [0]
        
        async def pyrogram_progress(current, total):
            if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
                return
            await keyboards.progress_bar(
                current, total, texts.tr(lang, "uploading"), status_msg, up_start_time, last_update, icon="📤", task_id=task_id, lang=lang
            )

        caption, brand_markup = upload.build_file_caption(filename, actual_file_size, category_desc, icon, user_id, custom_caption)

        if state.ACTIVE_TASKS.get(task_id, {}).get("cancelled"):
            await keyboards.safe_edit_text(status_msg, "🛑 <b>Upload cancelled!</b>", parse_mode=ParseMode.HTML)
            return

        CHANNEL_ID = utils.parse_chat_id(os.environ.get("CHANNEL_ID", ""))
        force_video = False if settings["upload_mode"] == "doc" else is_video_type
        
        duration, width, height = 0, 0, 0
        if force_video and settings.get("enable_thumbs", 1):
            thumb_path, duration, width, height = await upload.extract_video_metadata(file_path)

        # 1. إرسال الملف فوراً ومباشرة للمستخدم عبر البوت
        sent_msg = await upload.resilient_send_media(clients.bot, user_msg.chat.id, file_path, caption, force_video, pyrogram_progress, thumb=thumb_path, duration=duration, width=width, height=height, reply_markup=brand_markup)

        # 2. النشر التلقائي في القناة (مثل @APKBlitz) إذا تم تحديد CHANNEL_ID في البيئة
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
            
        total_time_spent = round(time.time() - start_time)
        avg_speed = actual_file_size / total_time_spent if total_time_spent > 0 else 0
        
        db.db_add_history(user_id, filename, actual_file_size, category_desc)
        if url_key and sent_msg and hasattr(sent_msg, "id") and isinstance(sent_msg.id, int) and not isinstance(sent_msg.id, bool):
            apk_pkg = precomputed_apk_info.get("package") if (is_apk_family and precomputed_apk_info) else None
            apk_vc = precomputed_apk_info.get("version_code") if (is_apk_family and precomputed_apk_info) else None
            db.db_record_delivery(user_id, url_key, filename, actual_file_size, user_msg.chat.id, [sent_msg.id], apk_pkg, apk_vc)
        await status_msg.delete()
        
        extra_ssl_line = f"\n{cfg.TLS_VERIFICATION_SKIPPED_NOTICE}" if ssl_unverified_used else ""
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

    except aiohttp.ClientError as e:
        await keyboards.safe_edit_text(status_msg, f"❌ <b>Network Connection Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except asyncio.TimeoutError:
        await keyboards.safe_edit_text(status_msg, "❌ <b>Request Timeout.</b>", parse_mode=ParseMode.HTML)
    except OSError as e:
        await keyboards.safe_edit_text(status_msg, f"❌ <b>Disk/Storage Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except MessageNotModified:
        pass
    except RPCError as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            await keyboards.safe_edit_text(status_msg, f"❌ <b>Telegram Upload Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await keyboards.safe_edit_text(status_msg, f"❌ <b>Unexpected Error:</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
    finally:
        state.ACTIVE_TASKS.pop(task_id, None)
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        gc.collect()

def cleanup_temp_dir(max_age_hours: float | None = 6.0):
    """
    Cleans orphan downloads in DOWNLOAD_DIR.
    If max_age_hours is given, only files older than max_age_hours (default 6h) are deleted.
    Never touches PENDING_DIR.
    """
    try:
        if os.path.exists(cfg.DOWNLOAD_DIR):
            now = time.time()
            cutoff = (now - max_age_hours * 3600) if max_age_hours is not None else None
            for f in os.listdir(cfg.DOWNLOAD_DIR):
                fp = os.path.join(cfg.DOWNLOAD_DIR, f)
                if os.path.isfile(fp):
                    try:
                        if cutoff is None or os.path.getmtime(fp) < cutoff:
                            os.remove(fp)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Cleanup temp notice: {e}")
