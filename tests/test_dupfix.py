import os
import sys
import time
import json
import shutil
import sqlite3
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot
from pyrogram.errors import MessageNotModified

class TestDupFix(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = os.path.abspath("test_data_dupfix")
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

    def test_approved_flow_regression_message_not_modified(self):
        """
        Simulate the approval flow with a fake status message whose edit_text
        raises MessageNotModified when new_text == current_text (seeded with «uploading» text).
        Verify that the upload completes, pending file is removed, and row status becomes 'done'.
        On pre-fix code, this MUST FAIL because MessageNotModified crashes the upload.
        """
        # Create a pending file
        test_file = os.path.join(bot.PENDING_DIR, "pending_123_test.apk")
        with open(test_file, "wb") as f:
            f.write(b"dummy apk content for dupfix test")

        pid = bot.db_add_pending_download(
            user_id=1594244556,
            chat_id=1594244556,
            file_path=test_file,
            filename="test.apk",
            custom_caption="",
            package="com.example.testapp",
            version_name="1.0",
            version_code=100,
            size=len(b"dummy apk content for dupfix test"),
            status="approved",
            flow_type="direct"
        )

        class FakeStatusMsg:
            def __init__(self, initial_text):
                self.current_text = initial_text
                self.id = 8888
                self.chat = MagicMock()
                self.chat.id = 1594244556
                self.delete = AsyncMock()

            async def edit_text(self, text, **kwargs):
                if text == self.current_text:
                    raise MessageNotModified()
                self.current_text = text
                return self

        status_messages = []
        original_msg = MagicMock()
        original_msg.chat.id = 1594244556

        async def fake_reply_text(text, **kwargs):
            s_msg = FakeStatusMsg(text)
            status_messages.append(s_msg)
            return s_msg

        original_msg.reply_text = AsyncMock(side_effect=fake_reply_text)

        async def run_test():
            with patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media, \
                 patch("bot.handle_apk_inspection_card", new_callable=AsyncMock) as mock_inspect_card:
                await bot.run_approved_pending_upload(pid, original_msg)
                return mock_send_media, mock_inspect_card

        mock_send_media, mock_inspect_card = asyncio.run(run_test())

        # Assert upload was delivered
        self.assertEqual(mock_send_media.call_count, 1, "Expected resilient_send_media to be called once")

        # Assert pending row ended in status 'done'
        row = bot.db_get_pending_download(pid)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "done", f"Expected row status to be 'done', got '{row['status']}'")

        # Assert pending file was removed
        self.assertFalse(os.path.exists(test_file), "Expected pending file to be deleted on completion")

    def test_cleanup_expired_pending_downloads_reaps_approved(self):
        """
        Verify that cleanup_expired_pending_downloads reaps rows in status 'approved'
        and 'pending' older than 24h, but leaves 'done', 'cancelled', and fresh rows untouched.
        """
        cutoff_old = time.time() - (25 * 3600)
        cutoff_fresh = time.time() - (1 * 3600)

        # 1. Old approved row
        old_approved_file = os.path.join(bot.PENDING_DIR, "old_approved.apk")
        with open(old_approved_file, "wb") as f:
            f.write(b"old approved")
        pid_approved = bot.db_add_pending_download(
            user_id=123, chat_id=123, file_path=old_approved_file, filename="old_approved.apk",
            custom_caption="", package="pkg.app", version_name="1.0", version_code=1,
            size=12, status="approved"
        )

        # 2. Old pending row
        old_pending_file = os.path.join(bot.PENDING_DIR, "old_pending.apk")
        with open(old_pending_file, "wb") as f:
            f.write(b"old pending")
        pid_pending = bot.db_add_pending_download(
            user_id=123, chat_id=123, file_path=old_pending_file, filename="old_pending.apk",
            custom_caption="", package="pkg.pen", version_name="1.0", version_code=1,
            size=11, status="pending"
        )

        # 3. Old done row
        old_done_file = os.path.join(bot.PENDING_DIR, "old_done.apk")
        with open(old_done_file, "wb") as f:
            f.write(b"old done")
        pid_done = bot.db_add_pending_download(
            user_id=123, chat_id=123, file_path=old_done_file, filename="old_done.apk",
            custom_caption="", package="pkg.done", version_name="1.0", version_code=1,
            size=8, status="done"
        )

        # 4. Old cancelled row
        old_cancelled_file = os.path.join(bot.PENDING_DIR, "old_cancelled.apk")
        with open(old_cancelled_file, "wb") as f:
            f.write(b"old cancelled")
        pid_cancelled = bot.db_add_pending_download(
            user_id=123, chat_id=123, file_path=old_cancelled_file, filename="old_cancelled.apk",
            custom_caption="", package="pkg.can", version_name="1.0", version_code=1,
            size=13, status="cancelled"
        )

        # 5. Fresh approved row
        fresh_approved_file = os.path.join(bot.PENDING_DIR, "fresh_approved.apk")
        with open(fresh_approved_file, "wb") as f:
            f.write(b"fresh approved")
        pid_fresh = bot.db_add_pending_download(
            user_id=123, chat_id=123, file_path=fresh_approved_file, filename="fresh_approved.apk",
            custom_caption="", package="pkg.fresh", version_name="1.0", version_code=1,
            size=14, status="approved"
        )

        # Backdate old rows
        conn = sqlite3.connect(bot.DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE pending_downloads SET created_at = ? WHERE id IN (?, ?, ?, ?)",
                  (cutoff_old, pid_approved, pid_pending, pid_done, pid_cancelled))
        c.execute("UPDATE pending_downloads SET created_at = ? WHERE id = ?",
                  (cutoff_fresh, pid_fresh))
        conn.commit()
        conn.close()

        # Run cleanup
        bot.cleanup_expired_pending_downloads()

        # Assert old approved was reaped
        self.assertFalse(os.path.exists(old_approved_file), "Old approved file should be deleted")
        row_app = bot.db_get_pending_download(pid_approved)
        self.assertEqual(row_app["status"], "expired", "Old approved row should become expired")

        # Assert old pending was reaped
        self.assertFalse(os.path.exists(old_pending_file), "Old pending file should be deleted")
        row_pen = bot.db_get_pending_download(pid_pending)
        self.assertEqual(row_pen["status"], "expired", "Old pending row should become expired")

        # Assert old done is UNTOUCHED
        self.assertTrue(os.path.exists(old_done_file), "Old done file should NOT be deleted")
        row_done = bot.db_get_pending_download(pid_done)
        self.assertEqual(row_done["status"], "done", "Old done row should remain done")

        # Assert old cancelled is UNTOUCHED
        self.assertTrue(os.path.exists(old_cancelled_file), "Old cancelled file should NOT be deleted")
        row_can = bot.db_get_pending_download(pid_cancelled)
        self.assertEqual(row_can["status"], "cancelled", "Old cancelled row should remain cancelled")

        # Assert fresh approved is UNTOUCHED
        self.assertTrue(os.path.exists(fresh_approved_file), "Fresh approved file should NOT be deleted")
        row_fresh = bot.db_get_pending_download(pid_fresh)
        self.assertEqual(row_fresh["status"], "approved", "Fresh approved row should remain approved")

if __name__ == "__main__":
    unittest.main()
