import html
import logging
import os
import re
import ssl
import sys
import urllib.parse

import aiohttp

import myidm  # noqa: F401
from myidm import config as cfg

logger = logging.getLogger("bot.validation")
_self = sys.modules[__name__]


def is_valid_binary_file(filepath: str) -> tuple:
    if not filepath or not os.path.exists(filepath):
        return False, ""

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return False, ""

    try:
        with open(filepath, "rb") as f:
            header = f.read(8192)
    except Exception:
        return False, ""

    # إذا كان الملف يحتوي على بايتات فارغة (null bytes)، فهو حتماً ملف ثنائي وليس صفحة HTML
    if b"\x00" in header:
        return True, ""

    # تواقيع الملفات الثنائية المعروفة
    known_magic = (
        b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",  # ZIP, APK, JAR, DOCX, etc.
        b"\x1f\x8b",                                  # GZIP
        b"Rar!\x1a\x07",                              # RAR
        b"7z\xbc\xaf\x27\x1c",                        # 7Z
        b"%PDF",                                      # PDF
        b"\xff\xd8\xff",                              # JPEG
        b"\x89PNG\r\n\x1a\n",                         # PNG
        b"GIF87a", b"GIF89a",                         # GIF
        b"RIFF",                                      # WEBP, AVI, WAV
        b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2",# MP3
        b"OggS",                                      # OGG
        b"fLaC",                                      # FLAC
        b"\x1aE\xdf\xa3",                             # MKV, WEBM
        b"MZ",                                        # EXE, DLL
        b"\x7fELF",                                   # Linux ELF
    )
    if any(header.startswith(sig) for sig in known_magic):
        return True, ""

    # فحص صريح لنصوص HTML
    header_lower = header.lstrip().lower()
    html_signatures = (
        b"<!doctype html", b"<html", b"<?xml", b"<head", b"<script", b"<!--",
        b"<body", b"<div", b"<title"
    )
    if any(header_lower.startswith(sig) for sig in html_signatures) or (b"<html" in header_lower[:1024]):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f_full:
                return False, f_full.read(300 * 1024)
        except Exception:
            return False, header.decode("utf-8", errors="ignore")

    # إذا لم يكن يحتوي على وسوم HTML، فهو ملف صالح (مثل ملفات نصية، ترجمات srt، كود، إلخ)
    return True, ""


