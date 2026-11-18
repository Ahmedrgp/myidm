import asyncio
import ast
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from myidm import apk_inspect
from myidm import app
from myidm import config as cfg
from myidm import db
from myidm import texts

EXPECTED_TEXTS_SHA256 = "9e65688cf94b3e5094a23e8ad65060f89642aa3b422c802b200906acd4b2c23a"
EXPECTED_AR_SHA256 = "ab99b909b06e4a858e4d505bf551e30816b67432f3dfd5082b82406d91c65b8e"
EXPECTED_EN_SHA256 = "8c8c1742e468dd16bb631b03637ac1e45cd2d7685b8dff3657b0d7fad3f38d0b"

EXPECTED_TEXTS_KEYS = [
    "welcome", "god_panel", "probe_info", "settings_title",
    "btn_panel", "btn_history", "btn_settings", "btn_probe",
    "btn_stats", "btn_back", "btn_cancel", "btn_lang",
    "btn_mode_auto", "btn_mode_doc", "btn_threads",
    "btn_caption_on", "btn_caption_off", "btn_thumbs_on", "btn_thumbs_off",
    "btn_cleantags_on", "btn_cleantags_off",
    "transfer_rate", "processed_size", "eta",
    "downloading", "uploading", "torrent_connecting",
    "success_title", "file_name", "category", "final_size",
    "total_time", "avg_speed",
    "dup_warning_title", "dup_prev_header", "dup_prev_date", "dup_prev_hash",
    "dup_signer_match", "dup_signer_diff", "dup_prompt",
    "btn_dup_download", "btn_dup_cancel", "dup_cancelled_notice",
    "dup_approved_notice", "dup_expired_alert", "dup_already_done_alert",
    "dup_already_cancelled_alert", "dup_file_missing_alert",
    "disk_low_error", "help_text",
]

EXPECTED_BLITZVERIFY_OUTPUTS = {
    "full": (
        "```\n"
        "BLITZVERIFY v1\n"
        "package: org.supertuxkart.stk\n"
        "version_name: 1.5\n"
        "version_code: 328\n"
        "size_bytes: 183727403\n"
        "min_sdk: 21\n"
        "target_sdk: 35\n"
        "file_sha256: e1f2f49152abfb8f3ed0ced47981e84096758bff9758563aa3b917111a2a3cbd\n"
        "cert_sha256: 326b6dc20bfee3eda6bf25624e164a2a266e3f7a094d6fded99dda29da92f8bb\n"
        "inspected_at: 2024-10-27 06:33\n"
        "```"
    ),
    "partial": (
        "```\n"
        "BLITZVERIFY v1\n"
        "package: org.supertuxkart.stk\n"
        "version_name: 1.5\n"
        "version_code: 328\n"
        "size_bytes: 183727403\n"
        "min_sdk: 21\n"
        "file_sha256: e1f2f49152abfb8f3ed0ced47981e84096758bff9758563aa3b917111a2a3cbd\n"
        "inspected_at: 2024-10-27 06:33\n"
        "```"
    ),
    "bundle": (
        "```\n"
        "BLITZVERIFY v1\n"
        "package: com.game.bundle\n"
        "version_name: 2.0.1\n"
        "version_code: 201\n"
        "size_bytes: 500000000\n"
        "min_sdk: 26\n"
        "target_sdk: 34\n"
        "file_sha256: aaaaaaaa1111222233334444555566667777888899990000aaaabbbbccccdddd\n"
        "cert_sha256: bbbbbbbb1111222233334444555566667777888899990000aaaabbbbccccdddd\n"
        "inspected_at: 2024-10-27 06:33\n"
        "```"
    ),
    "degraded": (
        "```\n"
        "BLITZVERIFY v1\n"
        "package: com.degraded.app\n"
        "size_bytes: 12345\n"
        "file_sha256: abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890\n"
        "```"
    ),
    "empty": "",
    "none": "",
}

EXPECTED_EMITTED_CALLBACK_EXACT = {
    "btn_god_panel", "btn_history", "btn_settings", "btn_probe_info",
    "btn_stats", "btn_admin_panel", "toggle_lang", "toggle_mode",
    "toggle_threads", "toggle_caption", "toggle_thumbs", "toggle_cleantags",
    "btn_open_brand", "btn_start", "btn_brand_help", "toggle_brand_pos",
    "toggle_brand_btn", "btn_clear_brand",
}

