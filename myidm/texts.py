# ==========================================
# 2. قاموس اللغات المزدوج الشامل (Arabic & English Dictionary)
# ==========================================
TEXTS = {
    "ar": {
        "welcome": (
            "<b>مرحباً {name}</b>\n\n"
            "<b>طريقة الاستخدام:</b>\n"
            "• أرسل رابط تحميل مباشر (HTTP / HTTPS)\n"
            "• أرسل رابط تورينت (Magnet Link)\n"
            "• أرسل ملف تورينت (.torrent)"
        ),
        "god_panel": (
            "<b>لوحة التحكم</b>\n"
            "<b>خيوط التحميل:</b> <code>{threads}x</code>\n"
            "<b>دعم التورينت:</b> <code>مفعل (Magnet و Torrent)</code>\n"
            "<b>اللغة:</b> <code>العربية</code>\n"
            "📄 <b>إجمالي الملفات:</b> <code>{files}</code>\n"
            "📊 <b>إجمالي البيانات:</b> <code>{bytes}</code>"
        ),
        "probe_info": (
            "🔎 <b>فحص الروابط</b>\n"
            "لمعاينة تفاصيل الملف مسبقاً:\n\n"
            "<code>/probe الرابط المباشر</code>"
        ),
        "settings_title": "⚙️ <b>الإعدادات والتفضيلات:</b>",
        "btn_panel": "لوحة التحكم",
        "btn_history": "📜 سجل التحميلات",
        "btn_settings": "⚙️ إعدادات التسريع واللغة",
        "btn_probe": "🔎 فحص الروابط Probe",
        "btn_stats": "📊 إحصائيات المحرك",
        "btn_back": "🔙 العودة للقائمة الرئيسية",
        "btn_cancel": "🛑 إلغاء العملية فوراً",
        "btn_lang": "🌐 اللغة: 🇸🇦 العربية",
        "btn_mode_auto": "🎬 وضع الرفع: تلقائي",
        "btn_mode_doc": "📄 وضع الرفع: مستند دائم",
        "btn_threads": "خيوط التحميل: {threads}x",
        "btn_caption_on": "📝 الوصف: مفعل ✅",
        "btn_caption_off": "📝 الوصف: معطل ❌",
        "btn_thumbs_on": "🖼️ المعاينة والمصغرات: مفعلة ✅",
        "btn_thumbs_off": "🖼️ المعاينة والمصغرات: معطلة ❌",
        "btn_cleantags_on": "🧹 تنظيف الإعلانات: مفعل ✅",
        "btn_cleantags_off": "🧹 تنظيف الإعلانات: معطل ❌",
        "transfer_rate": "معدل النقل:",
        "processed_size": "📦 الحجم المعالج:",
        "eta": "⏱️ الوقت المتبقي:",
        "downloading": "جاري التنزيل...",
        "uploading": "جاري الرفع المباشر إلى تليجرام...",
        "torrent_connecting": "جاري الاتصال بالتورينت وجلب البيانات...",
        "success_title": "✅ تمت العملية بنجاح",
        "file_name": "📄 اسم الملف:",
        "category": "التصنيف:",
        "final_size": "📊 الحجم النهائي:",
        "total_time": "⏱️ الوقت الإجمالي:",
        "avg_speed": "متوسط السرعة:",
        "dup_warning_title": "⚠️ <b>تنبيه: تم تنزيل هذا التطبيق مسبقاً بنفس الإصدار!</b>",
        "dup_prev_header": "📜 <b>بيانات التنزيل السابق المسجل:</b>",
        "dup_prev_date": "🕒 تاريخ التنزيل السابق:",
        "dup_prev_hash": "🔑 بصمة الملف السابقة:",
        "dup_signer_match": "✍️ التوقيع: ✅ نفس شهادة التوقيع الأصلية",
        "dup_signer_diff": "✍️ التوقيع: ⚠️ شهادة توقيع مختلفة تماماً!",
        "dup_prompt": "💡 <b>هل ترغب في تنزيله ورفعه إلى تليجرام مجدداً؟</b>",
        "btn_dup_download": "✅ نزّله تاني",
        "btn_dup_cancel": "🛑 إلغاء",
        "dup_cancelled_notice": "🛑 <b>تم إلغاء تنزيل التطبيق المكرر وحذفه بنجاح.</b>",
        "dup_approved_notice": "⏳ <b>جاري رفع الملف المعتمد إلى تليجرام...</b>",
        "dup_expired_alert": "⚠️ هذه العملية منتهية الصلاحية (Expired).",
        "dup_already_done_alert": "✅ تم رفع هذا الملف مسبقاً.",
        "dup_already_cancelled_alert": "🛑 تم إلغاء هذه العملية مسبقاً.",
        "dup_file_missing_alert": "❌ الملف غير موجود في مسار الانتظار.",
        "disk_low_error": (
            "❌ <b>مساحة القرص غير كافية لإتمام العملية!</b>\n\n"
            "📊 <b>المطلوب:</b> <code>{needed}</code>\n"
            "💾 <b>المتاح حالياً:</b> <code>{free}</code>\n"
            "🛡️ <b>الحد الأدنى للاحتياطي:</b> <code>{reserve}</code>\n\n"
            "💡 <i>يرجى تحرير بعض المساحة على الخادم والمحاولة مجدداً.</i>"
        ),
        "help_text": (
            "<b>دليل الاستخدام</b>\n"
            "1. <b>الروابط المباشرة:</b> أرسل رابط الملف المباشر هنا\n"
            "2. <b>روابط التورينت (Magnet):</b> أرسل رابط <code>magnet:?xt=...</code>\n"
            "3. <b>ملفات التورينت:</b> أرسل ملف <code>.torrent</code> مباشرة\n"
            "4. <b>حزمة ZIP:</b> أرسل <code>[ZIP]</code> في السطر الأول ثم الروابط لدمجها في ملف ZIP واحد\n\n"
            "<b>تسمية ووصف مخصص:</b>\n"
            "• <code>الرابط | اسم مخصص | وصف مخصص</code>"
        )
    },
    "en": {
        "welcome": (
            "<b>Welcome {name}</b>\n\n"
            "<b>How to use:</b>\n"
            "• Send a direct download link (HTTP / HTTPS)\n"
            "• Send a Magnet link (magnet:?xt=...)\n"
            "• Send a .torrent file"
        ),
        "god_panel": (
            "<b>Control Panel</b>\n"
            "<b>Download threads:</b> <code>{threads}x</code>\n"
            "<b>Torrent support:</b> <code>Active (Magnet & Torrent)</code>\n"
            "<b>Language:</b> <code>English</code>\n"
            "📄 <b>Total files:</b> <code>{files}</code>\n"
            "📊 <b>Total data:</b> <code>{bytes}</code>"
        ),
        "probe_info": (
            "🔎 <b>Link Probe</b>\n"
            "Inspect file details before downloading:\n\n"
            "<code>/probe Direct_URL</code>"
        ),
        "settings_title": "⚙️ <b>Settings & Preferences:</b>",
        "btn_panel": "Control Panel",
        "btn_history": "📜 Download History",
        "btn_settings": "⚙️ Settings & Language",
        "btn_probe": "🔎 Probe Inspector",
        "btn_stats": "📊 Engine Stats",
        "btn_back": "🔙 Back to Main Menu",
        "btn_cancel": "🛑 Cancel Task Immediately",
        "btn_lang": "🌐 Language: 🇺🇸 English",
        "btn_mode_auto": "🎬 Upload Mode: Auto Media",
        "btn_mode_doc": "📄 Upload Mode: Document",
        "btn_threads": "Threads: {threads}x",
        "btn_caption_on": "📝 Caption: Enabled ✅",
        "btn_caption_off": "📝 Caption: Disabled ❌",
        "btn_thumbs_on": "🖼️ Thumbnails: Enabled ✅",
        "btn_thumbs_off": "🖼️ Thumbnails: Disabled ❌",
        "btn_cleantags_on": "🧹 Clean Ads & Tags: Enabled ✅",
        "btn_cleantags_off": "🧹 Clean Ads & Tags: Disabled ❌",
        "transfer_rate": "Transfer Speed:",
        "processed_size": "📦 Processed Data:",
        "eta": "⏱️ Time Remaining:",
        "downloading": "Downloading...",
        "uploading": "Uploading directly to Telegram...",
        "torrent_connecting": "Connecting to peers and fetching metadata...",
        "success_title": "✅ Download complete",
        "file_name": "📄 File Name:",
        "category": "Category:",
        "final_size": "📊 Final Size:",
        "total_time": "⏱️ Total Duration:",
        "avg_speed": "Average Speed:",
        "dup_warning_title": "⚠️ <b>Warning: Duplicate APK Download Detected!</b>",
        "dup_prev_header": "📜 <b>Previous Recorded Download:</b>",
        "dup_prev_date": "🕒 Previous Date:",
        "dup_prev_hash": "🔑 Previous File SHA-256:",
        "dup_signer_match": "✍️ Signer: ✅ Same original signing certificate",
        "dup_signer_diff": "✍️ Signer: ⚠️ DIFFERENT signing certificate!",
        "dup_prompt": "💡 <b>Do you want to download and upload it to Telegram again?</b>",
        "btn_dup_download": "✅ Download anyway",
        "btn_dup_cancel": "🛑 Cancel",
        "dup_cancelled_notice": "🛑 <b>Duplicate download cancelled and temporary file removed.</b>",
        "dup_approved_notice": "⏳ <b>Uploading approved file to Telegram...</b>",
        "dup_expired_alert": "⚠️ This pending task has expired.",
        "dup_already_done_alert": "✅ This file has already been uploaded.",
        "dup_already_cancelled_alert": "🛑 This task was already cancelled.",
        "dup_file_missing_alert": "❌ File not found in pending directory.",
        "disk_low_error": (
            "❌ <b>Insufficient disk space to proceed!</b>\n\n"
            "📊 <b>Required:</b> <code>{needed}</code>\n"
            "💾 <b>Available:</b> <code>{free}</code>\n"
            "🛡️ <b>Minimum Reserve:</b> <code>{reserve}</code>\n\n"
            "💡 <i>Please free up disk space on the server and try again.</i>"
        ),
        "help_text": (
            "<b>User Guide</b>\n"
            "1. <b>Direct Links:</b> Send any direct HTTP/HTTPS URL\n"
            "2. <b>Torrent Magnets:</b> Send <code>magnet:?xt=...</code>\n"
            "3. <b>Torrent Files:</b> Send any <code>.torrent</code> file directly\n"
            "4. <b>ZIP Bundle:</b> Send <code>[ZIP]</code> as the first line, then list URLs to combine into a ZIP\n\n"
            "<b>Custom Naming & Captions:</b>\n"
            "• <code>URL | Custom_Name.ext | Custom_Caption</code>"
        )
    }
}

def tr(lang: str, key: str, **kwargs) -> str:
    lang_dict = TEXTS.get(lang, TEXTS["ar"])
    template = lang_dict.get(key, TEXTS["ar"].get(key, ""))
    return template.format(**kwargs) if kwargs else template
