import os
import time
import json
import secrets
import logging
import sqlite3

from myidm import config as cfg

logger = logging.getLogger("bot.db")

# ==========================================
# 3. إدارة وتحديث قاعدة البيانات الدائمة
# ==========================================
ALLOWED_USER_SETTINGS = {
    "upload_mode", "enable_thumbs", "enable_caption", "fast_speed",
    "god_threads", "lang", "clean_tags", "custom_prefix", "custom_suffix",
    "channel_tag", "brand_position", "channel_button"
}

def get_or_create_dashboard_secret() -> str:
    env_secret = os.environ.get("DASHBOARD_SECRET", "").strip()
    if env_secret:
        return env_secret
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("SELECT value FROM bot_meta WHERE key = 'dashboard_secret'")
    row = cursor.fetchone()
    if row and row[0]:
        secret = row[0]
    else:
        secret = secrets.token_hex(24)
        cursor.execute("INSERT OR REPLACE INTO bot_meta (key, value) VALUES ('dashboard_secret', ?)", (secret,))
        conn.commit()
    conn.close()
    return secret

def init_db():
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at REAL,
            upload_mode TEXT DEFAULT 'auto',
            enable_thumbs INTEGER DEFAULT 1,
            enable_caption INTEGER DEFAULT 1,
            fast_speed INTEGER DEFAULT 1,
            god_threads INTEGER DEFAULT 64,
            lang TEXT DEFAULT 'ar',
            clean_tags INTEGER DEFAULT 1,
            custom_prefix TEXT DEFAULT '',
            custom_suffix TEXT DEFAULT '',
            channel_tag TEXT DEFAULT '',
            brand_position TEXT DEFAULT 'suffix',
            channel_button INTEGER DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            size INTEGER,
            category TEXT DEFAULT '📁 عام',
            timestamp REAL
        )
    """)
    
    # DEF-04: Unused table preserved verbatim for schema parity (IBC-05 excluded)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY,
            val_num INTEGER DEFAULT 0,
            val_float REAL DEFAULT 0.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_replacements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            find_text TEXT,
            replace_text TEXT
        )
    """)

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
            checked_at REAL,
            min_sdk INTEGER,
            target_sdk INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            url_key TEXT NOT NULL,
            filename TEXT,
            total_size INTEGER,
            chat_id INTEGER NOT NULL,
            message_ids TEXT NOT NULL,
            package TEXT,
            version_code INTEGER,
            created_at INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_user_url ON download_deliveries(user_id, url_key)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            file_path TEXT,
            filename TEXT,
            custom_caption TEXT,
            package TEXT,
            version_name TEXT,
            version_code INTEGER,
            size INTEGER,
            created_at REAL,
            status TEXT DEFAULT 'pending',
            inspection_json TEXT,
            flow_type TEXT DEFAULT 'direct'
        )
    """)
    
    for col, col_def in [
        ("god_threads", "INTEGER DEFAULT 64"),
        ("lang", "TEXT DEFAULT 'ar'"),
        ("clean_tags", "INTEGER DEFAULT 1"),
        ("custom_prefix", "TEXT DEFAULT ''"),
        ("custom_suffix", "TEXT DEFAULT ''"),
        ("channel_tag", "TEXT DEFAULT ''"),
        ("brand_position", "TEXT DEFAULT 'suffix'"),
        ("channel_button", "INTEGER DEFAULT 1")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("ALTER TABLE history ADD COLUMN category TEXT DEFAULT '📁 عام'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE pending_downloads ADD COLUMN url_key TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE apk_inspections ADD COLUMN min_sdk INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE apk_inspections ADD COLUMN target_sdk INTEGER")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def db_add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, time.time()))
    conn.commit()
    conn.close()

def db_get_user_settings(user_id: int) -> dict:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT upload_mode, enable_thumbs, enable_caption, fast_speed, god_threads, lang,
                   clean_tags, custom_prefix, custom_suffix, channel_tag, brand_position, channel_button
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if row:
        return {
            "upload_mode": row[0] or "auto",
            "enable_thumbs": row[1] if row[1] is not None else 1,
            "enable_caption": row[2] if row[2] is not None else 1,
            "fast_speed": row[3] if row[3] is not None else 1,
            "god_threads": row[4] or 64,
            "lang": row[5] or "ar",
            "clean_tags": row[6] if row[6] is not None else 1,
            "custom_prefix": row[7] or "",
            "custom_suffix": row[8] or "",
            "channel_tag": (row[9] if len(row) > 9 and row[9] is not None else "") or "",
            "brand_position": (row[10] if len(row) > 10 and row[10] is not None else "suffix") or "suffix",
            "channel_button": (row[11] if len(row) > 11 and row[11] is not None else 1)
        }
    return {
        "upload_mode": "auto",
        "enable_thumbs": 1,
        "enable_caption": 1,
        "fast_speed": 1,
        "god_threads": 64,
        "lang": "ar",
        "clean_tags": 1,
        "custom_prefix": "",
        "custom_suffix": "",
        "channel_tag": "",
        "brand_position": "suffix",
        "channel_button": 1
    }

def db_add_replacement(user_id: int, find_text: str, replace_text: str):
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO custom_replacements (user_id, find_text, replace_text)
        VALUES (?, ?, ?)
    """, (user_id, find_text, replace_text))
    conn.commit()
    conn.close()