EXPECTED_EMITTED_CALLBACK_PREFIXES = {
    "cancel_", "dup_go_", "dup_no_", "fwd_fresh_",
}

EXPECTED_HANDLED_CALLBACK_PATTERNS = (
    EXPECTED_EMITTED_CALLBACK_EXACT
    | EXPECTED_EMITTED_CALLBACK_PREFIXES
    | {"btn_help"}
)

EXPECTED_COMMANDS = {
    "start", "god", "godmode", "omnipotent", "probe", "settings", "lang",
    "help", "stats", "history", "broadcast", "set_prefix", "prefix",
    "clear_prefix", "cleanprefix", "set_suffix", "suffix", "clear_suffix",
    "cleansuffix", "replace", "replacements", "rules", "clear_replacements",
    "brand", "branding", "set_brand", "set_channel", "channel",
    "clear_brand", "clear_channel",
}

EXPECTED_BOT_MENU_COMMANDS = [
    "start", "omnipotent", "probe", "settings", "help", "history",
    "stats", "broadcast", "set_prefix", "set_suffix", "replace", "replacements",
]

EXPECTED_SCHEMA = {
    "apk_inspections": [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "user_id", "INTEGER", 0, None, 0),
        (2, "package", "TEXT", 0, None, 0),
        (3, "version_name", "TEXT", 0, None, 0),
        (4, "version_code", "INTEGER", 0, None, 0),
        (5, "file_sha256", "TEXT", 0, None, 0),
        (6, "cert_sha256", "TEXT", 0, None, 0),
        (7, "size", "INTEGER", 0, None, 0),
        (8, "filename", "TEXT", 0, None, 0),
        (9, "checked_at", "REAL", 0, None, 0),
        (10, "min_sdk", "INTEGER", 0, None, 0),
        (11, "target_sdk", "INTEGER", 0, None, 0),
    ],
    "bot_meta": [
        (0, "key", "TEXT", 0, None, 1),
        (1, "value", "TEXT", 0, None, 0),
    ],
    "custom_replacements": [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "user_id", "INTEGER", 0, None, 0),
        (2, "find_text", "TEXT", 0, None, 0),
        (3, "replace_text", "TEXT", 0, None, 0),
    ],
    "download_deliveries": [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "user_id", "INTEGER", 1, None, 0),
        (2, "url_key", "TEXT", 1, None, 0),
        (3, "filename", "TEXT", 0, None, 0),
        (4, "total_size", "INTEGER", 0, None, 0),
        (5, "chat_id", "INTEGER", 1, None, 0),
        (6, "message_ids", "TEXT", 1, None, 0),
        (7, "package", "TEXT", 0, None, 0),
        (8, "version_code", "INTEGER", 0, None, 0),
        (9, "created_at", "INTEGER", 1, None, 0),
    ],
    "global_stats": [
        (0, "key", "TEXT", 0, None, 1),
        (1, "val_num", "INTEGER", 0, "0", 0),
        (2, "val_float", "REAL", 0, "0.0", 0),
    ],
    "history": [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "user_id", "INTEGER", 0, None, 0),
        (2, "filename", "TEXT", 0, None, 0),
        (3, "size", "INTEGER", 0, None, 0),
        (4, "category", "TEXT", 0, "'📁 عام'", 0),
        (5, "timestamp", "REAL", 0, None, 0),
    ],
    "pending_downloads": [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "user_id", "INTEGER", 0, None, 0),
        (2, "chat_id", "INTEGER", 0, None, 0),
        (3, "file_path", "TEXT", 0, None, 0),
        (4, "filename", "TEXT", 0, None, 0),
        (5, "custom_caption", "TEXT", 0, None, 0),
        (6, "package", "TEXT", 0, None, 0),
        (7, "version_name", "TEXT", 0, None, 0),
        (8, "version_code", "INTEGER", 0, None, 0),
        (9, "size", "INTEGER", 0, None, 0),
        (10, "created_at", "REAL", 0, None, 0),
        (11, "status", "TEXT", 0, "'pending'", 0),
        (12, "inspection_json", "TEXT", 0, None, 0),
        (13, "flow_type", "TEXT", 0, "'direct'", 0),
        (14, "url_key", "TEXT", 0, "''", 0),
    ],
    "users": [
        (0, "user_id", "INTEGER", 0, None, 1),
        (1, "username", "TEXT", 0, None, 0),
        (2, "first_name", "TEXT", 0, None, 0),
        (3, "joined_at", "REAL", 0, None, 0),
        (4, "upload_mode", "TEXT", 0, "'auto'", 0),
        (5, "enable_thumbs", "INTEGER", 0, "1", 0),
        (6, "enable_caption", "INTEGER", 0, "1", 0),
        (7, "fast_speed", "INTEGER", 0, "1", 0),
        (8, "god_threads", "INTEGER", 0, "64", 0),
        (9, "lang", "TEXT", 0, "'ar'", 0),
        (10, "clean_tags", "INTEGER", 0, "1", 0),
        (11, "custom_prefix", "TEXT", 0, "''", 0),
        (12, "custom_suffix", "TEXT", 0, "''", 0),
        (13, "channel_tag", "TEXT", 0, "''", 0),
        (14, "brand_position", "TEXT", 0, "'suffix'", 0),
        (15, "channel_button", "INTEGER", 0, "1", 0),
    ],
}

