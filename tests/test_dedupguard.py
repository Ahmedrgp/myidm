import os
import sys
import time
import json
import shutil
import sqlite3
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestDedupGuard(unittest.TestCase):
    def setUp(self):
        # Set up a clean test directory
        self.test_data_dir = os.path.abspath("test_data_dedupguard")
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir, ignore_errors=True)
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        self.orig_data_dir = bot.DATA_DIR
        self.orig_db_file = bot.DB_FILE
        self.orig_pending_dir = bot.PENDING_DIR
        
        bot.DATA_DIR = self.test_data_dir
        bot.DB_FILE = os.path.join(self.test_data_dir, "bot_database.db")
        bot.PENDING_DIR = os.path.join(self.test_data_dir, "pending_downloads")
        os.makedirs(bot.PENDING_DIR, exist_ok=True)
        
        bot.init_db()

    def tearDown(self):
        bot.DATA_DIR = self.orig_data_dir
        bot.DB_FILE = self.orig_db_file
        bot.PENDING_DIR = self.orig_pending_dir
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # TASK 0: Data Persistence Verification
    # -------------------------------------------------------------
    def test_task0_data_persistence_config(self):
        self.assertTrue(os.path.exists(bot.DATA_DIR))
        self.assertTrue(os.path.exists(bot.PENDING_DIR))
        self.assertTrue(os.path.exists(bot.DB_FILE))
        
        # Verify Pyrogram client workdir
        self.assertEqual(str(bot.bot.workdir), str(self.orig_data_dir))
        if bot.user_bot:
            self.assertEqual(str(bot.user_bot.workdir), str(self.orig_data_dir))
            
        # Verify required tables in SQLite
        conn = sqlite3.connect(bot.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        self.assertIn("users", tables)
        self.assertIn("history", tables)
        self.assertIn("bot_meta", tables)
        self.assertIn("apk_inspections", tables)
        self.assertIn("pending_downloads", tables)

    # -------------------------------------------------------------
    # TASK 1: Duplicate Detection (AND condition: package + version_code)
    # -------------------------------------------------------------
    def test_task1_and_condition_duplicate_check(self):
        # 1. No record in DB -> NOT duplicate
        self.assertIsNone(bot.db_check_apk_duplicate("com.example.test", 100))
        
        # 2. Add an inspection record
        bot.db_add_apk_inspection(
            user_id=123,
            package="com.example.test",
            version_name="1.0.0",
            version_code=100,
            file_sha256="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            cert_sha256="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            size=50000,
            filename="test_100.apk"
        )
        
        # 3. Exactly same package AND same version_code -> MATCH
        dup = bot.db_check_apk_duplicate("com.example.test", 100)
        self.assertIsNotNone(dup)
        self.assertEqual(dup["package"], "com.example.test")
        self.assertEqual(dup["version_code"], 100)
        
        # 4. Same package, DIFFERENT version_code -> NO MATCH
        self.assertIsNone(bot.db_check_apk_duplicate("com.example.test", 101))
        
        # 5. Different package, SAME version_code -> NO MATCH
        self.assertIsNone(bot.db_check_apk_duplicate("com.example.other", 100))
        
        # 6. Degraded (missing package or version_code) -> NO MATCH
        self.assertIsNone(bot.db_check_apk_duplicate(None, 100))
        self.assertIsNone(bot.db_check_apk_duplicate("com.example.test", None))

    def test_task1_pending_download_lifecycle(self):
        # Create a dummy pending file
        pending_file = os.path.join(bot.PENDING_DIR, "pending_test.apk")
        with open(pending_file, "wb") as f:
            f.write(b"PK\x03\x04test_apk_content")
            
        pid = bot.db_add_pending_download(
            user_id=12345,
            chat_id=12345,
            file_path=pending_file,
            filename="pending_test.apk",
            custom_caption="test caption",
            package="com.test.app",
            version_name="2.1",
            version_code=210,
            size=len(b"PK\x03\x04test_apk_content"),
            status="pending",
            inspection_json=json.dumps({"package": "com.test.app", "version_code": 210}),
            flow_type="direct"
        )
        
        # Verify retrieval
        row = bot.db_get_pending_download(pid)
        self.assertIsNotNone(row)
        self.assertEqual(row["package"], "com.test.app")
        self.assertEqual(row["version_code"], 210)
        self.assertEqual(row["status"], "pending")
        
        # Update status
        bot.db_update_pending_status(pid, "approved")
        row_approved = bot.db_get_pending_download(pid)
        self.assertEqual(row_approved["status"], "approved")

    def test_task1_24h_expiry_cleaner(self):
        old_file = os.path.join(bot.PENDING_DIR, "old_expired.apk")
        with open(old_file, "wb") as f:
            f.write(b"expired")
            
        pid = bot.db_add_pending_download(
            user_id=12345,
            chat_id=12345,
            file_path=old_file,
            filename="old_expired.apk",
            custom_caption="",
            package="com.old.app",
            version_name="1.0",
            version_code=10,
            size=7,
            status="pending"
        )
        # Manually backdate created_at to 25 hours ago
        conn = sqlite3.connect(bot.DB_FILE)
        conn.cursor().execute("UPDATE pending_downloads SET created_at = ? WHERE id = ?", (time.time() - 90000, pid))
        conn.commit()
        conn.close()
        
        # Run cleaner
        bot.cleanup_expired_pending_downloads()
        
        # Assert file was removed and status became expired
        self.assertFalse(os.path.exists(old_file))
        row = bot.db_get_pending_download(pid)
        self.assertEqual(row["status"], "expired")

    def test_task1_duplicate_warning_card_and_keyboard(self):
        info = {
            "package": "com.duplicate.app",
            "version_name": "3.0.0",
            "version_code": 300,
            "size_bytes": 1048576,
            "cert_sha256": "11223344556677889900AABBCCDDEEFF11223344556677889900AABBCCDDEEFF"
        }
        prev = {
            "package": "com.duplicate.app",
            "version_name": "3.0.0",
            "version_code": 300,
            "file_sha256": "FEDCBA9876543210FEDCBA9876543210FEDCBA9876543210FEDCBA9876543210",
            "cert_sha256": "11223344556677889900AABBCCDDEEFF11223344556677889900AABBCCDDEEFF",
            "checked_at": time.time() - 3600
        }
        
        # Arabic card
        card_ar = bot.format_duplicate_warning_card(info, prev, lang="ar")
        self.assertIn("تنبيه: تم تنزيل هذا التطبيق مسبقاً بنفس الإصدار!", card_ar)
        self.assertIn("com.duplicate.app", card_ar)
        self.assertIn("3.0.0 (300)", card_ar)
        self.assertIn("نفس شهادة التوقيع الأصلية", card_ar)
        self.assertIn("FEDCBA987654...", card_ar)
        
        # English card
        card_en = bot.format_duplicate_warning_card(info, prev, lang="en")
        self.assertIn("Warning: Duplicate APK Download Detected!", card_en)
        self.assertIn("com.duplicate.app", card_en)
        self.assertIn("Same original signing certificate", card_en)
        
        # Keyboard buttons
        kb = bot.make_duplicate_keyboard(42, lang="ar")
        buttons = kb.inline_keyboard[0]
        self.assertEqual(buttons[0].callback_data, "dup_go_42")
        self.assertEqual(buttons[1].callback_data, "dup_no_42")
        self.assertEqual(buttons[0].text, "✅ نزّله تاني")
        self.assertEqual(buttons[1].text, "🛑 إلغاء")

    # -------------------------------------------------------------
    # TASK 2: Disk Guard
    # -------------------------------------------------------------
    def test_task2_check_disk_space_rules(self):
        reserve = int(bot.DISK_MIN_FREE_GB * (1024 ** 3))
        
        # Rule 1: Known size -> free >= needed * 1.25 + reserve
        with patch("shutil.disk_usage") as mock_usage:
            # Case A: Free space is plenty
            mock_usage.return_value = MagicMock(free=int(100 * 1024 * 1024 * 1.25 + reserve + 1000), total=10**11)
            ok, needed, free, res = bot.check_disk_space(bot.DOWNLOAD_DIR, 100 * 1024 * 1024)
            self.assertTrue(ok)
            
            # Case B: Free space is insufficient
            mock_usage.return_value = MagicMock(free=int(100 * 1024 * 1024 * 1.25 + reserve - 1000), total=10**11)
            ok, needed, free, res = bot.check_disk_space(bot.DOWNLOAD_DIR, 100 * 1024 * 1024)
            self.assertFalse(ok)
            
            # Rule 2: Unknown size -> free >= reserve * 2
            mock_usage.return_value = MagicMock(free=int(reserve * 2 + 1000), total=10**11)
            ok, needed, free, res = bot.check_disk_space(bot.DOWNLOAD_DIR, None)
            self.assertTrue(ok)
            
            mock_usage.return_value = MagicMock(free=int(reserve * 2 - 1000), total=10**11)
            ok, needed, free, res = bot.check_disk_space(bot.DOWNLOAD_DIR, 0)
            self.assertFalse(ok)
            
            # Rule 3: Splitting check -> free >= piece_size + reserve
            piece_size = 1900 * 1024 * 1024
            mock_usage.return_value = MagicMock(free=piece_size + reserve + 500, total=10**11)
            ok, psize, free, res = bot.check_disk_space_for_split(bot.DOWNLOAD_DIR, piece_size)
            self.assertTrue(ok)
            
            mock_usage.return_value = MagicMock(free=piece_size + reserve - 500, total=10**11)
            ok, psize, free, res = bot.check_disk_space_for_split(bot.DOWNLOAD_DIR, piece_size)
            self.assertFalse(ok)

    def test_task2_cleanup_temp_dir_retention(self):
        temp_dir = bot.DOWNLOAD_DIR
        os.makedirs(temp_dir, exist_ok=True)
        
        file_fresh = os.path.join(temp_dir, "fresh_file.tmp")
        file_old = os.path.join(temp_dir, "orphan_7h.tmp")
        
        with open(file_fresh, "w") as f:
            f.write("fresh")
        with open(file_old, "w") as f:
            f.write("old")
            
        now = time.time()
        # Set file_old mtime to 7 hours ago
        os.utime(file_old, (now - 7 * 3600, now - 7 * 3600))
        # Set file_fresh mtime to 1 hour ago
        os.utime(file_fresh, (now - 1 * 3600, now - 1 * 3600))
        
        # Pending file inside PENDING_DIR must NEVER be touched
        pending_protected = os.path.join(bot.PENDING_DIR, "protected.apk")
        with open(pending_protected, "w") as f:
            f.write("protected")
        os.utime(pending_protected, (now - 10 * 3600, now - 10 * 3600))
        
        bot.cleanup_temp_dir(max_age_hours=6.0)
        
        # Assert orphan > 6h deleted, fresh preserved, pending untouched
        self.assertFalse(os.path.exists(file_old))
        self.assertTrue(os.path.exists(file_fresh))
        self.assertTrue(os.path.exists(pending_protected))
        
        # Cleanup
        if os.path.exists(file_fresh):
            os.remove(file_fresh)
        if os.path.exists(pending_protected):
            os.remove(pending_protected)

    # -------------------------------------------------------------
    # TASK 3: Security Mini-Pack Verification
    # -------------------------------------------------------------
    def test_task3_zero_eval_in_bot(self):
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("eval(", content)
        self.assertNotIn("/eval", content)

    def test_task3_dashboard_secret_persistence(self):
        # When DASHBOARD_SECRET env var is not set, secret comes from bot_meta in DB
        secret1 = bot.get_or_create_dashboard_secret()
        self.assertGreaterEqual(len(secret1), 24)
        
        # Query DB directly
        conn = sqlite3.connect(bot.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_meta WHERE key = 'dashboard_secret'")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], secret1)
        
        # Subsequent call returns the SAME secret
        secret2 = bot.get_or_create_dashboard_secret()
        self.assertEqual(secret1, secret2)

    def test_task3_requirements_pinned(self):
        with open("requirements.txt", "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        for line in lines:
            self.assertIn("==", line, f"Requirement line not pinned to exact version: {line}")
            self.assertFalse(line.startswith(">="))

    def test_task3_test_echo_deleted(self):
        self.assertFalse(os.path.exists("test_echo.py"))

    # -------------------------------------------------------------
    # TASK 4: Bundle Labeling and Signer Comparison
    # -------------------------------------------------------------
    def test_task4_bundle_labeling_in_cards(self):
        bundle_info = {
            "is_bundle": True,
            "bundle_rule_en": "base APK (base.apk)",
            "bundle_rule_ar": "ملف الحزمة الأساسي (base.apk)",
            "package": "com.game.bundle",
            "version_name": "4.5.1",
            "version_code": 451,
            "size_bytes": 104857600, # 100 MB bundle
            "file_sha256": "BUNDLE_SHA256_HASH_1234567890",
            "base_apk_entry_name": "base.apk",
            "base_apk_size": 83886080, # 80 MB base APK
            "base_apk_sha256": "BASE_APK_SHA256_HASH_0987654321",
            "cert_sha256": "CERT_HASH_1111",
            "subject_dn": "CN=GameDev",
            "min_sdk": 21,
            "target_sdk": 34,
            "checked_at": time.time()
        }
        
        # Test English Bundle Card
        card_en = bot.format_apk_inspection_card(bundle_info, prev=None, lang="en")
        self.assertIn("Delivered Bundle Size:", card_en)
        self.assertIn("Delivered Bundle SHA-256:", card_en)
        self.assertIn("BUNDLE_SHA256_HASH_1234567890", card_en)
        self.assertIn("Base APK Entry: <code>base.apk</code>", card_en)
        self.assertIn("Base APK Size:", card_en)
        self.assertIn("Base APK SHA-256:", card_en)
        self.assertIn("BASE_APK_SHA256_HASH_0987654321", card_en)
        
        # Test Arabic Bundle Card
        card_ar = bot.format_apk_inspection_card(bundle_info, prev=None, lang="ar")
        self.assertIn("حجم الحزمة (Bundle):", card_ar)
        self.assertIn("بصمة الحزمة SHA-256:", card_ar)
        self.assertIn("ملف APK الأساسي: <code>base.apk</code>", card_ar)
        self.assertIn("حجم APK الأساسي:", card_ar)
        self.assertIn("بصمة APK الأساسي SHA-256:", card_ar)

    def test_task4_signer_comparison_different_version_only(self):
        pkg = "com.signer.test"
        
        # Initial version 1.0 (vcode 10)
        bot.db_add_apk_inspection(1, pkg, "1.0", 10, "HASH1", "CERT_ORIGINAL", 1000, "v1.apk")
        
        # Previous inspection for vcode 10 -> None (because exclude_version_code=10)
        prev = bot.db_get_last_inspection_for_package(pkg, exclude_latest=True, exclude_version_code=10)
        self.assertIsNone(prev)
        
        # Re-downloading the SAME version 1.0 (vcode 10) approved -> records second inspection with vcode 10
        bot.db_add_apk_inspection(1, pkg, "1.0", 10, "HASH1", "CERT_ORIGINAL", 1000, "v1_copy.apk")
        prev = bot.db_get_last_inspection_for_package(pkg, exclude_latest=True, exclude_version_code=10)
        # MUST still be None because no other version_code exists!
        self.assertIsNone(prev)
        
        # Now a new release 1.1 (vcode 11) with SAME cert
        prev = bot.db_get_last_inspection_for_package(pkg, exclude_latest=True, exclude_version_code=11)
        self.assertIsNotNone(prev)
        self.assertEqual(prev["version_code"], 10)
        self.assertEqual(prev["cert_sha256"], "CERT_ORIGINAL")
        
        # Now record version 1.1
        bot.db_add_apk_inspection(1, pkg, "1.1", 11, "HASH2", "CERT_ORIGINAL", 1050, "v1_1.apk")
        
        # Now release 2.0 (vcode 20) with CHANGED cert
        prev = bot.db_get_last_inspection_for_package(pkg, exclude_latest=True, exclude_version_code=20)
        self.assertIsNotNone(prev)
        self.assertEqual(prev["version_code"], 11) # latest was v1.1
        self.assertEqual(prev["cert_sha256"], "CERT_ORIGINAL")

if __name__ == "__main__":
    unittest.main()