def db_get_user_replacements(user_id: int) -> list:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT find_text, replace_text FROM custom_replacements WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_clear_user_replacements(user_id: int):
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_replacements WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def db_get_total_users_count() -> int:
    try:
        conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        cnt = cursor.fetchone()[0]
        conn.close()
        return cnt
    except Exception:
        return 0

def db_update_user_setting(user_id: int, key: str, val):
    if key not in ALLOWED_USER_SETTINGS:
        logger.warning(f"Rejected attempt to update unauthorized setting: {key}")
        return
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def db_add_history(user_id: int, filename: str, size: int, category: str):
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, filename, size, category, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (user_id, filename, size, category, time.time()))
    conn.commit()
    conn.close()

def db_get_history(user_id: int, limit: int = 10) -> list:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT filename, size, category, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows

def db_add_apk_inspection(user_id: int, package: str, version_name: str, version_code: int,
                          file_sha256: str, cert_sha256: str, size: int, filename: str,
                          checked_at: float = None, min_sdk: int | None = None, target_sdk: int | None = None) -> int:
    if checked_at is None:
        checked_at = time.time()
    if min_sdk is not None:
        try:
            min_sdk = int(min_sdk)
        except (ValueError, TypeError):
            pass
    if target_sdk is not None:
        try:
            target_sdk = int(target_sdk)
        except (ValueError, TypeError):
            pass
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO apk_inspections (user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at, min_sdk, target_sdk)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at, min_sdk, target_sdk))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def db_get_last_inspection_for_package(package: str, exclude_latest: bool = True, exclude_version_code: int | None = None) -> dict | None:
    if not package:
        return None
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        if exclude_version_code is not None:
            cursor.execute("""
                SELECT id, user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at, min_sdk, target_sdk
                FROM apk_inspections
                WHERE package = ? AND version_code != ?
                ORDER BY id DESC
                LIMIT 1
            """, (package, exclude_version_code))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "user_id": row[1],
                "package": row[2],
                "version_name": row[3],
                "version_code": row[4],
                "file_sha256": row[5],
                "cert_sha256": row[6],
                "size": row[7],
                "filename": row[8],
                "checked_at": row[9],
                "min_sdk": row[10],
                "target_sdk": row[11]
            }
        else:
            limit = 2 if exclude_latest else 1
            cursor.execute("""
                SELECT id, user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at, min_sdk, target_sdk
                FROM apk_inspections
                WHERE package = ?
                ORDER BY id DESC
                LIMIT ?
            """, (package, limit))
            rows = cursor.fetchall()
            if not rows:
                return None
            if exclude_latest:
                if len(rows) < 2:
                    return None
                row = rows[1]
            else:
                row = rows[0]
            return {
                "id": row[0],
                "user_id": row[1],
                "package": row[2],
                "version_name": row[3],
                "version_code": row[4],
                "file_sha256": row[5],
                "cert_sha256": row[6],
                "size": row[7],
                "filename": row[8],
                "checked_at": row[9],
                "min_sdk": row[10],
                "target_sdk": row[11]
            }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def db_check_apk_duplicate(package: str, version_code: int) -> dict | None:
    if not package or version_code is None:
        return None
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at, min_sdk, target_sdk
            FROM apk_inspections
            WHERE package = ? AND version_code = ?
            ORDER BY id DESC
            LIMIT 1
        """, (package, version_code))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "package": row[2],
            "version_name": row[3],
            "version_code": row[4],
            "file_sha256": row[5],
            "cert_sha256": row[6],
            "size": row[7],
            "filename": row[8],
            "checked_at": row[9],
            "min_sdk": row[10],
            "target_sdk": row[11]
        }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def db_add_pending_download(user_id: int, chat_id: int, file_path: str, filename: str,
                            custom_caption: str, package: str, version_name: str,
                            version_code: int, size: int, status: str = "pending",
                            inspection_json: str = "", flow_type: str = "direct",
                            url_key: str = "") -> int:
    if url_key:
        try:
            _ij = json.loads(inspection_json) if inspection_json else {}
            if isinstance(_ij, dict):
                _ij["url_key"] = url_key
                inspection_json = json.dumps(_ij)
        except Exception:
            pass
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO pending_downloads (user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, created_at, status, inspection_json, flow_type, url_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, time.time(), status, inspection_json, flow_type, url_key))
    except sqlite3.OperationalError:
        cursor.execute("""
            INSERT INTO pending_downloads (user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, created_at, status, inspection_json, flow_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, time.time(), status, inspection_json, flow_type))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def db_get_pending_download(pending_id: int) -> dict | None:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute("""
                SELECT id, user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, created_at, status, inspection_json, flow_type, url_key
                FROM pending_downloads
                WHERE id = ?
            """, (pending_id,))
            row = cursor.fetchone()
            if not row:
                return None
            ret = {
                "id": row[0],
                "user_id": row[1],
                "chat_id": row[2],
                "file_path": row[3],
                "filename": row[4],
                "custom_caption": row[5],
                "package": row[6],
                "version_name": row[7],
                "version_code": row[8],
                "size": row[9],
                "created_at": row[10],
                "status": row[11],
                "inspection_json": row[12],
                "flow_type": row[13],
                "url_key": row[14] or ""
            }
        except sqlite3.OperationalError:
            cursor.execute("""
                SELECT id, user_id, chat_id, file_path, filename, custom_caption, package, version_name, version_code, size, created_at, status, inspection_json, flow_type
                FROM pending_downloads
                WHERE id = ?
            """, (pending_id,))
            row = cursor.fetchone()
            if not row:
                return None
            ret = {
                "id": row[0],
                "user_id": row[1],
                "chat_id": row[2],
                "file_path": row[3],
                "filename": row[4],
                "custom_caption": row[5],
                "package": row[6],
                "version_name": row[7],
                "version_code": row[8],
                "size": row[9],
                "created_at": row[10],
                "status": row[11],
                "inspection_json": row[12],
                "flow_type": row[13],
                "url_key": ""
            }
        if not ret["url_key"] and ret["inspection_json"]:
            try:
                _ij = json.loads(ret["inspection_json"])
                if isinstance(_ij, dict) and _ij.get("url_key"):
                    ret["url_key"] = _ij["url_key"]
            except Exception:
                pass
        return ret
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def db_update_pending_status(pending_id: int, status: str):
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("UPDATE pending_downloads SET status = ? WHERE id = ?", (status, pending_id))
    conn.commit()
    conn.close()

