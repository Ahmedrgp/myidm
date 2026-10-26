import os
import sys
import shutil
import sqlite3
import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageIdInvalid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestFwdCache(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = os.path.abspath("test_data_fwdcache")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)

        self.orig_data_dir = bot.DATA_DIR
        self.orig_db_file = bot.DB_FILE
        self.orig_download_dir = bot.DOWNLOAD_DIR
        self.orig_pending_dir = bot.PENDING_DIR

        bot.DATA_DIR = self.test_dir
        bot.DB_FILE = os.path.join(self.test_dir, "bot_database.db")
        bot.DOWNLOAD_DIR = os.path.join(self.test_dir, "downloads")
        bot.PENDING_DIR = os.path.join(self.test_dir, "pending_downloads")
        os.makedirs(bot.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(bot.PENDING_DIR, exist_ok=True)

        bot.init_db()

        self.user_id = 1594244556
        self.chat_id = 1594244556

    async def asyncTearDown(self):
        bot.DATA_DIR = self.orig_data_dir
        bot.DB_FILE = self.orig_db_file
        bot.DOWNLOAD_DIR = self.orig_download_dir
        bot.PENDING_DIR = self.orig_pending_dir

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_user_msg(self, user_id=None, chat_id=None):
        uid = user_id or self.user_id
        cid = chat_id or self.chat_id
        user_msg = MagicMock()
        user_msg.chat = MagicMock()
        user_msg.chat.id = cid
        user_msg.from_user = MagicMock()
        user_msg.from_user.id = uid
        user_msg.from_user.is_bot = False
        user_msg.replies = []

        async def fake_reply(text, **kwargs):
            user_msg.replies.append({"text": text, "kwargs": kwargs})
            resp = AsyncMock()
            resp.edit_reply_markup = AsyncMock()
            resp.delete = AsyncMock()
            return resp

        user_msg.reply_text = AsyncMock(side_effect=fake_reply)
        return user_msg

    def _make_status_msg(self):
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        status_msg.delete = AsyncMock()
        return status_msg

    async def test_repeat_url_forwarded_no_download(self):
        """Case 1: Repeat URL -> stored ids forwarded in order; download engine NOT invoked; note with fwd_fresh_ button sent."""
        url = "https://example.com/files/archive.zip"
        row_id = bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="archive.zip",
            total_size=104857600,
            chat_id=self.chat_id,
            message_ids=[701]
        )
        self.assertGreater(row_id, 0)

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine:
            await bot.handle_url_intake(
                url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            # Stored message forwarded in order
            mock_fwd.assert_awaited_once_with(
                chat_id=self.chat_id,
                from_chat_id=self.chat_id,
                message_ids=[701]
            )
            # Download engine NOT invoked
            mock_engine.assert_not_called()

            # Note sent with fwd_fresh_ button
            self.assertEqual(len(user_msg.replies), 1)
            reply = user_msg.replies[0]
            self.assertIn("Forwarded your earlier download instead of re-downloading", reply["text"])
            self.assertIn("archive.zip", reply["text"])
            self.assertIn("100.0 MiB", reply["text"])
            self.assertIn("Cairo", reply["text"])

            kb = reply["kwargs"].get("reply_markup")
            self.assertIsNotNone(kb)
            btn = kb.inline_keyboard[0][0]
            self.assertEqual(btn.text, "⬇️ نزّله من جديد")
            self.assertEqual(btn.callback_data, f"fwd_fresh_{row_id}")

            # Status message deleted
            status_msg.delete.assert_awaited_once()

    async def test_forward_raising_message_id_invalid_deletes_row_and_falls_through(self):
        """Case 2: Forward raising MessageIdInvalid -> row deleted and fresh-download path invoked."""
        url = "https://example.com/stale/document.pdf"
        row_id = bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="document.pdf",
            total_size=54321,
            chat_id=self.chat_id,
            message_ids=[801]
        )
        self.assertIsNotNone(bot.db_get_delivery_by_id(row_id))

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine, \
             self.assertLogs("bot", level="WARNING") as logs:
            mock_fwd.side_effect = MessageIdInvalid()

            await bot.handle_url_intake(
                url=url,
                custom_name="custom_doc",
                custom_caption="caption",
                status_msg=status_msg,
                user_msg=user_msg
            )

            # Stale row must be deleted
            self.assertIsNone(bot.db_get_delivery_by_id(row_id))
            self.assertIsNone(bot.db_get_delivery(self.user_id, url))

            # One WARNING logged
            self.assertTrue(any("Forward failed for delivery id=" in l and "Deleting stale row" in l for l in logs.output))

            # Fresh download path invoked with original arguments
            mock_engine.assert_awaited_once_with(url, "custom_name" if False else "custom_doc", "caption", status_msg, user_msg)

    async def test_fwd_fresh_callback_runs_fresh_download(self):
        """Case 3: fwd_fresh_<id> callback -> fresh download runs even though a row exists."""
        url = "https://example.com/app/release.apk"
        row_id = bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="release.apk",
            total_size=20000000,
            chat_id=self.chat_id,
            message_ids=[901]
        )
        self.assertIsNotNone(bot.db_get_delivery_by_id(row_id))

        query = MagicMock()
        query.data = f"fwd_fresh_{row_id}"
        query.from_user = MagicMock(id=self.user_id)
        query.message = MagicMock()
        query.message.chat = MagicMock(id=self.chat_id)
        query.message.reply_text = AsyncMock()
        query.message.edit_reply_markup = AsyncMock()
        query.answer = AsyncMock()

        status_mock = AsyncMock()
        query.message.reply_text.return_value = status_mock

        with patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine, \
             patch("bot.is_admin", return_value=True):
            await bot.callback_handler(bot.bot, query)
            # Give background task time to run
            await asyncio.sleep(0.01)

            query.answer.assert_awaited_once()
            query.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
            mock_engine.assert_awaited_once_with(
                raw_url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_mock,
                user_msg=query.message,
                forced_user_id=self.user_id
            )

    async def test_split_delivery_forwards_all_parts_in_order(self):
        """Case 4: Split delivery (3 stored ids) -> all 3 forwarded in order."""
        url = "https://example.com/large/system_image.iso"
        row_id = bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="system_image.iso",
            total_size=4000000000,
            chat_id=self.chat_id,
            message_ids=[1001, 1002, 1003]
        )

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine:
            await bot.handle_url_intake(
                url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            mock_fwd.assert_awaited_once_with(
                chat_id=self.chat_id,
                from_chat_id=self.chat_id,
                message_ids=[1001, 1002, 1003]
            )
            mock_engine.assert_not_called()
            self.assertEqual(len(user_msg.replies), 1)

    async def test_apk_repeat_with_stored_inspection_resends_blitzverify(self):
        """Case 5: APK repeat with a stored inspection -> BLITZVERIFY block is re-sent, byte-identical."""
        url = "https://example.com/apks/game.apk"
        pkg = "org.example.game"
        vcode = 105
        checked_epoch = 1730000000.0

        # Store inspection in apk_inspections with realistic min_sdk and target_sdk
        bot.db_add_apk_inspection(
            user_id=self.user_id,
            package=pkg,
            version_name="1.5.0",
            version_code=vcode,
            file_sha256="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            cert_sha256="ffffbbbbccccdddd1111222233334444555566667777888899990000aaaaffff",
            size=45678901,
            filename="game.apk",
            checked_at=checked_epoch,
            min_sdk=21,
            target_sdk=34
        )

        # Store delivery with package + version_code
        bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="game.apk",
            total_size=45678901,
            chat_id=self.chat_id,
            message_ids=[2001],
            package=pkg,
            version_code=vcode
        )

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine:
            await bot.handle_url_intake(
                url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            mock_fwd.assert_awaited_once_with(
                chat_id=self.chat_id,
                from_chat_id=self.chat_id,
                message_ids=[2001]
            )
            mock_engine.assert_not_called()

            # Expect 2 replies: note + BLITZVERIFY block
            self.assertEqual(len(user_msg.replies), 2)
            note_reply = user_msg.replies[0]
            block_reply = user_msg.replies[1]

            self.assertIn("Forwarded your earlier download", note_reply["text"])
            self.assertEqual(block_reply["kwargs"].get("parse_mode"), ParseMode.MARKDOWN)

            # Build expected block directly using format_blitzverify_block on the stored inspection row
            stored_insp = bot.db_check_apk_duplicate(pkg, vcode)
            expected_info = {
                "package": stored_insp["package"],
                "version_name": stored_insp["version_name"],
                "version_code": stored_insp["version_code"],
                "size_bytes": stored_insp["size"],
                "min_sdk": stored_insp["min_sdk"],
                "target_sdk": stored_insp["target_sdk"],
                "file_sha256": stored_insp["file_sha256"],
                "cert_sha256": stored_insp["cert_sha256"],
                "checked_at": stored_insp["checked_at"]
            }
            expected_block = bot.format_blitzverify_block(expected_info)

            # Verify byte-identical re-emission and that SDK fields are present
            self.assertEqual(block_reply["text"], expected_block)
            self.assertTrue(block_reply["text"].startswith("```\nBLITZVERIFY v1\n"))
            self.assertIn("min_sdk: 21", block_reply["text"])
            self.assertIn("target_sdk: 34", block_reply["text"])

    async def test_same_url_different_user_no_match(self):
        """Case 6: Same URL, different user -> no match, normal flow."""
        url = "https://example.com/shared/manual.pdf"
        # User A downloads
        bot.db_record_delivery(
            user_id=11111,
            url_key=url,
            filename="manual.pdf",
            total_size=12345,
            chat_id=11111,
            message_ids=[3001]
        )

        # User B sends same URL
        user_msg = self._make_user_msg(user_id=22222, chat_id=22222)
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine:
            await bot.handle_url_intake(
                url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            # User B must NOT receive forward of User A
            mock_fwd.assert_not_called()
            # Normal engine called
            mock_engine.assert_awaited_once_with(url, "", "", status_msg, user_msg)

    async def test_urls_differing_only_in_fragment_no_match(self):
        """Case 7: URLs differing only in the fragment -> no match."""
        url_v1 = "https://an1.com/game-download.html#file_version=1"
        url_v2 = "https://an1.com/game-download.html#file_version=2"

        bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url_v1,
            filename="game_v1.apk",
            total_size=99999,
            chat_id=self.chat_id,
            message_ids=[4001]
        )

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch.object(bot.bot, "forward_messages", new_callable=AsyncMock) as mock_fwd, \
             patch("bot.process_download_and_upload", new_callable=AsyncMock) as mock_engine:
            await bot.handle_url_intake(
                url=url_v2,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            # Different fragment must NOT match
            mock_fwd.assert_not_called()
            mock_engine.assert_awaited_once_with(url_v2, "", "", status_msg, user_msg)

    async def test_re_download_replaces_row(self):
        """Verify that freshly re-downloading the same URL replaces the row with newest delivery."""
        url = "https://example.com/firmware.bin"
        bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="firmware.bin",
            total_size=1000,
            chat_id=self.chat_id,
            message_ids=[101],
            created_at=1000
        )
        row1 = bot.db_get_delivery(self.user_id, url)
        self.assertEqual(row1["message_ids"], [101])

        # New delivery replaces old delivery
        bot.db_record_delivery(
            user_id=self.user_id,
            url_key=url,
            filename="firmware.bin",
            total_size=2000,
            chat_id=self.chat_id,
            message_ids=[202],
            created_at=2000
        )
        row2 = bot.db_get_delivery(self.user_id, url)
        self.assertEqual(row2["message_ids"], [202])
        self.assertEqual(row2["total_size"], 2000)
        self.assertEqual(row2["created_at"], 2000)

    async def test_delivery_recorded_on_process_download_and_upload_single(self):
        """Verify delivery row is recorded on successful single upload in process_download_and_upload."""
        test_file = os.path.join(self.test_dir, "test_doc.mp4")
        with open(test_file, "wb") as f:
            f.write(b"mock video content")

        fake_msg = MagicMock()
        fake_msg.id = 777
        fake_msg.chat = MagicMock(id=self.chat_id)

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()
        url = "https://example.com/test_doc.mp4"

        with patch("bot.unrestrict_direct_link", new_callable=AsyncMock, return_value=url), \
             patch("bot.is_hls_or_video_stream", return_value=True), \
             patch("bot.download_video_or_m3u8", new_callable=AsyncMock, return_value=(True, test_file, "test_doc.mp4")), \
             patch("bot.is_valid_binary_file", return_value=(True, b"")), \
             patch("bot.resilient_send_media", new_callable=AsyncMock, return_value=fake_msg):
            await bot.process_download_and_upload(
                raw_url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        row = bot.db_get_delivery(self.user_id, url)
        self.assertIsNotNone(row)
        self.assertEqual(row["message_ids"], [777])
        self.assertEqual(row["filename"], "test doc.mp4")
        self.assertIsNone(row["package"])
        self.assertIsNone(row["version_code"])

    async def test_failed_download_records_no_delivery(self):
        """Failed downloads must record nothing."""
        url = "https://example.com/broken.pdf"
        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()

        with patch("bot.unrestrict_direct_link", new_callable=AsyncMock, side_effect=Exception("Network failure")):
            try:
                await bot.process_download_and_upload(
                    raw_url=url,
                    custom_name="",
                    custom_caption="",
                    status_msg=status_msg,
                    user_msg=user_msg
                )
            except Exception:
                pass

        row = bot.db_get_delivery(self.user_id, url)
        self.assertIsNone(row)

    async def test_delivery_recorded_for_apk_with_package_and_version(self):
        """Verify delivery row captures package and version_code for APK deliveries."""
        test_file = os.path.join(self.test_dir, "test_app.apk")
        with open(test_file, "wb") as f:
            f.write(b"mock apk bytes")

        fake_msg = MagicMock()
        fake_msg.id = 888
        fake_msg.chat = MagicMock(id=self.chat_id)

        user_msg = self._make_user_msg()
        status_msg = self._make_status_msg()
        url = "https://example.com/test_app.apk"
        apk_inspect_data = {
            "package": "com.mock.app",
            "version_name": "3.0",
            "version_code": 300,
            "size_bytes": 14,
            "file_sha256": "abc",
            "cert_sha256": "def",
            "checked_at": 1730000000.0
        }

        with patch("bot.unrestrict_direct_link", new_callable=AsyncMock, return_value=url), \
             patch("bot.is_hls_or_video_stream", return_value=True), \
             patch("bot.download_video_or_m3u8", new_callable=AsyncMock, return_value=(True, test_file, "test_app.apk")), \
             patch("bot.is_valid_binary_file", return_value=(True, b"")), \
             patch("bot.inspect_apk", return_value=apk_inspect_data), \
             patch("bot.db_check_apk_duplicate", return_value=None), \
             patch("bot.resilient_send_media", new_callable=AsyncMock, return_value=fake_msg), \
             patch("bot.handle_apk_inspection_card", new_callable=AsyncMock):
            await bot.process_download_and_upload(
                raw_url=url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        row = bot.db_get_delivery(self.user_id, url)
        self.assertIsNotNone(row)
        self.assertEqual(row["message_ids"], [888])
        self.assertEqual(row["package"], "com.mock.app")
        self.assertEqual(row["version_code"], 300)

    def test_fresh_inspection_stores_and_returns_sdk_values(self):
        """Fresh-inspection test: after db_add_apk_inspection with SDK values, db_get_apk_inspection returns them."""
        pkg = "com.test.fresh_sdk"
        vcode = 42
        row_id = bot.db_add_apk_inspection(
            user_id=self.user_id,
            package=pkg,
            version_name="2.1.0",
            version_code=vcode,
            file_sha256="aaaa11112222",
            cert_sha256="bbbb22223333",
            size=123456,
            filename="fresh.apk",
            checked_at=1730000000.0,
            min_sdk=24,
            target_sdk=35
        )
        self.assertIsNotNone(row_id)
        insp = bot.db_get_apk_inspection(pkg, vcode)
        self.assertIsNotNone(insp)
        self.assertEqual(insp["package"], pkg)
        self.assertEqual(insp["version_code"], vcode)
        self.assertEqual(insp["min_sdk"], 24)
        self.assertEqual(insp["target_sdk"], 35)
        self.assertEqual(insp["version_name"], "2.1.0")
        self.assertEqual(insp["size"], 123456)

    def test_migration_adds_sdk_columns_to_existing_db_and_is_idempotent(self):
        """Migration test: existing DB without min_sdk/target_sdk gains them on startup without error, and a second startup is a no-op."""
        legacy_db_path = os.path.join(self.test_dir, "legacy_db.db")
        if os.path.exists(legacy_db_path):
            os.remove(legacy_db_path)

        # Create an unmigrated database with legacy apk_inspections schema (no min_sdk, no target_sdk)
        conn = sqlite3.connect(legacy_db_path)
        cursor = conn.cursor()
        cursor.execute("""
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
        cursor.execute("""
            CREATE TABLE history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                file_size INTEGER,
                download_time REAL,
                file_type TEXT,
                created_at REAL
            )
        """)
        cursor.execute("""
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
        cursor.execute("""
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
        # Insert an old inspection row without SDK columns
        cursor.execute("""
            INSERT INTO apk_inspections (user_id, package, version_name, version_code, file_sha256, cert_sha256, size, filename, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.user_id, "com.legacy.app", "1.0", 1, "sha_file", "sha_cert", 1000, "legacy.apk", 1700000000.0))
        conn.commit()
        conn.close()

        # Switch bot.DB_FILE to legacy DB
        bot.DB_FILE = legacy_db_path
        try:
            # 1. First startup / migration
            bot.init_db()

            # Verify columns exist
            conn = sqlite3.connect(legacy_db_path)
            c = conn.cursor()
            c.execute("PRAGMA table_info(apk_inspections)")
            cols = {row[1]: row[2] for row in c.fetchall()}
            conn.close()

            self.assertIn("min_sdk", cols)
            self.assertIn("target_sdk", cols)

            # Query the pre-existing row: min_sdk and target_sdk should be None (NULL)
            legacy_insp = bot.db_get_apk_inspection("com.legacy.app", 1)
            self.assertIsNotNone(legacy_insp)
            self.assertIsNone(legacy_insp["min_sdk"])
            self.assertIsNone(legacy_insp["target_sdk"])
            self.assertEqual(legacy_insp["version_name"], "1.0")

            # Formatter handles NULL SDKs gracefully without crash or error
            insp_info = {
                "package": legacy_insp.get("package"),
                "version_name": legacy_insp.get("version_name"),
                "version_code": legacy_insp.get("version_code"),
                "size_bytes": legacy_insp.get("size"),
                "file_sha256": legacy_insp.get("file_sha256"),
                "cert_sha256": legacy_insp.get("cert_sha256"),
                "checked_at": legacy_insp.get("checked_at"),
                "min_sdk": legacy_insp.get("min_sdk"),
                "target_sdk": legacy_insp.get("target_sdk")
            }
            block = bot.format_blitzverify_block(insp_info)
            self.assertNotIn("min_sdk:", block)
            self.assertNotIn("target_sdk:", block)

            # 2. Second startup / migration must be a completely silent no-op
            bot.init_db()

            # 3. New inspection with SDK values works on the migrated DB
            bot.db_add_apk_inspection(
                user_id=self.user_id,
                package="com.migrated.app",
                version_name="2.0",
                version_code=2,
                file_sha256="sha_file2",
                cert_sha256="sha_cert2",
                size=2000,
                filename="migrated.apk",
                min_sdk=26,
                target_sdk=34
            )
            migrated_insp = bot.db_get_apk_inspection("com.migrated.app", 2)
            self.assertIsNotNone(migrated_insp)
            self.assertEqual(migrated_insp["min_sdk"], 26)
            self.assertEqual(migrated_insp["target_sdk"], 34)
        finally:
            bot.DB_FILE = os.path.join(self.test_dir, "bot_database.db")

if __name__ == "__main__":
    unittest.main()
