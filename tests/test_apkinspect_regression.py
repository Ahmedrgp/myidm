import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestApkInspectionSuite(unittest.TestCase):
    def setUp(self):
        self.apk_dir = "tests_apk"
        self.golden_v1 = os.path.join(self.apk_dir, "golden_v1.apk")
        self.golden_v2 = os.path.join(self.apk_dir, "golden_v2.apk")
        self.v2_only = os.path.join(self.apk_dir, "v2_only.apk")
        self.test_debug = os.path.join(self.apk_dir, "test_debug.apk")
        self.xapk = os.path.join(self.apk_dir, "sample_manifest.xapk")
        self.apks = os.path.join(self.apk_dir, "sample_largest.apks")
        self.non_apk = os.path.join(self.apk_dir, "non_apk.zip")
        self.corrupt = os.path.join(self.apk_dir, "corrupt.apk")

    def test_case_a_real_v1_signed(self):
        info = bot.inspect_apk(self.golden_v1)
        self.assertIsNotNone(info)
        self.assertEqual(info["package"], "android.appsecurity.cts.tinyapp")
        self.assertEqual(info["version_name"], "1.0")
        self.assertEqual(info["version_code"], 10)
        self.assertEqual(info["min_sdk"], 23)
        self.assertEqual(info["target_sdk"], 23)
        self.assertEqual(info["signer_source"], "v1")
        self.assertEqual(info["cert_sha256"], "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8")
        self.assertEqual(info["cert_sha1"], "0AA07C0F297B4AE834DC85A17EEA8C2CF9380FF7")
        self.assertIn("CN=rsa-2048", info["subject_dn"])

    def test_case_b_real_v2_v3_only_signed(self):
        info = bot.inspect_apk(self.golden_v2)
        self.assertIsNotNone(info)
        self.assertEqual(info["package"], "android.appsecurity.cts.tinyapp")
        self.assertEqual(info["version_name"], "1.0")
        self.assertEqual(info["version_code"], 10)
        self.assertEqual(info["signer_source"], "v2/v3")
        self.assertEqual(info["cert_sha256"], "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8")
        self.assertIn("CN=rsa-2048", info["subject_dn"])

        info2 = bot.inspect_apk(self.v2_only)
        self.assertIsNotNone(info2)
        self.assertEqual(info2["signer_source"], "v2/v3")
        self.assertEqual(info2["cert_sha256"], "BC5E64EAB1C4B5137C0FBC5ED05850B3A148D1C41775CFFA4D96EEA90BDD0EB8")
        self.assertIn("CN=rsa-1024", info2["subject_dn"])

    def test_case_c_xapk_and_apks_bundle(self):
        info_xapk = bot.inspect_apk(self.xapk)
        self.assertIsNotNone(info_xapk)
        self.assertTrue(info_xapk["is_bundle"])
        self.assertIn("manifest package match", info_xapk["bundle_rule_en"])
        self.assertEqual(info_xapk["package"], "android.appsecurity.cts.tinyapp")
        self.assertEqual(info_xapk["cert_sha256"], "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8")

        info_apks = bot.inspect_apk(self.apks)
        self.assertIsNotNone(info_apks)
        self.assertTrue(info_apks["is_bundle"])
        self.assertIn("largest APK", info_apks["bundle_rule_en"])
        self.assertEqual(info_apks["package"], "android.appsecurity.cts.tinyapp")

    def test_case_d_non_apk_zip(self):
        info = bot.inspect_apk(self.non_apk)
        self.assertIsNotNone(info)
        self.assertIsNone(info["package"])
        self.assertIsNone(info["version_name"])
        self.assertIsNone(info["cert_sha256"])
        self.assertIsNotNone(info["file_sha256"])
        card = bot.format_apk_inspection_card(info, None, lang="ar")
        self.assertIn("لم يتم العثور على شهادة توقيع", card)

    def test_case_e_truncated_corrupt_apk(self):
        info = bot.inspect_apk(self.corrupt)
        self.assertIsNone(info)

    def test_signer_consistency_across_versions(self):
        test_pkg = f"com.test.consistency_{int(bot.time.time())}"
        cert_A = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        cert_B = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

        # 1. First inspection
        bot.db_add_apk_inspection(1234, test_pkg, "1.0", 1, "FILE_SHA_1", cert_A, 1024, "app1.apk")
        prev1 = bot.db_get_last_inspection_for_package(test_pkg, exclude_latest=True)
        self.assertIsNone(prev1)

        # 2. Second inspection, same signer
        bot.db_add_apk_inspection(1234, test_pkg, "1.1", 2, "FILE_SHA_2", cert_A, 2048, "app2.apk")
        prev2 = bot.db_get_last_inspection_for_package(test_pkg, exclude_latest=True)
        self.assertIsNotNone(prev2)
        self.assertEqual(prev2["cert_sha256"], cert_A)
        self.assertEqual(prev2["version_name"], "1.0")

        mock_info2 = {"package": test_pkg, "version_name": "1.1", "version_code": 2, "size_bytes": 2048, "cert_sha256": cert_A, "subject_dn": "CN=SignerA", "file_sha256": "F2", "checked_at": bot.time.time()}
        card_ar2 = bot.format_apk_inspection_card(mock_info2, prev2, lang="ar")
        card_en2 = bot.format_apk_inspection_card(mock_info2, prev2, lang="en")
        self.assertIn("✅ نفس الموقّع مثل الإصدار v1.0", card_ar2)
        self.assertIn("✅ Same signer as v1.0", card_en2)

        # 3. Third inspection, different signer (re-signed)
        bot.db_add_apk_inspection(1234, test_pkg, "2.0", 3, "FILE_SHA_3", cert_B, 3072, "app3.apk")
        prev3 = bot.db_get_last_inspection_for_package(test_pkg, exclude_latest=True)
        self.assertIsNotNone(prev3)
        self.assertEqual(prev3["cert_sha256"], cert_A)
        self.assertEqual(prev3["version_name"], "1.1")

        mock_info3 = {"package": test_pkg, "version_name": "2.0", "version_code": 3, "size_bytes": 3072, "cert_sha256": cert_B, "subject_dn": "CN=SignerB", "file_sha256": "F3", "checked_at": bot.time.time()}
        card_ar3 = bot.format_apk_inspection_card(mock_info3, prev3, lang="ar")
        card_diff_en = bot.format_apk_inspection_card(mock_info3, prev3, lang="en")
        self.assertIn("⚠️ موقّع مختلف عن الإصدار v1.1", card_ar3)
        self.assertIn("⚠️ DIFFERENT signer than v1.1", card_diff_en)

    def test_pipeline_wiring_non_apk_vs_apk(self):
        async def run_pipeline_test():
            user_msg = MagicMock()
            user_msg.reply_text = AsyncMock()
            user_msg.chat.id = 12345
            user_msg.from_user.id = 12345

            # Non-APK upload
            non_apk_file = os.path.join(self.apk_dir, "non_apk.zip")
            await bot.handle_apk_inspection_card(non_apk_file, "file.zip", 12345, user_msg, lang="ar")
            user_msg.reply_text.assert_not_called()

            # Real APK upload: emits inspection card then BLITZVERIFY block
            await bot.handle_apk_inspection_card(self.golden_v1, "golden_v1.apk", 12345, user_msg, lang="ar")
            self.assertEqual(user_msg.reply_text.call_count, 2)
            card_call = user_msg.reply_text.call_args_list[0]
            block_call = user_msg.reply_text.call_args_list[1]
            card_text = card_call[0][0]
            block_text = block_call[0][0]
            self.assertIn("بطاقة فحص APK | APK Inspection", card_text)
            self.assertIn("android.appsecurity.cts.tinyapp", card_text)
            self.assertIn("FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8", card_text)
            self.assertIn("BLITZVERIFY v1", block_text)
            self.assertIn("package: android.appsecurity.cts.tinyapp", block_text)

        asyncio.run(run_pipeline_test())

if __name__ == "__main__":
    unittest.main()
