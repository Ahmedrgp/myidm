import os
import sys
import json
import sqlite3
import zipfile
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot import (
    inspect_apk,
    format_dn,
    compute_file_sha256,
)

def build_card(info: dict, prev: dict | None, lang: str = "ar") -> str:
    # Mirror structure specified in Prompt Section 3
    if not info:
        return ""
    
    # Cairo time
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Africa/Cairo")
    except Exception:
        import datetime
        tz = datetime.timezone(datetime.timedelta(hours=3))
    import datetime
    checked_at = info.get("checked_at")
    if checked_at:
        dt = datetime.datetime.fromtimestamp(checked_at, tz=tz)
        cairo_time_str = dt.strftime("%Y-%m-%d %H:%M Cairo")
    else:
        cairo_time_str = datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M Cairo")

    def humanbytes(b):
        if not b:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024.0:
                return f"{b:.2f} {unit}".replace(".00", "")
            b /= 1024.0
        return f"{b:.2f} PB"

    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🛡️ بطاقة فحص APK | APK Inspection")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Bundle line
    if info.get("is_bundle"):
        rule = info.get("bundle_rule_ar") if lang == "ar" else info.get("bundle_rule_en")
        if lang == "ar":
            lines.append(f"📦 الحزمة: تم فحص APK الأساسي ({rule})")
        else:
            lines.append(f"📦 Bundle: base APK inspected ({rule})")

    # Package
    package = info.get("package")
    if package:
        if lang == "ar":
            lines.append(f"📦 الباكدج: <code>{package}</code>")
        else:
            lines.append(f"📦 Package: <code>{package}</code>")

    # Version
    vname = info.get("version_name")
    vcode = info.get("version_code")
    if vname and vcode is not None:
        vdisp = f"{vname} ({vcode})"
    elif vname:
        vdisp = str(vname)
    elif vcode is not None:
        vdisp = str(vcode)
    else:
        vdisp = None

    if vdisp:
        if lang == "ar":
            lines.append(f"🔢 الإصدار: <code>{vdisp}</code>")
        else:
            lines.append(f"🔢 Version: <code>{vdisp}</code>")

    # Size
    size = info.get("size_bytes")
    if size is not None:
        if lang == "ar":
            lines.append(f"📊 الحجم: <code>{humanbytes(size)} ({size} B)</code>")
        else:
            lines.append(f"📊 Size: <code>{humanbytes(size)} ({size} B)</code>")

    # Android SDK
    min_sdk = info.get("min_sdk")
    target_sdk = info.get("target_sdk")
    if min_sdk is not None and target_sdk is not None:
        sdk_disp = f"minSdk {min_sdk} / target {target_sdk}"
    elif min_sdk is not None:
        sdk_disp = f"minSdk {min_sdk}"
    elif target_sdk is not None:
        sdk_disp = f"target {target_sdk}"
    else:
        sdk_disp = None

    if sdk_disp:
        if lang == "ar":
            lines.append(f"🤖 أندرويد: <code>{sdk_disp}</code>")
        else:
            lines.append(f"🤖 Android: <code>{sdk_disp}</code>")

    # Optional App Label
    label = info.get("label")
    if label:
        import html
        esc_label = html.escape(str(label))
        if lang == "ar":
            lines.append(f"📱 التطبيق: <code>{esc_label}</code>")
        else:
            lines.append(f"📱 App: <code>{esc_label}</code>")

    # File SHA-256
    file_sha256 = info.get("file_sha256")
    if file_sha256:
        if lang == "ar":
            lines.append("🔑 بصمة الملف SHA-256:")
        else:
            lines.append("🔑 File SHA-256:")
        lines.append(f"<code>{file_sha256}</code>")

    # Signer block
    cert_sha256 = info.get("cert_sha256")
    subject_dn = info.get("subject_dn")
    if not cert_sha256 and not subject_dn:
        if lang == "ar":
            lines.append("✍️ الموقّع: <code>لم يتم العثور على شهادة توقيع</code>")
        else:
            lines.append("✍️ Signer: <code>No signing certificate found</code>")
    else:
        import html
        esc_dn = html.escape(str(subject_dn or "Unknown"))
        if lang == "ar":
            lines.append(f"✍️ الموقّع: <code>{esc_dn}</code>")
            lines.append("🖋️ بصمة الشهادة SHA-256:")
            lines.append(f"<code>{cert_sha256}</code>")
        else:
            lines.append(f"✍️ Signer: <code>{esc_dn}</code>")
            lines.append("🖋️ Cert SHA-256:")
            lines.append(f"<code>{cert_sha256}</code>")

        # Signer consistency check
        if prev and prev.get("cert_sha256"):
            prev_v = prev.get("version_name") or prev.get("version_code") or "?"
            if prev["cert_sha256"] == cert_sha256:
                if lang == "ar":
                    lines.append(f"✅ نفس الموقّع مثل الإصدار v{prev_v}")
                else:
                    lines.append(f"✅ Same signer as v{prev_v}")
            else:
                if lang == "ar":
                    lines.append(f"⚠️ موقّع مختلف عن الإصدار v{prev_v} — تم تغيير التوقيع (لن يتم تثبيت التحديثات فوق الإصدار القديم)")
                else:
                    lines.append(f"⚠️ DIFFERENT signer than v{prev_v} — signature changed (updates will NOT install over the old version)")

    # Time
    if lang == "ar":
        lines.append(f"🕒 وقت الفحص: <code>{cairo_time_str}</code>")
    else:
        lines.append(f"🕒 Checked At: <code>{cairo_time_str}</code>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def run_suite():
    print("========================================")
    print("RUNNING APK INSPECT VERIFICATION SUITE")
    print("========================================")

    # 1. Real v1-signed APK
    print("\n--- Test (a): Real v1-signed APK (golden_v1.apk) ---")
    r1 = inspect_apk("tests_apk/golden_v1.apk")
    assert r1 is not None, "Failed on golden_v1.apk"
    assert r1["package"] == "android.appsecurity.cts.tinyapp"
    assert r1["version_name"] == "1.0"
    assert r1["version_code"] == 10
    assert r1["min_sdk"] == 23
    assert r1["target_sdk"] == 23
    assert r1["cert_sha256"] == "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8"
    assert r1["signer_source"] == "v1"
    print("PASSED: package, version, minSdk, targetSdk, cert SHA256 match perfectly.")

    # 2. Real v2/v3-only-signed APK
    print("\n--- Test (b): Real v2/v3-only-signed APK (golden_v2.apk) ---")
    r2 = inspect_apk("tests_apk/golden_v2.apk")
    assert r2 is not None, "Failed on golden_v2.apk"
    assert r2["package"] == "android.appsecurity.cts.tinyapp"
    assert r2["version_name"] == "1.0"
    assert r2["version_code"] == 10
    assert r2["cert_sha256"] == "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8"
    assert r2["signer_source"] == "v2/v3"
    print("PASSED: v2/v3 block parsed correctly without v1 cert.")

    # 3. XAPK Bundle
    print("\n--- Test (c): XAPK Bundle (manifest match & largest entry) ---")
    # Bundle with manifest match
    xapk_path = "tests_apk/sample_manifest.xapk"
    with zipfile.ZipFile(xapk_path, "w") as z:
        z.writestr("manifest.json", json.dumps({"package_name": "android.appsecurity.cts.tinyapp"}))
        z.write("tests_apk/golden_v1.apk", "android.appsecurity.cts.tinyapp.apk")
        z.writestr("config.arm64.apk", "dummy small apk")
    r3 = inspect_apk(xapk_path)
    assert r3 is not None
    assert r3["is_bundle"] is True
    assert "manifest package match" in r3["bundle_rule_en"]
    assert r3["package"] == "android.appsecurity.cts.tinyapp"
    assert r3["cert_sha256"] == "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8"
    print("PASSED: XAPK manifest match rule verified.")

    # Bundle without manifest match (largest APK rule)
    apks_path = "tests_apk/sample_largest.apks"
    with zipfile.ZipFile(apks_path, "w") as z:
        z.writestr("split_small.apk", "small dummy data")
        z.write("tests_apk/v2_only.apk", "split_main.apk")
    r3_largest = inspect_apk(apks_path)
    assert r3_largest is not None
    assert r3_largest["is_bundle"] is True
    assert "largest APK" in r3_largest["bundle_rule_en"]
    assert r3_largest["package"] == "android.appsecurity.cts.tinyapp"
    assert r3_largest["cert_sha256"] == "BC5E64EAB1C4B5137C0FBC5ED05850B3A148D1C41775CFFA4D96EEA90BDD0EB8"
    print("PASSED: APKS largest entry rule verified.")

    # 4. Non-APK ZIP
    print("\n--- Test (d): Non-APK ZIP (clean degradation) ---")
    non_apk_path = "tests_apk/non_apk.zip"
    with zipfile.ZipFile(non_apk_path, "w") as z:
        z.writestr("readme.txt", "hello world")
        z.writestr("image.png", "fake image bytes")
    r4 = inspect_apk(non_apk_path)
    assert r4 is not None
    assert r4["package"] is None
    assert r4["version_name"] is None
    assert r4["cert_sha256"] is None
    assert r4["file_sha256"] is not None
    assert r4["size_bytes"] > 0
    card_non_apk = build_card(r4, None, lang="ar")
    assert "لم يتم العثور على شهادة توقيع" in card_non_apk
    print("PASSED: non-APK zip degraded cleanly, no crash.")

    # 5. Corrupt / truncated file
    print("\n--- Test (e): Truncated/corrupt APK ---")
    corrupt_path = "tests_apk/corrupt.apk"
    with open("tests_apk/golden_v1.apk", "rb") as f_in, open(corrupt_path, "wb") as f_out:
        f_out.write(f_in.read(100)) # truncate to 100 bytes
    r5 = inspect_apk(corrupt_path)
    assert r5 is None, "Truncated zip must return None"
    print("PASSED: Truncated file returned None safely without raising.")

    # 6. Signer consistency test
    print("\n--- Test (f): Signer Consistency Across Versions ---")
    test_db = "tests_apk/test_consistency.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apk_inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            package TEXT,
            version_name TEXT,
            version_code INTEGER,
            file_sha256 TEXT,
            cert_sha256 TEXT,
            size INTEGER,
            filename TEXT,
            checked_at REAL
        )
    """)
    conn.commit()

    def db_add(uid, pkg, vname, vcode, f_sha, c_sha, sz, fn, cat):
        c = conn.cursor()
        c.execute("""
            INSERT INTO apk_inspections (user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, pkg, vname, vcode, f_sha, c_sha, sz, fn, cat))
        conn.commit()

    def db_get_last(pkg, exclude_latest=True):
        c = conn.cursor()
        limit = 2 if exclude_latest else 1
        c.execute("SELECT id, user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at FROM apk_inspections WHERE package = ? ORDER BY id DESC LIMIT ?", (pkg, limit))
        rows = c.fetchall()
        if not rows: return None
        row = rows[1] if exclude_latest and len(rows) >= 2 else (None if exclude_latest else rows[0])
        if not row: return None
        return {"id": row[0], "user_id": row[1], "package": row[2], "version_name": row[3], "version_code": row[4], "file_sha256": row[5], "cert_sha256": row[6], "size": row[7], "filename": row[8], "checked_at": row[9]}

    # Step 1: Insert first inspection (v1.0)
    db_add(123, r1["package"], r1["version_name"], r1["version_code"], r1["file_sha256"], r1["cert_sha256"], r1["size_bytes"], "v1.apk", r1["checked_at"])
    prev1 = db_get_last(r1["package"], exclude_latest=True)
    assert prev1 is None, "First inspection must have no previous"

    # Step 2: Second inspection, same cert (v2.0 with golden_v2 cert which is identical)
    db_add(123, r2["package"], "1.1", 11, r2["file_sha256"], r2["cert_sha256"], r2["size_bytes"], "v2.apk", r2["checked_at"])
    prev2 = db_get_last(r2["package"], exclude_latest=True)
    assert prev2 is not None
    assert prev2["cert_sha256"] == r2["cert_sha256"]
    card_same_ar = build_card(r2, prev2, lang="ar")
    card_same_en = build_card(r2, prev2, lang="en")
    assert "✅ نفس الموقّع مثل الإصدار v1.0" in card_same_ar
    assert "✅ Same signer as v1.0" in card_same_en
    print("PASSED: Same signer verified (✅ line generated).")

    # Step 3: Third inspection, re-signed copy (v2_only has different cert!)
    r_diff = inspect_apk("tests_apk/v2_only.apk")
    db_add(123, r_diff["package"], "2.0", 20, r_diff["file_sha256"], r_diff["cert_sha256"], r_diff["size_bytes"], "v3_resigned.apk", r_diff["checked_at"])
    prev3 = db_get_last(r_diff["package"], exclude_latest=True)
    assert prev3 is not None
    assert prev3["cert_sha256"] != r_diff["cert_sha256"]
    card_diff_ar = build_card(r_diff, prev3, lang="ar")
    card_diff_en = build_card(r_diff, prev3, lang="en")
    assert "⚠️ موقّع مختلف عن الإصدار v1.1" in card_diff_ar
    assert "⚠️ DIFFERENT signer than v1.1" in card_diff_en
    print("PASSED: Different signer verified (⚠️ line generated).")

    conn.close()

    print("\n--- Card Output Sample (Arabic) ---")
    print(card_diff_ar)
    print("\n--- Card Output Sample (English) ---")
    print(card_diff_en)
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_suite()