MODULE_LAYER_RANKS = {
    "__init__": 0,
    "config": 1,
    "state": 2,
    "texts": 3,
    "db": 4,
    "utils": 5,
    "clients": 6,
    "keyboards": 7,
    "validation": 8,
    "dupguard": 9,
    "apk_inspect": 10,
    "resolvers": 11,
    "upload": 12,
    "downloads": 13,
    "fwdcache": 14,
    "commands": 15,
    "callbacks": 16,
    "intake": 17,
    "dashboard": 18,
    "app": 19,
}

BANNED_BY_VALUE_CONFIG_NAMES = {
    "DATA_DIR", "DB_FILE", "PENDING_DIR", "DOWNLOAD_DIR",
    "DISK_MIN_FREE_GB", "CURL_CFFI_AVAILABLE", "CurlAsyncSession",
    "PSUTIL_AVAILABLE", "TORRENTP_AVAILABLE", "ADMIN_IDS",
}


def _all_code_trees() -> list[tuple[Path, str, ast.Module]]:
    files = [ROOT_DIR / "bot.py"] + sorted((ROOT_DIR / "myidm").glob("*.py"))
    out = []
    for p in files:
        src = p.read_text(encoding="utf-8")
        out.append((p, src, ast.parse(src, filename=str(p))))
    return out