def extract_video_embed_from_html(html_text: str, original_url: str) -> tuple:
    """استخراج مشغلات وسيرفرات الفيديو المضمنة في صفحات المشاهدة (مثل AhwakTV، FaselHD، وغيرها)"""
    if not html_text:
        return None, None

    # استخراج عنوان الفيلم أو الحلقة بدقة
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if not title_match:
        title_match = re.search(r'<title>([^<]+)</title>', html_text, re.I)

    extracted_title = ""
    if title_match:
        raw_t = html.unescape(title_match.group(1)).strip()
        cleaned = re.split('[-|\u2013\u2014•»]', raw_t)[0].strip()
        cleaned = re.sub(r'[\\/*?:"<>|]', '', cleaned).strip()
        extracted_title = cleaned

    candidate_urls = []

    # 1. عناصر قوائم السيرفرات (WatchList / data-embed-url / data-url / data-src)
    embed_attrs = [
        r'<li[^>]*data-embed-url=["\']([^"\']+)["\']',
        r'data-embed-url=["\']([^"\']+)["\']',
        r'data-url=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+)["\']',
        r'data-embed=["\']([^"\']+)["\']'
    ]
    for pattern in embed_attrs:
        for match in re.findall(pattern, html_text, re.I):
            clean = html.unescape(match).strip()
            if clean.startswith("//"):
                clean = "https:" + clean
            if clean.startswith("http"):
                candidate_urls.append(clean)

    # 2. إطارات iframes المضمنة
    for ifr in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I):
        clean = html.unescape(ifr).strip()
        if clean.startswith("//"):
            clean = "https:" + clean
        if clean.startswith("http"):
            candidate_urls.append(clean)

    # 3. تدفقات الفيديو المباشرة ومصادر HTML5 video في كود الصفحة
    for v in re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mpd|mp4)[^\s"\'<>]*)', html_text, re.I):
        candidate_urls.append(v)

    # استبعاد روابط التواصل الاجتماعي والإعلانات
    ignore_domains = ["facebook.com", "twitter.com", "x.com", "google.com", "disqus.com", "analytics", "doubleclick", "mg.pamphiltre"]
    unique_candidates = []
    seen = set()
    for c in candidate_urls:
        if c not in seen and not any(ign in c.lower() for ign in ignore_domains):
            seen.add(c)
            unique_candidates.append(c)

    # ترتيب الأفضلية: تفضيل سيرفرات OK.ru ثم Dood و Streamwish وباقي السيرفرات
    priority_hosts = [
        "ok.ru", "odnoklassniki", "dood", "streamwish", "filelions", "vidtube",
        "streamtape", "mixdrop", "mp4upload", "vidspeed", "voe.sx", "uqload", "vk.com"
    ]

    sorted_candidates = sorted(
        unique_candidates,
        key=lambda u: next((i for i, h in enumerate(priority_hosts) if h in u.lower()), 999)
    )

    if sorted_candidates:
        best_candidate = sorted_candidates[0]
        m_ok = re.search(r'(?:ok\.ru/video/|ok\.ru/videoembed/)(\d+)', best_candidate)
        if m_ok:
            best_candidate = f"https://ok.ru/videoembed/{m_ok.group(1)}"
        return best_candidate, extracted_title

    return None, extracted_title


def extract_real_download_link_from_html(html_text: str, original_url: str) -> str:
    if not html_text:
        return ""

    # فحص روابط تأكيد التحميل لملفات Google Drive الكبيرة
    if "drive.google.com" in original_url or "drive.usercontent.google.com" in original_url:
        g_confirm = re.search(r'href=["\'](/uc\?export=download&[^"\']+)["\']', html_text)
        if g_confirm:
            return "https://drive.google.com" + html.unescape(g_confirm.group(1))
        g_confirm2 = re.search(r'href=["\'](https://drive\.usercontent\.google\.com/download\?[^"\']+)["\']', html_text)
        if g_confirm2:
            return html.unescape(g_confirm2.group(1))

    # فحص مشغلات الفيديو وسيرفرات الأفلام أولاً
    video_embed, video_title = _self.extract_video_embed_from_html(html_text, original_url)
    if video_embed:
        title_part = f"&title={urllib.parse.quote(video_title)}" if video_title else ""
        return f"{video_embed}#ref={urllib.parse.quote(original_url)}{title_part}"

    forbidden = ["an1store.apk", "store.apk", "googleplay", "telegram", "play.google.com", "ad.doubleclick"]
    all_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html_text)

    candidate_links = []
    for link in all_links:
        link_lower = link.lower()
        if any(f in link_lower for f in forbidden):
            continue

        if any(link_lower.endswith(ext) or f"{ext}?" in link_lower for ext in ('.apk', '.xapk', '.apks', '.zip', '.rar', '.7z')):
            candidate_links.append(link)
        elif any(kw in link_lower for kw in ("d.an1.com", "d.an1.net", "/downloads/", "/download/", "download_link", "file_download")):
            candidate_links.append(link)

    if candidate_links:
        parsed_orig = urllib.parse.urlparse(original_url)
        orig_name = os.path.basename(parsed_orig.path).replace(".html", "")
        if orig_name:
            orig_name_clean = re.sub(r'[^a-zA-Z0-9]', '', orig_name.split('-')[0]).lower()
            for cl in candidate_links:
                if orig_name_clean and orig_name_clean in cl.lower():
                    return cl
        return candidate_links[0]

    return ""


def is_cert_verification_error(exc: BaseException | None, seen: set | None = None) -> bool:
    """
    Returns True if exc is specifically a certificate verification failure
    (e.g. broken certificate chain, missing intermediate, self-signed, expired, untrusted root).
    Excludes non-certificate SSL errors (e.g. handshake failure, protocol mismatch, wrong version)
    and non-SSL network/OS errors.
    """
    if exc is None:
        return False
    if seen is None:
        seen = set()
    exc_id = id(exc)
    if exc_id in seen:
        return False
    seen.add(exc_id)

    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, aiohttp.ClientConnectorCertificateError):
        return True

    if cfg.CURL_CFFI_AVAILABLE:
        try:
            from curl_cffi.requests.exceptions import CertificateVerifyError
            if isinstance(exc, CertificateVerifyError):
                return True
        except (ImportError, AttributeError):
            pass
        try:
            from curl_cffi.curl import CurlError
            if isinstance(exc, CurlError) and getattr(exc, "code", None) == 60:
                return True
        except (ImportError, AttributeError):
            pass

    err_str = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in err_str or "SSLCertVerificationError" in err_str:
        return True

    cert_err = getattr(exc, "certificate_error", None)
    if cert_err is not None and _self.is_cert_verification_error(cert_err, seen):
        return True

    cause = getattr(exc, "__cause__", None)
    if cause is not None and _self.is_cert_verification_error(cause, seen):
        return True

    context = getattr(exc, "__context__", None)
    if context is not None and _self.is_cert_verification_error(context, seen):
        return True

    os_err = getattr(exc, "os_error", None)
    if os_err is not None and _self.is_cert_verification_error(os_err, seen):
        return True

    return False
