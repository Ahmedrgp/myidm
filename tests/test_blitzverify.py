import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot
from pyrogram.enums import ParseMode

class TestBlitzverify(unittest.TestCase):
    def setUp(self):
        self.sample_full = {
            "package": "org.supertuxkart.stk",
            "version_name": "1.5",
            "version_code": 328,
            "size_bytes": 183727403,
            "min_sdk": 21,
            "target_sdk": 35,
            "file_sha256": "E1F2F49152ABFB8F3ED0CED47981E84096758BFF9758563AA3B917111A2A3CBD",
            "cert_sha256": "326B6DC20BFEE3EDA6BF25624E164A2A266E3F7A094D6FDED99DDA29DA92F8BB",
            "checked_at": 1730000000.0,
            "is_bundle": False
        }

    def test_formatter_full_sample(self):
        msg = bot.format_blitzverify_block(self.sample_full)
        self.assertTrue(msg.startswith("```\n"))
        self.assertTrue(msg.endswith("\n```"))

        body = msg.strip().strip("`").strip("\r\n")
        lines = body.splitlines()

        expected_lines = [
            "BLITZVERIFY v1",
            "package: org.supertuxkart.stk",
            "version_name: 1.5",
            "version_code: 328",
            "size_bytes: 183727403",
            "min_sdk: 21",
            "target_sdk: 35",
            "file_sha256: e1f2f49152abfb8f3ed0ced47981e84096758bff9758563aa3b917111a2a3cbd",
            "cert_sha256: 326b6dc20bfee3eda6bf25624e164a2a266e3f7a094d6fded99dda29da92f8bb",
            "inspected_at: 2024-10-27 06:33"
        ]
        self.assertEqual(lines, expected_lines)

        # Verify lowercase hashes
        self.assertEqual(expected_lines[7].split(": ")[1], self.sample_full["file_sha256"].lower())
        self.assertEqual(expected_lines[8].split(": ")[1], self.sample_full["cert_sha256"].lower())

    def test_formatter_missing_cert_and_target_sdk(self):
        sample = dict(self.sample_full)
        sample["cert_sha256"] = None
        sample["target_sdk"] = None

        msg = bot.format_blitzverify_block(sample)
        body = msg.strip().strip("`").strip("\r\n")
        lines = body.splitlines()

        expected_lines = [
            "BLITZVERIFY v1",
            "package: org.supertuxkart.stk",
            "version_name: 1.5",
            "version_code: 328",
            "size_bytes: 183727403",
            "min_sdk: 21",
            "file_sha256: e1f2f49152abfb8f3ed0ced47981e84096758bff9758563aa3b917111a2a3cbd",
            "inspected_at: 2024-10-27 06:33"
        ]
        self.assertEqual(lines, expected_lines)
        self.assertNotIn("cert_sha256:", msg)
        self.assertNotIn("target_sdk:", msg)

    def test_formatter_bundle_values(self):
        bundle_info = {
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
            "checked_at": 1730000000.0
        }
        msg = bot.format_blitzverify_block(bundle_info)
        body = msg.strip().strip("`").strip("\r\n")
        lines = body.splitlines()

        # size_bytes and file_sha256 must be bundle's delivered values
        self.assertIn("size_bytes: 500000000", lines)
        self.assertIn("file_sha256: aaaaaaaa1111222233334444555566667777888899990000aaaabbbbccccdddd", lines)
        # metadata from base APK
        self.assertIn("package: com.game.bundle", lines)
        self.assertIn("version_code: 201", lines)
        self.assertIn("min_sdk: 26", lines)
        self.assertIn("target_sdk: 34", lines)
        self.assertIn("cert_sha256: bbbbbbbb1111222233334444555566667777888899990000aaaabbbbccccdddd", lines)

    def test_formatter_placeholders_omitted(self):
        degraded = {
            "package": "com.degraded.app",
            "version_name": "Unknown",
            "version_code": None,
            "size_bytes": 12345,
            "min_sdk": "-",
            "target_sdk": "N/A",
            "file_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "cert_sha256": None,
            "checked_at": None
        }
        msg = bot.format_blitzverify_block(degraded)
        body = msg.strip().strip("`").strip("\r\n")
        lines = body.splitlines()

        expected_lines = [
            "BLITZVERIFY v1",
            "package: com.degraded.app",
            "size_bytes: 12345",
            "file_sha256: abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        ]
        self.assertEqual(lines, expected_lines)

    def test_empty_info(self):
        self.assertEqual(bot.format_blitzverify_block({}), "")
        self.assertEqual(bot.format_blitzverify_block(None), "")

    async def async_test_handle_card_emits_card_and_block(self):
        user_msg = MagicMock()
        replies = []
        parse_modes = []

        async def reply_mock(text, parse_mode=None, **kwargs):
            replies.append(text)
            parse_modes.append(parse_mode)
            m = AsyncMock()
            return m

        user_msg.reply_text = AsyncMock(side_effect=reply_mock)

        await bot.handle_apk_inspection_card(
            file_path="tests_apk/golden_v1.apk",
            filename="golden_v1.apk",
            user_id=123456,
            user_msg=user_msg,
            lang="ar",
            precomputed_info=self.sample_full
        )

        self.assertEqual(len(replies), 1)
        # BLITZVERIFY code block (MARKDOWN) ONLY (no inspection card)
        self.assertTrue(replies[0].startswith("```\n"))
        self.assertTrue(replies[0].endswith("\n```"))
        self.assertIn("BLITZVERIFY v1", replies[0])
        self.assertIn("package: org.supertuxkart.stk", replies[0])
        self.assertEqual(parse_modes[0], ParseMode.MARKDOWN)
        self.assertFalse(any("🛡️ بطاقة فحص APK" in r for r in replies))

    def test_handle_card_emits_card_and_block(self):
        import asyncio
        asyncio.run(self.async_test_handle_card_emits_card_and_block())

if __name__ == "__main__":
    unittest.main()
