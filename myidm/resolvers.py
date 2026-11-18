import html
import json
import logging
import re
import sys
import urllib.parse

import aiohttp

import myidm  # noqa: F401
from myidm import config as cfg
from myidm import validation

logger = logging.getLogger("bot.resolvers")
_self = sys.modules[__name__]


async def unrestrict_terabox(url: str) -> tuple:
    """فك تشفير واستخراج رابط التنزيل المباشر واسم الملف من TeraBox تلقائياً"""
    try:
        m = re.search(r'(?:surl=|/s/|/share/init\?surl=)([a-zA-Z0-9_-]+)', url)
        if not m:
            return url, None
        raw_id = m.group(1)
        clean_id = raw_id[1:] if raw_id.startswith("1") else raw_id
        
        api_endpoints = [
            f"https://terabox-downloader.online/api/get-info?shorturl={clean_id}",
            f"https://yt-api.org/api/terabox?url={urllib.parse.quote(url)}",
            f"https://terabox-api.online/api?url={urllib.parse.quote(url)}"
        ]
        
        headers = {**cfg.STEALTH_HEADERS, "Referer": "https://www.terabox.com/"}
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=8)) as session:
            for api in api_endpoints:
                try:
                    async with session.get(api, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                if "list" in data and len(data["list"]) > 0:
                                    item = data["list"][0]
                                    dlink = item.get("dlink") or item.get("download_link") or item.get("direct_link")
                                    fname = item.get("server_filename") or item.get("filename")
                                    if dlink:
                                        return dlink, fname
                                dlink = data.get("download_link") or data.get("dlink") or data.get("direct_link") or data.get("url")
                                fname = data.get("file_name") or data.get("filename")
                                if dlink and isinstance(dlink, str) and dlink.startswith("http"):
                                    return dlink, fname
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"terabox resolver error: {e}")
    return url, None

async def unrestrict_1fichier(url: str) -> str:
    """تجاوز صفحة الانتظار واستخراج رابط التحميل المباشر لـ 1Fichier"""
    try:
        clean_url = url.split('&')[0]
        headers = {
            **cfg.STEALTH_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": clean_url
        }
        data = {"did": "0"}
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(clean_url, headers=headers, data=data, allow_redirects=True) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="ignore")
                    m = re.search(r'href=["\'](https?://[a-zA-Z0-9-]+\.1fichier\.com/[^"\'>\s]+)["\']', text)
                    if m:
                        return m.group(1)
                    m_btn = re.search(r'<a[^>]+class=["\'][^"\']*btn-general[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', text)
                    if m_btn:
                        return m_btn.group(1)
    except Exception as e:
        logger.warning(f"1fichier resolver error: {e}")
    return url