def db_record_delivery(user_id: int, url_key: str, filename: str, total_size: int,
                       chat_id: int, message_ids: list[int],
                       package: str | None = None, version_code: int | None = None,
                       created_at: int | None = None) -> int:
    if not url_key or not message_ids or not user_id:
        return 0
    if created_at is None:
        created_at = int(time.time())
    msg_ids_json = json.dumps([int(m) for m in message_ids])
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM download_deliveries WHERE user_id = ? AND url_key = ?", (user_id, url_key))
        cursor.execute("""
            INSERT INTO download_deliveries (user_id, url_key, filename, total_size, chat_id, message_ids, package, version_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, url_key, filename, total_size, chat_id, msg_ids_json, package, version_code, created_at))
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()

def db_get_delivery(user_id: int, url_key: str) -> dict | None:
    if not user_id or not url_key:
        return None
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, user_id, url_key, filename, total_size, chat_id, message_ids, package, version_code, created_at
            FROM download_deliveries
            WHERE user_id = ? AND url_key = ?
            ORDER BY id DESC
            LIMIT 1
        """, (user_id, url_key))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            mids = json.loads(row[6])
        except Exception:
            mids = []
        return {
            "id": row[0],
            "user_id": row[1],
            "url_key": row[2],
            "filename": row[3],
            "total_size": row[4],
            "chat_id": row[5],
            "message_ids": mids,
            "package": row[7],
            "version_code": row[8],
            "created_at": row[9]
        }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def db_get_delivery_by_id(delivery_id: int) -> dict | None:
    if not delivery_id:
        return None
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, user_id, url_key, filename, total_size, chat_id, message_ids, package, version_code, created_at
            FROM download_deliveries
            WHERE id = ?
        """, (delivery_id,))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            mids = json.loads(row[6])
        except Exception:
            mids = []
        return {
            "id": row[0],
            "user_id": row[1],
            "url_key": row[2],
            "filename": row[3],
            "total_size": row[4],
            "chat_id": row[5],
            "message_ids": mids,
            "package": row[7],
            "version_code": row[8],
            "created_at": row[9]
        }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def db_delete_delivery(delivery_id: int):
    if not delivery_id:
        return
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM download_deliveries WHERE id = ?", (delivery_id,))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def db_get_apk_inspection(package: str, version_code: int) -> dict | None:
    return db_check_apk_duplicate(package, version_code)

def cleanup_expired_pending_downloads():
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cutoff = time.time() - (24 * 3600)
    try:
        cursor.execute("SELECT id, file_path FROM pending_downloads WHERE created_at < ? AND status IN ('pending', 'approved')", (cutoff,))
        rows = cursor.fetchall()
        for pid, fpath in rows:
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception as e:
                    logger.warning(f"Failed to delete expired pending file {fpath}: {e}")
            cursor.execute("UPDATE pending_downloads SET status = 'expired' WHERE id = ?", (pid,))
        conn.commit()
    except Exception as ex:
        logger.warning(f"Error cleaning expired pending downloads: {ex}")
    finally:
        conn.close()

def db_get_all_user_ids() -> list:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [r[0] for r in rows if r[0]]

def db_get_global_stats() -> dict:
    conn = sqlite3.connect(cfg.DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), SUM(size) FROM history")
    hist_row = cursor.fetchone()
    total_files = hist_row[0] or 0
    total_bytes = hist_row[1] or 0
    conn.close()
    return {"users": total_users, "files": total_files, "bytes": total_bytes}

init_db()
DASHBOARD_SECRET = get_or_create_dashboard_secret()
