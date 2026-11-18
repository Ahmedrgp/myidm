import html
import logging

import myidm  # noqa: F401
from myidm import keyboards
from myidm import utils

logger = logging.getLogger("bot.dupguard")

make_duplicate_keyboard = keyboards.make_duplicate_keyboard


def format_duplicate_warning_card(info: dict, prev: dict, lang: str = "ar") -> str:
    lines = []
    if lang == "ar":
        lines.append("⚠️ <b>تنبيه: تم تنزيل هذا التطبيق مسبقاً بنفس الإصدار!</b>")
    else:
        lines.append("⚠️ <b>Warning: Duplicate APK Download Detected!</b>")

    pkg = info.get("package") or "Unknown"
    vname = info.get("version_name") or ""
    vcode = info.get("version_code")
    vdisp = f"{vname} ({vcode})" if (vname and vcode is not None) else (str(vname or vcode or "Unknown"))
    size = info.get("size_bytes") or 0

    if lang == "ar":
        lines.append(f"📦 الباكدج: <code>{html.escape(pkg)}</code>")
        lines.append(f"🔢 الإصدار: <code>{html.escape(vdisp)}</code>")
        lines.append(f"📊 الحجم: <code>{utils.humanbytes(size)} ({size} B)</code>")
        lines.append("")
        lines.append("📜 <b>بيانات التنزيل السابق المسجل:</b>")
        if prev.get("checked_at"):
            lines.append(f"🕒 تاريخ التنزيل: <code>{utils.format_cairo_time(prev['checked_at'])}</code>")
        if prev.get("file_sha256"):
            lines.append(f"🔑 بصمة الملف: <code>{prev['file_sha256'][:12]}...</code>")
    else:
        lines.append(f"📦 Package: <code>{html.escape(pkg)}</code>")
        lines.append(f"🔢 Version: <code>{html.escape(vdisp)}</code>")
        lines.append(f"📊 Size: <code>{utils.humanbytes(size)} ({size} B)</code>")
        lines.append("")
        lines.append("📜 <b>Previous Recorded Download:</b>")
        if prev.get("checked_at"):
            lines.append(f"🕒 Date: <code>{utils.format_cairo_time(prev['checked_at'])}</code>")
        if prev.get("file_sha256"):
            lines.append(f"🔑 File SHA-256: <code>{prev['file_sha256'][:12]}...</code>")

    curr_cert = info.get("cert_sha256")
    prev_cert = prev.get("cert_sha256")
    if curr_cert and prev_cert:
        if curr_cert == prev_cert:
            lines.append("✍️ التوقيع: ✅ نفس شهادة التوقيع الأصلية" if lang == "ar" else "✍️ Signer: ✅ Same original signing certificate")
        else:
            lines.append("✍️ التوقيع: ⚠️ شهادة توقيع مختلفة تماماً!" if lang == "ar" else "✍️ Signer: ⚠️ DIFFERENT signing certificate!")

    lines.append("")
    if lang == "ar":
        lines.append("💡 <b>هل ترغب في تنزيله ورفعه إلى تليجرام مجدداً؟</b>")
    else:
        lines.append("💡 <b>Do you want to download and upload it to Telegram again?</b>")
    return "\n".join(lines)
