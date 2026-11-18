import asyncio
import datetime
import hashlib
import html
import json
import logging
import os
import shutil
import struct
import sys
import time
import zipfile
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs7
from pyrogram.enums import ParseMode
from pyrogram.types import Message

import myidm  # noqa: F401
from myidm import config as cfg
from myidm import db
from myidm import utils
from myidm import validation

logger = logging.getLogger("bot.apk_inspect")
_self = sys.modules[__name__]


def compute_file_sha256(filepath: str, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().upper()


def format_dn(name: x509.Name) -> str:
    try:
        parts = []
        for attr in name:
            oid_name = attr.oid._name
            val = str(attr.value)
            if oid_name == "commonName":
                parts.append(f"CN={val}")
            elif oid_name == "organizationName":
                parts.append(f"O={val}")
            elif oid_name == "organizationalUnitName":
                parts.append(f"OU={val}")
            elif oid_name == "countryName":
                parts.append(f"C={val}")
            elif oid_name == "stateOrProvinceName":
                parts.append(f"ST={val}")
            elif oid_name == "localityName":
                parts.append(f"L={val}")
            elif oid_name == "emailAddress":
                parts.append(f"emailAddress={val}")
            else:
                label = oid_name or attr.oid.dotted_string
                parts.append(f"{label}={val}")
        if parts:
            return ", ".join(parts)
        return name.rfc4514_string()
    except Exception:
        return name.rfc4514_string()


def parse_axml(raw: bytes) -> dict:
    result = {
        "package": None,
        "version_name": None,
        "version_code": None,
        "min_sdk": None,
        "target_sdk": None,
        "label": None,
    }
    if not raw or len(raw) < 8:
        return result
    try:
        magic, header_size, file_size = struct.unpack_from('<HHI', raw, 0)
        if magic != 0x0003:  # RES_XML_TYPE
            return result

        offset = header_size
        strings = []
        res_ids = []

        RES_LABEL = 0x01010001
        RES_NAME = 0x01010003
        RES_MIN_SDK = 0x0101020c
        RES_VERSION_CODE = 0x0101021b
        RES_VERSION_NAME = 0x0101021c
        RES_TARGET_SDK = 0x01010270

        while offset + 8 <= len(raw):
            chunk_type, chunk_header_size, chunk_size = struct.unpack_from('<HHI', raw, offset)
            if chunk_size == 0 or offset + chunk_size > len(raw):
                break

            if chunk_type == 0x0001:  # RES_STRING_POOL_TYPE
                if chunk_size >= 28:
                    str_cnt, sty_cnt, flags, str_start, sty_start = struct.unpack_from('<IIIII', raw, offset + 8)
                    is_utf8 = bool(flags & 0x0100)
                    offsets_start = offset + 28
                    if offsets_start + str_cnt * 4 <= offset + chunk_size:
                        offsets = struct.unpack_from(f'<{str_cnt}I', raw, offsets_start)
                        base_str = offset + str_start
                        for off in offsets:
                            cur = base_str + off
                            if cur >= len(raw):
                                strings.append("")
                                continue
                            try:
                                if is_utf8:
                                    b1 = raw[cur]; cur += 1
                                    if b1 & 0x80:
                                        cur += 1
                                    b2 = raw[cur]; cur += 1
                                    if b2 & 0x80:
                                        b3 = raw[cur]; cur += 1
                                        byte_len = ((b2 & 0x7F) << 8) | b3
                                    else:
                                        byte_len = b2
                                    s = raw[cur:cur + byte_len].decode('utf-8', errors='replace')
                                else:
                                    u16_len = struct.unpack_from('<H', raw, cur)[0]
                                    cur += 2
                                    if u16_len & 0x8000:
                                        u16_len2 = struct.unpack_from('<H', raw, cur)[0]
                                        cur += 2
                                        u16_len = ((u16_len & 0x7FFF) << 16) | u16_len2
                                    byte_len = u16_len * 2
                                    s = raw[cur:cur + byte_len].decode('utf-16le', errors='replace')
                                strings.append(s)
                            except Exception:
                                strings.append("")

            elif chunk_type == 0x0180:  # RES_XML_RESOURCE_MAP_TYPE
                count = (chunk_size - chunk_header_size) // 4
                if count > 0:
                    res_ids = list(struct.unpack_from(f'<{count}I', raw, offset + chunk_header_size))

            elif chunk_type == 0x0102:  # RES_XML_START_ELEMENT_TYPE
                if offset + 30 <= len(raw):
                    ns_idx, name_idx = struct.unpack_from('<II', raw, offset + 16)
                    attr_start, attr_size, attr_count = struct.unpack_from('<HHH', raw, offset + 24)
                    tag_name = strings[name_idx] if name_idx < len(strings) else ""

                    attrs_base = offset + 16 + attr_start
                    for i in range(attr_count):
                        attr_offset = attrs_base + i * attr_size
                        if attr_offset + 20 > len(raw):
                            break
                        a_ns, a_name, a_raw_val, a_type_data, a_data = struct.unpack_from('<IIIII', raw, attr_offset)
                        data_type = (a_type_data >> 24) & 0xFF

                        attr_name = strings[a_name] if a_name < len(strings) else ""
                        attr_res_id = res_ids[a_name] if a_name < len(res_ids) else 0

                        val_str = strings[a_raw_val] if (0 <= a_raw_val < len(strings)) else None
                        if val_str is None and data_type == 0x03:
                            if 0 <= a_data < len(strings):
                                val_str = strings[a_data]

                        if tag_name == "manifest":
                            if attr_name == "package":
                                result["package"] = val_str or (strings[a_data] if 0 <= a_data < len(strings) else None)
                            elif attr_name == "versionName" or attr_res_id == RES_VERSION_NAME:
                                result["version_name"] = val_str or (strings[a_data] if data_type == 0x03 and 0 <= a_data < len(strings) else str(a_data))
                            elif attr_name == "versionCode" or attr_res_id == RES_VERSION_CODE:
                                if data_type in (0x10, 0x11):
                                    result["version_code"] = a_data
                                elif val_str and val_str.isdigit():
                                    result["version_code"] = int(val_str)
                                elif a_data:
                                    result["version_code"] = a_data

                        elif tag_name == "uses-sdk":
                            if attr_name == "minSdkVersion" or attr_res_id == RES_MIN_SDK:
                                if data_type in (0x10, 0x11):
                                    result["min_sdk"] = a_data
                                elif val_str:
                                    result["min_sdk"] = int(val_str) if val_str.isdigit() else val_str
                                else:
                                    result["min_sdk"] = a_data
                            elif attr_name == "targetSdkVersion" or attr_res_id == RES_TARGET_SDK:
                                if data_type in (0x10, 0x11):
                                    result["target_sdk"] = a_data
                                elif val_str:
                                    result["target_sdk"] = int(val_str) if val_str.isdigit() else val_str
                                else:
                                    result["target_sdk"] = a_data

                        elif tag_name == "application":
                            if attr_name == "label" or attr_res_id == RES_LABEL:
                                if data_type == 0x03 and 0 <= a_data < len(strings):
                                    cand = strings[a_data]
                                    if not cand.startswith("@") and not cand.startswith("res/"):
                                        result["label"] = cand
                                elif val_str and not val_str.startswith("@") and not val_str.startswith("res/"):
                                    result["label"] = val_str

            offset += chunk_size
    except Exception:
        pass
    return result


def extract_v1_cert(z: zipfile.ZipFile):
    for f in z.namelist():
        upper = f.upper()
        if upper.startswith("META-INF/") and upper.endswith((".RSA", ".DSA", ".EC")):
            try:
                data = z.read(f)
                certs = pkcs7.load_der_pkcs7_certificates(data)
                if certs:
                    return certs[0]
            except Exception:
                continue
    return None


def extract_v2_v3_cert(filepath: str):
    try:
        with open(filepath, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size < 32:
                return None
            max_search = min(size, 65535 + 22)
            f.seek(size - max_search)
            buf = f.read(max_search)
            pos = buf.rfind(b"PK\x05\x06")
            if pos == -1:
                return None
            cd_offset = struct.unpack_from("<I", buf, pos + 16)[0]
            if cd_offset < 24 or cd_offset > size:
                return None

            f.seek(cd_offset - 24)
            footer = f.read(24)
            if len(footer) < 24:
                return None
            size_of_block, magic = struct.unpack("<Q16s", footer)
            if magic != b"APK Sig Block 42":
                return None
            block_start = cd_offset - size_of_block - 8
            if block_start < 0:
                return None
            f.seek(block_start)
            header = f.read(8)
            if struct.unpack("<Q", header)[0] != size_of_block:
                return None

            pairs_len = size_of_block - 24
            pairs_data = f.read(pairs_len)
            offset = 0
            v2_payload = None
            v3_payload = None
            while offset + 12 <= len(pairs_data):
                pair_len, pair_id = struct.unpack_from("<QI", pairs_data, offset)
                val_len = pair_len - 4
                val_start = offset + 12
                if val_start + val_len > len(pairs_data):
                    break
                if pair_id == 0x7109871a:  # v2
                    v2_payload = pairs_data[val_start:val_start + val_len]
                elif pair_id == 0xf05368c0:  # v3
                    v3_payload = pairs_data[val_start:val_start + val_len]
                offset += 8 + pair_len

            payload = v2_payload or v3_payload
            if not payload or len(payload) < 8:
                return None

            signers_len = struct.unpack_from("<I", payload, 0)[0]
            pos = 4
            if pos + signers_len > len(payload):
                return None
            signer_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            if pos + signer_len > len(payload):
                return None
            signed_data_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            if pos + signed_data_len > len(payload):
                return None
            digests_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4 + digests_len
            if pos + 4 > len(payload):
                return None
            certs_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            if certs_len < 4 or pos + 4 > len(payload):
                return None
            first_cert_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            if pos + first_cert_len > len(payload):
                return None
            cert_bytes = payload[pos:pos + first_cert_len]
            return x509.load_der_x509_certificate(cert_bytes)
    except Exception:
        return None


def inspect_apk(file_path: str) -> dict | None:
    if not file_path or not os.path.exists(file_path):
        return None

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return None

    try:
        is_bin, _ = validation.is_valid_binary_file(file_path)
        if not is_bin:
            return None
    except Exception:
        pass

    if not zipfile.is_zipfile(file_path):
        return None

    try:
        file_sha256 = _self.compute_file_sha256(file_path)
    except Exception:
        return None

    checked_at = time.time()

    is_bundle = False
    bundle_rule_en = None
    bundle_rule_ar = None
    base_apk_entry_name = None
    base_apk_size = None
    base_apk_sha256 = None
    target_apk_path = file_path
    temp_extracted_apk = None

    clean_name = os.path.basename(file_path).lower()
    if clean_name.endswith((".xapk", ".apks")):
        is_bundle = True
        try:
            with zipfile.ZipFile(file_path, "r") as z_bundle:
                apk_entries = [info for info in z_bundle.infolist() if info.filename.lower().endswith(".apk") and not info.is_dir()]
                if not apk_entries:
                    return {
                        "package": None,
                        "version_name": None,
                        "version_code": None,
                        "min_sdk": None,
                        "target_sdk": None,
                        "label": None,
                        "cert_sha256": None,
                        "cert_sha1": None,
                        "subject_dn": None,
                        "signer_source": None,
                        "file_sha256": file_sha256,
                        "size_bytes": file_size,
                        "checked_at": checked_at,
                        "is_bundle": True,
                        "bundle_rule_en": "no APK entry found in bundle",
                        "bundle_rule_ar": "لم يتم العثور على ملفات APK داخل الحزمة",
                        "filename": os.path.basename(file_path)
                    }

                chosen_entry = None
                # Rule 1: manifest.json package match
                if "manifest.json" in z_bundle.namelist():
                    try:
                        m_data = json.loads(z_bundle.read("manifest.json").decode("utf-8", errors="ignore"))
                        pkg_name = m_data.get("package_name")
                        if pkg_name:
                            for e in apk_entries:
                                e_base = os.path.basename(e.filename).lower()
                                if e_base == f"{pkg_name.lower()}.apk":
                                    chosen_entry = e
                                    bundle_rule_en = "manifest package match"
                                    bundle_rule_ar = "مطابقة اسم الحزمة"
                                    break
                    except Exception:
                        pass

                # Rule 2: base.apk
                if not chosen_entry:
                    for e in apk_entries:
                        e_base = os.path.basename(e.filename).lower()
                        if e_base in ("base.apk", "base-master.apk"):
                            chosen_entry = e
                            bundle_rule_en = f"base APK ({e_base})"
                            bundle_rule_ar = f"ملف الحزمة الأساسي ({e_base})"
                            break

                # Rule 3: largest *.apk entry
                if not chosen_entry:
                    chosen_entry = max(apk_entries, key=lambda e: e.file_size)
                    e_base = os.path.basename(chosen_entry.filename)
                    bundle_rule_en = f"largest APK entry ({e_base})"
                    bundle_rule_ar = f"الملف الأكبر ({e_base})"

                tmp_dir = cfg.DOWNLOAD_DIR if os.path.exists(cfg.DOWNLOAD_DIR) else (os.path.dirname(file_path) or os.getcwd())
                temp_extracted_apk = os.path.join(tmp_dir, f"_temp_inspect_{os.getpid()}_{int(time.time()*1000)}.apk")
                with z_bundle.open(chosen_entry) as src, open(temp_extracted_apk, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                target_apk_path = temp_extracted_apk
                base_apk_entry_name = chosen_entry.filename
                base_apk_size = os.path.getsize(temp_extracted_apk)
                base_apk_sha256 = _self.compute_file_sha256(temp_extracted_apk)
        except Exception:
            return None

    manifest_info = {
        "package": None,
        "version_name": None,
        "version_code": None,
        "min_sdk": None,
        "target_sdk": None,
        "label": None,
    }
    cert = None
    signer_source = None

    try:
        try:
            with zipfile.ZipFile(target_apk_path, "r") as z:
                if "AndroidManifest.xml" in z.namelist():
                    raw_axml = z.read("AndroidManifest.xml")
                    manifest_info = _self.parse_axml(raw_axml)

                # Try v1 signature
                cert = _self.extract_v1_cert(z)
                if cert:
                    signer_source = "v1"
        except Exception:
            pass

        # If no v1 cert, try APK signing block (v2/v3)
        if not cert:
            cert = _self.extract_v2_v3_cert(target_apk_path)
            if cert:
                signer_source = "v2/v3"
    finally:
        if temp_extracted_apk and os.path.exists(temp_extracted_apk):
            try:
                os.remove(temp_extracted_apk)
            except Exception:
                pass

    cert_sha256 = None
    cert_sha1 = None
    subject_dn = None
    if cert:
        try:
            cert_sha256 = cert.fingerprint(hashes.SHA256()).hex().upper()
            cert_sha1 = cert.fingerprint(hashes.SHA1()).hex().upper()
            subject_dn = _self.format_dn(cert.subject)
        except Exception:
            pass

    return {
        "package": manifest_info.get("package"),
        "version_name": manifest_info.get("version_name"),
        "version_code": manifest_info.get("version_code"),
        "min_sdk": manifest_info.get("min_sdk"),
        "target_sdk": manifest_info.get("target_sdk"),
        "label": manifest_info.get("label"),
        "cert_sha256": cert_sha256,
        "cert_sha1": cert_sha1,
        "subject_dn": subject_dn,
        "signer_source": signer_source,
        "file_sha256": file_sha256,
        "size_bytes": file_size,
        "checked_at": checked_at,
        "is_bundle": is_bundle,
        "bundle_rule_en": bundle_rule_en,
        "bundle_rule_ar": bundle_rule_ar,
        "base_apk_entry_name": base_apk_entry_name,
        "base_apk_size": base_apk_size,
        "base_apk_sha256": base_apk_sha256,
        "filename": os.path.basename(file_path)
    }


def format_apk_inspection_card(info: dict, prev: dict | None, lang: str = "ar") -> str:
    if not info:
        return ""

    lines = []
    lines.append("🛡️ فحص APK / APK Inspection")

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
            lines.append(f"📦 الباكدج: <code>{html.escape(package)}</code>")
        else:
            lines.append(f"📦 Package: <code>{html.escape(package)}</code>")

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
            lines.append(f"🔢 الإصدار: <code>{html.escape(vdisp)}</code>")
        else:
            lines.append(f"🔢 Version: <code>{html.escape(vdisp)}</code>")

    # Size & File Hash:
    is_bundle = info.get("is_bundle", False)
    if is_bundle:
        size = info.get("size_bytes")
        file_sha256 = info.get("file_sha256")
        base_size = info.get("base_apk_size")
        base_sha256 = info.get("base_apk_sha256")
        base_entry = info.get("base_apk_entry_name")

        if size is not None:
            if lang == "ar":
                lines.append(f"📊 حجم الحزمة (Bundle): <code>{utils.humanbytes(size)} ({size} B)</code>")
            else:
                lines.append(f"📊 Delivered Bundle Size: <code>{utils.humanbytes(size)} ({size} B)</code>")
        if file_sha256:
            if lang == "ar":
                lines.append("🔑 بصمة الحزمة SHA-256:")
            else:
                lines.append("🔑 Delivered Bundle SHA-256:")
            lines.append(f"<code>{file_sha256}</code>")
        if base_entry:
            if lang == "ar":
                lines.append(f"📁 ملف APK الأساسي: <code>{html.escape(base_entry)}</code>")
            else:
                lines.append(f"📁 Base APK Entry: <code>{html.escape(base_entry)}</code>")
        if base_size is not None:
            if lang == "ar":
                lines.append(f"📊 حجم APK الأساسي: <code>{utils.humanbytes(base_size)} ({base_size} B)</code>")
            else:
                lines.append(f"📊 Base APK Size: <code>{utils.humanbytes(base_size)} ({base_size} B)</code>")
        if base_sha256:
            if lang == "ar":
                lines.append("🔑 بصمة APK الأساسي SHA-256:")
            else:
                lines.append("🔑 Base APK SHA-256:")
            lines.append(f"<code>{base_sha256}</code>")
    else:
        # Standard APK
        size = info.get("size_bytes")
        if size is not None:
            if lang == "ar":
                lines.append(f"📊 الحجم: <code>{utils.humanbytes(size)} ({size} B)</code>")
            else:
                lines.append(f"📊 Size: <code>{utils.humanbytes(size)} ({size} B)</code>")

        file_sha256 = info.get("file_sha256")
        if file_sha256:
            if lang == "ar":
                lines.append("🔑 بصمة الملف SHA-256:")
            else:
                lines.append("🔑 File SHA-256:")
            lines.append(f"<code>{file_sha256}</code>")

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
            lines.append(f"🤖 أندرويد: <code>{html.escape(sdk_disp)}</code>")
        else:
            lines.append(f"🤖 Android: <code>{html.escape(sdk_disp)}</code>")

    # Optional App Label
    label = info.get("label")
    if label:
        esc_label = html.escape(str(label))
        if lang == "ar":
            lines.append(f"📱 التطبيق: <code>{esc_label}</code>")
        else:
            lines.append(f"📱 App: <code>{esc_label}</code>")

    # Signer block
    cert_sha256 = info.get("cert_sha256")
    subject_dn = info.get("subject_dn")
    if not cert_sha256 and not subject_dn:
        if lang == "ar":
            lines.append("✍️ الموقّع: <code>لم يتم العثور على شهادة توقيع</code>")
        else:
            lines.append("✍️ Signer: <code>No signing certificate found</code>")
    else:
        esc_dn = html.escape(str(subject_dn or "Unknown"))
        if lang == "ar":
            lines.append(f"✍️ الموقّع: <code>{esc_dn}</code>")
            lines.append("🖋️ بصمة الشهادة SHA-256:")
            lines.append(f"<code>{cert_sha256}</code>")
        else:
            lines.append(f"✍️ Signer: <code>{esc_dn}</code>")
            lines.append("🖋️ Cert SHA-256:")
            lines.append(f"<code>{cert_sha256}</code>")

        # Signer consistency check (only if prev exists with a different version_code)
        if prev and prev.get("cert_sha256"):
            prev_v = prev.get("version_name") or prev.get("version_code") or "?"
            if prev["cert_sha256"] == cert_sha256:
                if lang == "ar":
                    lines.append(f"✅ نفس الموقّع مثل الإصدار v{prev_v}")
                else:
                    lines.append(f"✅ Same signer as v{prev_v}")
            else:
                if lang == "ar":
                    lines.append(f"⚠️ موقّع مختلف عن الإصدار v{prev_v} \u2014 تم تغيير التوقيع (لن يتم تثبيت التحديثات فوق الإصدار القديم)")
                else:
                    lines.append(f"⚠️ DIFFERENT signer than v{prev_v} \u2014 signature changed (updates will NOT install over the old version)")

    # Time
    checked_at = info.get("checked_at", time.time())
    cairo_time_str = utils.format_cairo_time(checked_at)
    if lang == "ar":
        lines.append(f"🕒 وقت الفحص: <code>{cairo_time_str}</code>")
    else:
        lines.append(f"🕒 Checked At: <code>{cairo_time_str}</code>")

    return "\n".join(lines)


def format_signer_change_warning(info: dict, prev: dict | None) -> str | None:
    if not info or not prev:
        return None
    curr_cert = info.get("cert_sha256")
    prev_cert = prev.get("cert_sha256")
    if not curr_cert or not prev_cert:
        return None
    if curr_cert == prev_cert or str(curr_cert).strip().upper() == str(prev_cert).strip().upper():
        return None

    package = info.get("package") or prev.get("package") or "Unknown"
    prev_vc = prev.get("version_code")
    curr_vc = info.get("version_code")

    prev_vc_str = str(prev_vc) if prev_vc is not None else "?"
    curr_vc_str = str(curr_vc) if curr_vc is not None else "?"

    return (
        "⚠️ تنبيه: توقيع النسخة دي مختلف عن النسخة اللي فاتت من نفس التطبيق / Warning: this version is signed differently from the previous version of this app\n"
        f"{package} ({prev_vc_str} → {curr_vc_str})"
    )


def format_blitzverify_block(info: dict) -> str:
    if not info:
        return ""

    def is_valid_val(val):
        if val is None:
            return False
        s = str(val).strip()
        if not s or s.lower() in ("unknown", "-", "n/a", "none"):
            return False
        return True

    lines = ["BLITZVERIFY v1"]

    # 1. package
    pkg = info.get("package")
    if is_valid_val(pkg):
        lines.append(f"package: {str(pkg).strip()}")

    # 2. version_name
    vname = info.get("version_name")
    if is_valid_val(vname):
        lines.append(f"version_name: {str(vname).strip()}")

    # 3. version_code
    vcode = info.get("version_code")
    if is_valid_val(vcode):
        try:
            lines.append(f"version_code: {int(vcode)}")
        except (ValueError, TypeError):
            pass

    # 4. size_bytes
    size_bytes = info.get("size_bytes")
    if is_valid_val(size_bytes):
        try:
            lines.append(f"size_bytes: {int(size_bytes)}")
        except (ValueError, TypeError):
            pass

    # 5. min_sdk
    min_sdk = info.get("min_sdk")
    if is_valid_val(min_sdk):
        try:
            lines.append(f"min_sdk: {int(min_sdk)}")
        except (ValueError, TypeError):
            pass

    # 6. target_sdk
    target_sdk = info.get("target_sdk")
    if is_valid_val(target_sdk):
        try:
            lines.append(f"target_sdk: {int(target_sdk)}")
        except (ValueError, TypeError):
            pass

    # 7. file_sha256
    file_sha256 = info.get("file_sha256")
    if is_valid_val(file_sha256):
        f_sha = str(file_sha256).strip().replace(":", "").lower()
        if f_sha and f_sha not in ("unknown", "-", "n/a", "none"):
            lines.append(f"file_sha256: {f_sha}")

    # 8. cert_sha256
    cert_sha256 = info.get("cert_sha256")
    if is_valid_val(cert_sha256):
        c_sha = str(cert_sha256).strip().replace(":", "").lower()
        if c_sha and c_sha not in ("unknown", "-", "n/a", "none"):
            lines.append(f"cert_sha256: {c_sha}")

    # 9. inspected_at
    checked_at = info.get("checked_at")
    if is_valid_val(checked_at):
        try:
            epoch = float(checked_at)
            try:
                tz = ZoneInfo("Africa/Cairo")
            except Exception:
                tz = datetime.timezone(datetime.timedelta(hours=3))
            dt = datetime.datetime.fromtimestamp(epoch, tz=tz)
            lines.append(f"inspected_at: {dt.strftime('%Y-%m-%d %H:%M')}")
        except Exception:
            pass

    content = "\n".join(lines)
    return f"```\n{content}\n```"


async def handle_apk_inspection_card(file_path: str, filename: str, user_id: int, user_msg: Message, lang: str = "ar", precomputed_info: dict | None = None):
    try:
        lower_name = (filename or "").lower()
        if not lower_name.endswith((".apk", ".xapk", ".apks")):
            return
        if not file_path or not os.path.exists(file_path):
            return

        if precomputed_info:
            info = precomputed_info
        else:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, _self.inspect_apk, file_path)
        if not info:
            return

        package = info.get("package")
        vcode = info.get("version_code")
        cert_sha256 = info.get("cert_sha256")

        # Get previous inspection for different version_code BEFORE recording new one
        prev = db.db_get_last_inspection_for_package(package, exclude_latest=True, exclude_version_code=vcode) if package else None

        # Record in DB
        db.db_add_apk_inspection(
            user_id=user_id,
            package=package,
            version_name=info.get("version_name"),
            version_code=vcode,
            file_sha256=info.get("file_sha256"),
            cert_sha256=cert_sha256,
            size=info.get("size_bytes"),
            filename=filename,
            checked_at=info.get("checked_at"),
            min_sdk=info.get("min_sdk"),
            target_sdk=info.get("target_sdk")
        )

        warn_text = _self.format_signer_change_warning(info, prev)
        if warn_text:
            try:
                await user_msg.reply_text(warn_text, parse_mode=ParseMode.DISABLED)
            except Exception as e_warn:
                logger.error(f"Signer change warning send failed: {e_warn}", exc_info=True)

        try:
            block_text = _self.format_blitzverify_block(info)
            if block_text:
                await user_msg.reply_text(block_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e_block:
            logger.error(f"BLITZVERIFY block send failed: {e_block}", exc_info=True)
    except Exception as e:
        logger.error(f"APK inspection card failed silently: {e}", exc_info=True)