async def unrestrict_mega(url: str) -> tuple:
    """فك روابط Mega.nz واستخراج الرابط المباشر السحابي"""
    try:
        api_url = f"https://megadl.hazex.workers.dev/?url={urllib.parse.quote(url)}"
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(api_url, headers=cfg.STEALTH_HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        dlink = data.get("url") or data.get("download_url")
                        fname = data.get("filename") or data.get("file_name")
                        if dlink:
                            return dlink, fname
    except Exception as e:
        logger.warning(f"mega resolver error: {e}")
    return url, None

# ==========================================
# 7. مستخرج ومفكك الروابط المطلق مع محاكاة الـ Referer المباشرة
# ==========================================
async def unrestrict_direct_link(url: str) -> str:
    # TeraBox & Affiliated Domains
    terabox_domains = ["terabox.com", "teraboxapp.com", "1024tera.com", "mirrobox.com", "nephobox.com", "freeterabox.com", "terasharelink.com", "terabox.link", "4funbox.com"]
    if any(d in url.lower() for d in terabox_domains):
        direct_tb, tb_name = await _self.unrestrict_terabox(url)
        if direct_tb and direct_tb != url:
            if tb_name:
                return f"{direct_tb}#title={urllib.parse.quote(tb_name)}"
            return direct_tb

    # 1Fichier & Mirrored Domains
    fichier_domains = ["1fichier.com", "alterupload.com", "cjoint.net", "desfichiers.com", "megadl.fr"]
    if any(d in url.lower() for d in fichier_domains):
        direct_1f = await _self.unrestrict_1fichier(url)
        if direct_1f and direct_1f != url:
            return direct_1f

    # Mega.nz / Mega.co.nz
    if "mega.nz" in url.lower() or "mega.co.nz" in url.lower():
        direct_mega, mega_name = await _self.unrestrict_mega(url)
        if direct_mega and direct_mega != url:
            if mega_name:
                return f"{direct_mega}#title={urllib.parse.quote(mega_name)}"
            return direct_mega

    # Mediafire
    if "mediafire.com" in url:
        try:
            if cfg.CURL_CFFI_AVAILABLE:
                async with cfg.CurlAsyncSession(impersonate="chrome124") as session:
                    resp = await session.get(url, headers=cfg.STEALTH_HEADERS, allow_redirects=True, stream=True)
                    if resp.status_code == 200:
                        content_bytes = bytearray()
                        async for chunk in resp.aiter_content(32 * 1024):
                            content_bytes.extend(chunk)
                            if len(content_bytes) >= 128 * 1024:
                                break
                        html_sample = content_bytes.decode("utf-8", errors="ignore")
                        match = re.search(r'href="(https?://download\d+\.mediafire\.com/[^"]+)"', html_sample)
                        if match:
                            return match.group(1)
        except Exception:
            pass

    # Pixeldrain
    if "pixeldrain.com/u/" in url:
        file_id = url.split("pixeldrain.com/u/")[1].split("?")[0].split("/")[0]
        return f"https://pixeldrain.com/api/file/{file_id}"

    # AN1 (an1.net / an1.com / files.an1.net) مع فرض Referer المباشر
    if "an1.net" in url or "an1.com" in url:
        target_ref = "https://an1.com/"
        custom_cookie = ""
        if "#" in url:
            _, frag = url.split("#", 1)
            p_dict = urllib.parse.parse_qs(frag)
            if "cookie" in p_dict and p_dict["cookie"][0]:
                custom_cookie = f"PHPSESSID={p_dict['cookie'][0]}"
        try:
            if cfg.CURL_CFFI_AVAILABLE:
                async with cfg.CurlAsyncSession(impersonate="chrome124") as session:
                    headers = {**cfg.STEALTH_HEADERS, "Referer": target_ref}
                    if custom_cookie:
                        headers["Cookie"] = custom_cookie
                    resp = await session.get(url, headers=headers, allow_redirects=True, stream=True)
                    if resp.status_code == 200:
                        content_length = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                        cl_bytes = int(content_length) if content_length and content_length.isdigit() else 0
                        if cl_bytes > 1 * 1024 * 1024:
                            return resp.url or url

                        content_bytes = bytearray()
                        async for chunk in resp.aiter_content(32 * 1024):
                            content_bytes.extend(chunk)
                            if len(content_bytes) >= 200 * 1024:
                                break
                        html_sample = content_bytes.decode("utf-8", errors="ignore")
                        
                        # البحث عن سيرفرات التنزيل لـ AN1 (d.an1.com)
                        an1_direct = re.findall(r'href=["\'](https?://d\d*\.an1\.(?:com|net)/[^"\']+)["\']', html_sample, re.IGNORECASE)
                        if an1_direct:
                            return an1_direct[0]
                        
                        extracted = validation.extract_real_download_link_from_html(html_sample, url)
                        if extracted:
                            return extracted
        except Exception:
            pass

    # GitHub Blob
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Dropbox
    if "dropbox.com" in url:
        url = url.replace("dl=0", "dl=1")
        if "dl=1" not in url:
            url += "&dl=1" if "?" in url else "?dl=1"
        return url

    # Google Drive
    gdrive_match = re.search(r'drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([^/&?]+)', url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # DocumentaryArea
    if "documentaryarea.com" in url:
        try:
            if cfg.CURL_CFFI_AVAILABLE:
                async with cfg.CurlAsyncSession(impersonate="chrome124") as session:
                    target_page = url
                    if "player.php" in url:
                        p_resp = await session.get(url, headers=cfg.STEALTH_HEADERS, timeout=15)
                        if p_resp.status_code == 200:
                            v_match = re.search(r'href=[\'"](/video/[^\'"]+)[\'"]', p_resp.text)
                            if v_match:
                                target_page = "https://www.documentaryarea.com" + v_match.group(1)
                    
                    if "video.php" not in target_page:
                        resp = await session.get(target_page, headers=cfg.STEALTH_HEADERS, timeout=15)
                        if resp.status_code == 200:
                            m = re.search(r'video\.php\?playback=([a-zA-Z0-9]+)', resp.text)
                            if m:
                                playback_hash = m.group(1)
                                cookies = session.cookies.get_dict()
                                phpsessid = cookies.get("PHPSESSID", "")
                                doc_title = "Documentary"
                                if "/video/" in target_page:
                                    doc_title = target_page.split("/video/")[1].strip("/").replace("+", " ").replace("-", " ")
                                direct_stream = f"https://www.documentaryarea.com/video.php?playback={playback_hash}"
                                return f"{direct_stream}#ref={urllib.parse.quote(target_page)}&cookie={phpsessid}&title={urllib.parse.quote(doc_title)}"
        except Exception as e:
            logger.warning(f"documentaryarea error: {e}")

    # OK.ru / Odnoklassniki / VK Video
    if "ok.ru" in url or "odnoklassniki.ru" in url:
        try:
            clean_url = url.strip()
            if "src=" in clean_url:
                src_match = re.search(r'src=["\']([^"\']+)["\']', clean_url)
                if src_match:
                    clean_url = src_match.group(1)
            if clean_url.startswith("//"):
                clean_url = "https:" + clean_url
            if not clean_url.startswith("http"):
                clean_url = "https://" + clean_url.lstrip("/")

            m_id = re.search(r'(?:video/|videoembed/|ok\.ru/)([0-9]{8,})', clean_url)
            if m_id:
                target_ok_url = f"https://ok.ru/videoembed/{m_id.group(1)}"
            else:
                target_ok_url = clean_url

            movie_title = ""
            if cfg.CURL_CFFI_AVAILABLE:
                try:
                    async with cfg.CurlAsyncSession(impersonate="chrome124") as session:
                        ok_resp = await session.get(target_ok_url, headers=cfg.STEALTH_HEADERS, timeout=10)
                        matches = re.findall(r'data-options="([^"]+)"', ok_resp.text)
                        if matches:
                            unescaped = matches[0].replace("&quot;", '"').replace("&amp;", "&")
                            ok_data = json.loads(unescaped)
                            meta_val = ok_data.get("flashvars", {}).get("metadata", {})
                            if isinstance(meta_val, str):
                                meta_val = json.loads(meta_val)
                            movie_title = meta_val.get("movie", {}).get("title", "")
                            movie_title = re.sub(r'[\\/*?:"<>|]', "", movie_title).strip()
                except Exception:
                    pass

            title_param = f"&title={urllib.parse.quote(movie_title)}" if movie_title else ""
            return f"{target_ok_url}#ref=https://ok.ru/{title_param}"
        except Exception as ok_err:
            logger.warning(f"ok.ru extraction error: {ok_err}")

    # Catbox
    if "catbox.moe" in url:
        return url

    # فاحص عام لصفحات الويب لاستخراج مشغلات الفيديو أو روابط التنزيل المباشرة
    try:
        if cfg.CURL_CFFI_AVAILABLE:
            async with cfg.CurlAsyncSession(impersonate="chrome124") as session:
                resp = await session.get(url, headers=cfg.STEALTH_HEADERS, allow_redirects=True, stream=True)
                content_bytes = bytearray()
                async for chunk in resp.aiter_content(32 * 1024):
                    content_bytes.extend(chunk)
                    if len(content_bytes) >= 300 * 1024:
                        break
                try:
                    html_sample = content_bytes.decode("utf-8")
                    if "\ufffd" in html_sample:
                        html_sample = content_bytes.decode("cp1256", errors="ignore")
                except Exception:
                    html_sample = content_bytes.decode("cp1256", errors="ignore")

                extracted = validation.extract_real_download_link_from_html(html_sample, url)
                if extracted:
                    return extracted
    except Exception:
        pass

    return url

def is_hls_or_video_stream(url: str) -> bool:
    """فحص ما إذا كان الرابط هو رابط بث مباشر m3u8 أو مشغل فيديو ويب"""
    url_lower = url.lower()
    if ".m3u8" in url_lower or ".mpd" in url_lower:
        return True
    
    video_hosts = [
        "hgcloud.to", "hglink.to", "dood.", "doodstream", "vidtube",
        "streamtape", "mixdrop", "mp4upload", "vidoza", "streamwish",
        "filelions", "dropload", "streamvid", "minochinos.com",
        "youtube.com", "youtu.be", "twitter.com", "x.com", "tiktok.com",
        "facebook.com", "fb.watch", "instagram.com", "ok.ru", "odnoklassniki.ru", "vk.com",
        "vidspeed", "voe.sx", "uqload", "yourupload", "ds2play", "okcdn.ru", "mycdn.me"
    ]
    parsed_netloc = urllib.parse.urlparse(url).netloc.lower()
    return any(host in parsed_netloc for host in video_hosts)

async def get_ok_direct_mp4(embed_or_video_url: str) -> tuple:
    """استخراج رابط MP4 المباشر عالي السرعة من سيرفرات OK.ru مع حساب حجم الملف بدقة دون استهلاك الباقة"""
    m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/|ok\.ru/)([0-9]{8,})', embed_or_video_url)
    clean_embed = f"https://ok.ru/videoembed/{m_ok.group(1)}" if m_ok else embed_or_video_url
    
    headers = {**cfg.STEALTH_HEADERS, "Referer": "https://ok.ru/"}
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=12)) as session:
        async with session.get(clean_embed, headers=headers) as resp:
            if resp.status != 200:
                return None, None, 0
            text = await resp.text(errors="ignore")
            m = re.search(r'data-options=(["\'])(.*?)\1', text)
            if not m:
                return None, None, 0
            try:
                raw_opts = json.loads(html.unescape(m.group(2)))
            except Exception:
                return None, None, 0
            meta = raw_opts.get("flashvars", {}).get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            
            movie_title = meta.get("movie", {}).get("title", "") if isinstance(meta, dict) else ""
            videos = meta.get("videos", []) if isinstance(meta, dict) else []
            
            # ترتيب الجودات من الأعلى إلى الأدنى لاختيار أفضل نسخة MP4 تدعم التيربو
            q_prio = ["ultra", "quad", "full", "hd", "sd", "low", "lowest", "mobile"]
            direct_url = None
            for q in q_prio:
                for v in videos:
                    if v.get("name") == q and v.get("url"):
                        direct_url = v.get("url")
                        break
                if direct_url:
                    break
            if not direct_url and videos:
                direct_url = videos[0].get("url")
                
            if not direct_url:
                return None, movie_title, 0
                
            # فحص حجم الملف الفعلي عبر طلب Range خفيف (1KB) دون استهلاك الباقة
            probe_headers = {
                "User-Agent": cfg.STEALTH_HEADERS["User-Agent"],
                "Referer": "https://ok.ru/",
                "Range": "bytes=0-1024"
            }
            try:
                async with session.get(direct_url, headers=probe_headers, ssl=False) as p_resp:
                    total_size = 0
                    cr = p_resp.headers.get("Content-Range", "")
                    if "/" in cr:
                        total_size = int(cr.split("/")[1])
                    elif "Content-Length" in p_resp.headers:
                        total_size = int(p_resp.headers["Content-Length"])
                    return direct_url, movie_title, total_size
            except Exception:
                return direct_url, movie_title, 0
