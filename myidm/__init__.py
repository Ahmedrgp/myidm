import asyncio

# ==========================================
# 0. إصلاح مشكلة Python 3.12+ / 3.14 على Render
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import pyrogram.utils

# Fix 64-bit Telegram Channel IDs in Pyrogram (-100...)
pyrogram.utils.MIN_CHANNEL_ID = -10099999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000

_safe_ok_parse_json = None
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
    try:
        from yt_dlp.extractor import odnoklassniki
        _orig_ok_parse_json = odnoklassniki.OdnoklassnikiIE._parse_json
        def _safe_ok_parse_json(self, json_string, *args, **kwargs):
            if isinstance(json_string, (dict, list)):
                return json_string
            return _orig_ok_parse_json(self, json_string, *args, **kwargs)
        odnoklassniki.OdnoklassnikiIE._parse_json = _safe_ok_parse_json
    except Exception as _patch_err:
        pass
except ImportError:
    yt_dlp = None
    YTDLP_AVAILABLE = False
