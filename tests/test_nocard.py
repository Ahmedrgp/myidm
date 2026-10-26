import os
import sys
import unittest
import asyncio
import sqlite3
import time
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pyrogram.enums import ParseMode

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestNoCardInspection(unittest.TestCase):
    def setUp(self):
        self.apk_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests_apk"))
        self.golden_v1 = os.path.join(self.apk_dir, "golden_v1.apk")
        self.test_pkg = f"com.nocard.test_{int(time.time() * 1000)}"

    def test_format_signer_change_warning_unit(self):
        cert_A = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        cert_B = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

        # 1. Either is None
        self.assertIsNone(bot.format_signer_change_warning(None, None))
        self.assertIsNone(bot.format_signer_change_warning({"package": "a"}, None))
        self.assertIsNone(bot.format_signer_change_warning(None, {"package": "a"}))

        # 2. Cert missing in either
        info_no_cert = {"package": "a", "version_code": 2, "cert_sha256": None}
        prev_has_cert = {"package": "a", "version_code": 1, "cert_sha256": cert_A}
        self.assertIsNone(bot.format_signer_change_warning(info_no_cert, prev_has_cert))

        info_has_cert = {"package": "a", "version_code": 2, "cert_sha256": cert_A}
        prev_no_cert = {"package": "a", "version_code": 1, "cert_sha256": None}
        self.assertIsNone(bot.format_signer_change_warning(info_has_cert, prev_no_cert))

        # 3. Same cert (case-insensitive)
        prev_cert_A = {"package": "com.test", "version_code": 10, "cert_sha256": cert_A}
        info_same_cert = {"package": "com.test", "version_code": 11, "cert_sha256": cert_A.lower()}
        self.assertIsNone(bot.format_signer_change_warning(info_same_cert, prev_cert_A))

        # 4. Different cert -> Generates warning
        info_diff_cert = {"package": "com.test", "version_code": 12, "cert_sha256": cert_B}
        warn = bot.format_signer_change_warning(info_diff_cert, prev_cert_A)
        self.assertIsNotNone(warn)
        self.assertIn("⚠️ تنبيه: توقيع النسخة دي مختلف عن النسخة اللي فاتت من نفس التطبيق", warn)
        self.assertIn("Warning: this version is signed differently from the previous version of this app", warn)
        self.assertIn("com.test", warn)
        self.assertIn("10 → 12", warn)

    def test_fresh_apk_emits_blitzverify_block_only(self):
        async def run_test():
            user_msg = MagicMock()
            replies = []
            parse_modes = []

            async def reply_mock(text, parse_mode=None, **kwargs):
                replies.append(text)
                parse_modes.append(parse_mode)
                return AsyncMock()

            user_msg.reply_text = AsyncMock(side_effect=reply_mock)

            # Use a completely fresh package name
            fresh_pkg = f"com.fresh.apk_{int(time.time() * 1000)}"
            mock_info = {
                "package": fresh_pkg,
                "version_name": "1.0",
                "version_code": 100,
                "size_bytes": 10240,
                "min_sdk": 21,
                "target_sdk": 34,
                "file_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "cert_sha256": "1122334455667788990011223344556677889900112233445566778899001122",
                "checked_at": time.time()
            }

            await bot.handle_apk_inspection_card(
                file_path=self.golden_v1,
                filename="fresh_app.apk",
                user_id=99901,
                user_msg=user_msg,
                lang="ar",
                precomputed_info=mock_info
            )

            # Assert on reply sequence: exactly 1 reply (BLITZVERIFY block ONLY)
            self.assertEqual(len(replies), 1, f"Expected 1 reply, got {len(replies)}: {replies}")
            self.assertEqual(parse_modes[0], ParseMode.MARKDOWN)
            self.assertTrue(replies[0].startswith("```\n"))
            self.assertTrue(replies[0].endswith("\n```"))
            self.assertIn("BLITZVERIFY v1", replies[0])
            self.assertIn(f"package: {fresh_pkg}", replies[0])
            self.assertIn("version_code: 100", replies[0])

            # Ensure NO card and NO signer warning in replies
            self.assertFalse(any("بطاقة فحص APK" in r for r in replies))
            self.assertFalse(any("تنبيه: توقيع النسخة دي مختلف" in r for r in replies))

        asyncio.run(run_test())

    def test_signer_same_apk_emits_block_only_no_warning(self):
        async def run_test():
            cert_same = "EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
            pkg = f"com.same.signer_{int(time.time() * 1000)}"

            # Insert previous inspection v1 with cert_same
            bot.db_add_apk_inspection(
                user_id=99902,
                package=pkg,
                version_name="1.0",
                version_code=1,
                file_sha256="FSHA1",
                cert_sha256=cert_same,
                size=5000,
                filename="app_v1.apk"
            )

            user_msg = MagicMock()
            replies = []
            parse_modes = []

            async def reply_mock(text, parse_mode=None, **kwargs):
                replies.append(text)
                parse_modes.append(parse_mode)
                return AsyncMock()

            user_msg.reply_text = AsyncMock(side_effect=reply_mock)

            # Second inspection v2 with SAME cert
            mock_info_v2 = {
                "package": pkg,
                "version_name": "1.1",
                "version_code": 2,
                "size_bytes": 5200,
                "min_sdk": 21,
                "target_sdk": 34,
                "file_sha256": "FSHA2",
                "cert_sha256": cert_same,
                "checked_at": time.time()
            }

            await bot.handle_apk_inspection_card(
                file_path=self.golden_v1,
                filename="app_v2.apk",
                user_id=99902,
                user_msg=user_msg,
                lang="ar",
                precomputed_info=mock_info_v2
            )

            # Assert on reply sequence: exactly 1 reply (BLITZVERIFY block ONLY, no warning, no card)
            self.assertEqual(len(replies), 1)
            self.assertEqual(parse_modes[0], ParseMode.MARKDOWN)
            self.assertIn("BLITZVERIFY v1", replies[0])
            self.assertIn(f"package: {pkg}", replies[0])
            self.assertIn("version_code: 2", replies[0])
            self.assertFalse(any("بطاقة فحص APK" in r for r in replies))
            self.assertFalse(any("تنبيه: توقيع النسخة دي مختلف" in r for r in replies))

        asyncio.run(run_test())

    def test_signer_changed_apk_emits_warning_then_block(self):
        async def run_test():
            cert_orig = "1111111111111111111111111111111111111111111111111111111111111111"
            cert_new = "2222222222222222222222222222222222222222222222222222222222222222"
            pkg = f"com.diff.signer_{int(time.time() * 1000)}"

            # Insert previous inspection v1 with cert_orig
            bot.db_add_apk_inspection(
                user_id=99903,
                package=pkg,
                version_name="1.0",
                version_code=10,
                file_sha256="FSHA_OLD",
                cert_sha256=cert_orig,
                size=8000,
                filename="app_v10.apk"
            )

            user_msg = MagicMock()
            replies = []
            parse_modes = []

            async def reply_mock(text, parse_mode=None, **kwargs):
                replies.append(text)
                parse_modes.append(parse_mode)
                return AsyncMock()

            user_msg.reply_text = AsyncMock(side_effect=reply_mock)

            # Second inspection v20 with DIFFERENT cert_new
            mock_info_v2 = {
                "package": pkg,
                "version_name": "2.0",
                "version_code": 20,
                "size_bytes": 9000,
                "min_sdk": 21,
                "target_sdk": 34,
                "file_sha256": "FSHA_NEW",
                "cert_sha256": cert_new,
                "checked_at": time.time()
            }

            await bot.handle_apk_inspection_card(
                file_path=self.golden_v1,
                filename="app_v20.apk",
                user_id=99903,
                user_msg=user_msg,
                lang="ar",
                precomputed_info=mock_info_v2
            )

            # Assert reply sequence: exactly 2 replies: warning line THEN BLITZVERIFY block
            self.assertEqual(len(replies), 2, f"Expected 2 replies, got {len(replies)}: {replies}")

            # Message 1: plain signer warning
            self.assertIn("⚠️ تنبيه: توقيع النسخة دي مختلف عن النسخة اللي فاتت من نفس التطبيق", replies[0])
            self.assertIn("Warning: this version is signed differently from the previous version of this app", replies[0])
            self.assertIn(pkg, replies[0])
            self.assertIn("10 → 20", replies[0])
            self.assertEqual(parse_modes[0], ParseMode.DISABLED)

            # Message 2: BLITZVERIFY code block (MARKDOWN)
            self.assertTrue(replies[1].startswith("```\n"))
            self.assertTrue(replies[1].endswith("\n```"))
            self.assertIn("BLITZVERIFY v1", replies[1])
            self.assertIn(f"package: {pkg}", replies[1])
            self.assertIn("version_code: 20", replies[1])
            self.assertEqual(parse_modes[1], ParseMode.MARKDOWN)

            # Ensure NO card in either reply
            self.assertFalse(any("بطاقة فحص APK" in r for r in replies))

        asyncio.run(run_test())

    def test_non_apk_delivery_no_inspection_messages(self):
        async def run_test():
            user_msg = MagicMock()
            user_msg.reply_text = AsyncMock()

            non_apk_file = os.path.join(self.apk_dir, "non_apk.zip")
            await bot.handle_apk_inspection_card(
                file_path=non_apk_file,
                filename="archive.zip",
                user_id=99904,
                user_msg=user_msg,
                lang="ar"
            )

            user_msg.reply_text.assert_not_called()

        asyncio.run(run_test())

    def test_duplicate_flow_paused_then_approved(self):
        async def run_test():
            pkg = f"com.dup.flow_{int(time.time() * 1000)}"
            vcode = 42
            cert = "4444444444444444444444444444444444444444444444444444444444444444"

            # Pre-populate DB with an inspection
            bot.db_add_apk_inspection(
                user_id=99905,
                package=pkg,
                version_name="1.0",
                version_code=vcode,
                file_sha256="DUP_FILE_SHA",
                cert_sha256=cert,
                size=12345,
                filename="dup_app.apk"
            )

            # Check duplicate detection
            dup = bot.db_check_apk_duplicate(pkg, vcode)
            self.assertIsNotNone(dup)
            self.assertEqual(dup["package"], pkg)
            self.assertEqual(dup["version_code"], vcode)

            # Now test approved pending upload flow
            # Create a temporary file copy so original is preserved
            with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
                temp_path = tmp.name
            shutil.copyfile(self.golden_v1, temp_path)

            try:
                pid = bot.db_add_pending_download(
                    user_id=99905,
                    chat_id=1234567,
                    file_path=temp_path,
                    filename="dup_app.apk",
                    custom_caption="",
                    package=pkg,
                    version_name="1.0",
                    version_code=vcode,
                    size=12345,
                    status="pending",
                    url_key="http://example.com/dup_app.apk"
                )

                user_msg = MagicMock()
                replies = []
                parse_modes = []

                async def reply_mock(text, parse_mode=None, **kwargs):
                    replies.append(text)
                    parse_modes.append(parse_mode)
                    m = AsyncMock()
                    m.edit_text = AsyncMock()
                    m.delete = AsyncMock()
                    return m

                user_msg.reply_text = AsyncMock(side_effect=reply_mock)
                user_msg.chat.id = 1234567
                user_msg.from_user.id = 99905

                with patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = MagicMock()
                    await bot.run_approved_pending_upload(pid, user_msg)

                # Approved duplicate produces:
                # 1. status message ("📤 جاري الرفع المباشر إلى تليجرام...")
                # 2. success card ("🌌 تمت العملية بنجاح...")
                # 3. BLITZVERIFY block (no warning since same package & version_code)
                self.assertEqual(len(replies), 3, f"Expected 3 replies, got {len(replies)}: {replies}")
                self.assertIn("جاري الرفع", replies[0])
                self.assertIn("تمت العملية بنجاح", replies[1])
                self.assertIn("BLITZVERIFY v1", replies[2])
                self.assertTrue(replies[2].startswith("```\n") and replies[2].endswith("\n```"))
                self.assertEqual(parse_modes[2], ParseMode.MARKDOWN)

                # Assert NO inspection card anywhere
                self.assertFalse(any("🛡️ بطاقة فحص APK" in r for r in replies))
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