class TestContractParity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="myidm_contract_parity_")
        self.orig_data_dir = cfg.DATA_DIR
        self.orig_db_file = cfg.DB_FILE
        self.orig_pending_dir = cfg.PENDING_DIR

    def tearDown(self):
        cfg.DATA_DIR = self.orig_data_dir
        cfg.DB_FILE = self.orig_db_file
        cfg.PENDING_DIR = self.orig_pending_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_blitzverify_fixture_byte_equality(self):
        try:
            from myidm import apk_inspect as _ai
            fmt_fn = _ai.format_blitzverify_block
        except ImportError:
            fmt_fn = apk_inspect.format_blitzverify_block

        fixtures = {
            "full": {
                "package": "org.supertuxkart.stk",
                "version_name": "1.5",
                "version_code": 328,
                "size_bytes": 183727403,
                "min_sdk": 21,
                "target_sdk": 35,
                "file_sha256": "E1F2F49152ABFB8F3ED0CED47981E84096758BFF9758563AA3B917111A2A3CBD",
                "cert_sha256": "326B6DC20BFEE3EDA6BF25624E164A2A266E3F7A094D6FDED99DDA29DA92F8BB",
                "checked_at": 1730000000.0,
                "is_bundle": False,
            },
            "partial": {
                "package": "org.supertuxkart.stk",
                "version_name": "1.5",
                "version_code": 328,
                "size_bytes": 183727403,
                "min_sdk": 21,
                "target_sdk": None,
                "file_sha256": "E1F2F49152ABFB8F3ED0CED47981E84096758BFF9758563AA3B917111A2A3CBD",
                "cert_sha256": None,
                "checked_at": 1730000000.0,
            },
            "bundle": {
                "package": "com.game.bundle",
                "version_name": "2.0.1",
                "version_code": 201,
                "size_bytes": 500000000,
                "min_sdk": 26,
                "target_sdk": 34,
                "file_sha256": "AAAAAAAA1111222233334444555566667777888899990000AAAABBBBCCCCDDDD",
                "cert_sha256": "BBBBBBBB1111222233334444555566667777888899990000AAAABBBBCCCCDDDD",
                "is_bundle": True,
                "base_apk_entry_name": "base.apk",
                "base_apk_size": 25000000,
                "base_apk_sha256": "CCCCCCC1111222233334444555566667777888899990000AAAABBBBCCCCDDDD",
                "checked_at": 1730000000.0,
            },
            "degraded": {
                "package": "com.degraded.app",
                "version_name": "Unknown",
                "version_code": None,
                "size_bytes": 12345,
                "min_sdk": "-",
                "target_sdk": "N/A",
                "file_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "cert_sha256": None,
                "checked_at": None,
            },
            "empty": {},
            "none": None,
        }

        for name, inp in fixtures.items():
            actual = fmt_fn(inp)
            expected = EXPECTED_BLITZVERIFY_OUTPUTS[name]
            self.assertEqual(actual.encode("utf-8"), expected.encode("utf-8"), f"BLITZVERIFY byte drift on fixture '{name}'")

    def test_callback_data_set_equality(self):
        emitted_exact = set()
        emitted_prefixes = set()
        handled_patterns = set()

        for _, _, tree in _all_code_trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn_name = node.func.id if isinstance(node.func, ast.Name) else (
                        node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    )
                    if fn_name == "InlineKeyboardButton":
                        for kw in node.keywords:
                            if kw.arg == "callback_data":
                                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                    emitted_exact.add(kw.value.value)
                                elif isinstance(kw.value, ast.JoinedStr) and kw.value.values:
                                    first = kw.value.values[0]
                                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                                        emitted_prefixes.add(first.value)

                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "callback_handler":
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Compare) and len(sub.ops) == 1 and isinstance(sub.ops[0], ast.Eq):
                            if isinstance(sub.left, ast.Name) and sub.left.id == "data":
                                comp = sub.comparators[0]
                                if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                                    handled_patterns.add(comp.value)
                        elif (
                            isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and isinstance(sub.func.value, ast.Name)
                            and sub.func.value.id == "data"
                            and sub.func.attr == "startswith"
                            and sub.args
                            and isinstance(sub.args[0], ast.Constant)
                            and isinstance(sub.args[0].value, str)
                        ):
                            handled_patterns.add(sub.args[0].value)

        self.assertEqual(emitted_exact, EXPECTED_EMITTED_CALLBACK_EXACT)
        self.assertEqual(emitted_prefixes, EXPECTED_EMITTED_CALLBACK_PREFIXES)
        self.assertEqual(len(emitted_exact | emitted_prefixes), 22)
        self.assertEqual(handled_patterns, EXPECTED_HANDLED_CALLBACK_PATTERNS)

    def test_command_set_equality(self):
        found_commands = set()
        found_menu_commands = []

        for _, _, tree in _all_code_trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "command"
                        and node.args
                    ):
                        arg0 = node.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            found_commands.add(arg0.value)
                        elif isinstance(arg0, (ast.List, ast.Tuple)):
                            for elt in arg0.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    found_commands.add(elt.value)
                    elif (
                        (isinstance(node.func, ast.Name) and node.func.id == "BotCommand")
                        or (isinstance(node.func, ast.Attribute) and node.func.attr == "BotCommand")
                    ) and node.args:
                        arg0 = node.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            found_menu_commands.append(arg0.value)

        self.assertEqual(found_commands, EXPECTED_COMMANDS)
        self.assertEqual(found_menu_commands, EXPECTED_BOT_MENU_COMMANDS)

        try:
            from myidm import clients as _cl
            tg_bot = _cl.bot
        except ImportError:
            tg_bot = app.bot

        if not tg_bot.dispatcher.groups.get(0) and not tg_bot.loop.is_running():
            tg_bot.loop.run_until_complete(asyncio.sleep(0))

        group0 = tg_bot.dispatcher.groups.get(0, [])
        self.assertEqual(len(group0), 20)
        handler_names = [h.callback.__name__ for h in group0]
        self.assertIn("start_handler", handler_names)
        self.assertIn("handle_document_torrent", handler_names)
        self.assertIn("handle_all_messages", handler_names)
        idx_doc = handler_names.index("handle_document_torrent")
        idx_all = handler_names.index("handle_all_messages")
        cmd_indices = [
            i for i, nm in enumerate(handler_names)
            if nm not in ("callback_handler", "handle_document_torrent", "handle_all_messages")
        ]
        self.assertEqual(len(cmd_indices), 17)
        self.assertTrue(all(ci < idx_doc < idx_all for ci in cmd_indices))

    def test_texts_key_and_byte_equality(self):
        self.assertEqual(list(texts.TEXTS.keys()), ["ar", "en"])
        self.assertEqual(list(texts.TEXTS["ar"].keys()), EXPECTED_TEXTS_KEYS)
        self.assertEqual(list(texts.TEXTS["en"].keys()), EXPECTED_TEXTS_KEYS)

        ar_digest = hashlib.sha256(
            json.dumps(texts.TEXTS["ar"], ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        en_digest = hashlib.sha256(
            json.dumps(texts.TEXTS["en"], ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        full_digest = hashlib.sha256(
            json.dumps(texts.TEXTS, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        self.assertEqual(ar_digest, EXPECTED_AR_SHA256)
        self.assertEqual(en_digest, EXPECTED_EN_SHA256)
        self.assertEqual(full_digest, EXPECTED_TEXTS_SHA256)

    def test_fresh_and_legacy_migrated_schema_equality(self):
        # 1. Fresh database schema check
        fresh_db = os.path.join(self.tmp_dir, "fresh.db")
        cfg.DB_FILE = fresh_db
        db.init_db()

        conn = sqlite3.connect(fresh_db)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode")
        self.assertEqual(cur.fetchone()[0].lower(), "wal")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        self.assertEqual(tables, sorted(EXPECTED_SCHEMA.keys()))

        for tbl in tables:
            cur.execute(f"PRAGMA table_info({tbl})")
            cols = cur.fetchall()
            self.assertEqual(cols, EXPECTED_SCHEMA[tbl], f"Schema mismatch on fresh table '{tbl}'")

        cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        indexes = cur.fetchall()
        self.assertEqual(
            indexes,
            [("idx_deliveries_user_url", "download_deliveries", "CREATE INDEX idx_deliveries_user_url ON download_deliveries(user_id, url_key)")],
        )
        conn.close()

        # 2. Legacy pre-migration database compatibility and idempotency check
        legacy_db = os.path.join(self.tmp_dir, "legacy.db")
        lconn = sqlite3.connect(legacy_db)
        lcur = lconn.cursor()
        lcur.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at REAL,
                upload_mode TEXT DEFAULT 'auto',
                enable_thumbs INTEGER DEFAULT 1,
                enable_caption INTEGER DEFAULT 1,
                fast_speed INTEGER DEFAULT 1
            )
        """)
        lcur.execute("""
            CREATE TABLE history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT,
                size INTEGER,
                timestamp REAL
            )
        """)
        lcur.execute("""
            CREATE TABLE pending_downloads (
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
        lcur.execute("""
            CREATE TABLE apk_inspections (
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
        lcur.execute("INSERT INTO users (user_id, username, first_name, joined_at) VALUES (1594244556, 'owner', 'TM', 1700000000.0)")
        lconn.commit()
        lconn.close()

        cfg.DB_FILE = legacy_db
        db.init_db()
        db.init_db()  # second run must be an idempotent no-op

        mconn = sqlite3.connect(legacy_db)
        mcur = mconn.cursor()
        for tbl in sorted(EXPECTED_SCHEMA.keys()):
            mcur.execute(f"PRAGMA table_info({tbl})")
            actual_cols_by_name = {c[1]: c[1:] for c in mcur.fetchall()}
            expected_cols_by_name = {c[1]: c[1:] for c in EXPECTED_SCHEMA[tbl]}
            self.assertEqual(actual_cols_by_name, expected_cols_by_name, f"Migrated schema mismatch on table '{tbl}'")
        mconn.close()

        st = db.db_get_user_settings(1594244556)
        self.assertEqual(st["god_threads"], 64)
        self.assertEqual(st["lang"], "ar")
        self.assertEqual(st["brand_position"], "suffix")

        # 3. Verify all sqlite3.connect call sites are centralized in myidm/db.py reading cfg.DB_FILE
        db_connect_sites = 0
        for path, _, tree in _all_code_trees():
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "sqlite3"
                    and node.func.attr == "connect"
                ):
                    self.assertEqual(path.name, "db.py", f"Un-centralized sqlite3.connect in {path}")
                    self.assertTrue(
                        node.args
                        and isinstance(node.args[0], ast.Attribute)
                        and isinstance(node.args[0].value, ast.Name)
                        and node.args[0].value.id == "cfg"
                        and node.args[0].attr == "DB_FILE",
                        f"sqlite3.connect at {path}:{node.lineno} does not pass cfg.DB_FILE dynamically",
                    )
                    db_connect_sites += 1
        self.assertEqual(db_connect_sites, 24)

    def test_ast_dag_and_no_by_value_config_imports(self):
        pkg_dir = ROOT_DIR / "myidm"
        pkg_files = sorted(pkg_dir.glob("*.py"))
        self.assertGreaterEqual(len(pkg_files), 6)

        edges: dict[str, set[str]] = {}

        for p in pkg_files:
            mod_name = p.stem
            self.assertIn(mod_name, MODULE_LAYER_RANKS, f"Unranked module in myidm/: {p.name}")
            src = p.read_text(encoding="utf-8")
            self.assertNotIn("\u2013", src, f"En dash found in {p.name}")
            self.assertNotIn("\u2014", src, f"Em dash found in {p.name}")

            tree = ast.parse(src, filename=str(p))
            deps: set[str] = set()
            if mod_name != "__init__":
                deps.add("__init__")

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name, "bot", f"myidm/{p.name} must never import bot")
                        self.assertFalse(alias.name.startswith("bot."), f"myidm/{p.name} must never import bot.*")
                        if alias.name == "myidm":
                            if mod_name != "__init__":
                                deps.add("__init__")
                        elif alias.name.startswith("myidm."):
                            target = alias.name.split(".")[1]
                            deps.add(target)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    self.assertNotEqual(mod, "bot", f"myidm/{p.name} must never import from bot")
                    self.assertFalse(mod.startswith("bot."), f"myidm/{p.name} must never import from bot.*")
                    if mod == "myidm":
                        for alias in node.names:
                            if (pkg_dir / f"{alias.name}.py").exists():
                                deps.add(alias.name)
                            elif mod_name != "__init__":
                                deps.add("__init__")
                    elif mod.startswith("myidm."):
                        sub = mod.split(".", 1)[1]
                        deps.add(sub)
                        if sub == "config":
                            for alias in node.names:
                                self.assertNotIn(
                                    alias.name,
                                    BANNED_BY_VALUE_CONFIG_NAMES,
                                    f"Banned by-value config import 'from myidm.config import {alias.name}' in {p.name}:{node.lineno}",
                                )

            edges[mod_name] = deps
            for dep in deps:
                self.assertIn(dep, MODULE_LAYER_RANKS, f"Unknown internal dependency '{dep}' in {p.name}")
                self.assertGreater(
                    MODULE_LAYER_RANKS[mod_name],
                    MODULE_LAYER_RANKS[dep],
                    f"DAG layer violation: myidm.{mod_name} (rank {MODULE_LAYER_RANKS[mod_name]}) imports myidm.{dep} (rank {MODULE_LAYER_RANKS[dep]})",
                )

        # Also check bot.py does not import mutable config paths by value from myidm.config
        bot_src = (ROOT_DIR / "bot.py").read_text(encoding="utf-8")
        bot_tree = ast.parse(bot_src, filename="bot.py")
        for node in ast.walk(bot_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "myidm.config":
                for alias in node.names:
                    self.assertNotIn(
                        alias.name,
                        BANNED_BY_VALUE_CONFIG_NAMES,
                        f"Banned by-value config import in bot.py:{node.lineno}: {alias.name}",
                    )

        # Explicit DFS cycle check
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(n: str):
            self.assertNotIn(n, visiting, f"Cycle detected involving myidm.{n}")
            if n in visited:
                return
            visiting.add(n)
            for nxt in edges.get(n, ()):
                dfs(nxt)
            visiting.remove(n)
            visited.add(n)

        for m in edges:
            dfs(m)


if __name__ == "__main__":
    unittest.main()
