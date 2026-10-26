import os
import sys
import ssl
import shutil
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from aiohttp import web
from aiohttp.client_reqrep import ConnectionKey

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestSSLRetry(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = os.path.abspath("test_data_sslretry")
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

        # Start ephemeral local HTTP server to serve real test file bytes
        self.app = web.Application()
        self.file_data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        async def handle_pdf(request):
            return web.Response(
                body=self.file_data,
                content_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="ssltest.pdf"'}
            )
        self.app.router.add_get("/ssltest.pdf", handle_pdf)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        # Retrieve actual dynamic port
        self.server_port = self.site._server.sockets[0].getsockname()[1]
        self.test_url = f"http://127.0.0.1:{self.server_port}/ssltest.pdf"

    async def asyncTearDown(self):
        try:
            await self.runner.cleanup()
        except Exception:
            pass

        bot.DATA_DIR = self.orig_data_dir
        bot.DB_FILE = self.orig_db_file
        bot.DOWNLOAD_DIR = self.orig_download_dir
        bot.PENDING_DIR = self.orig_pending_dir

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_cert_verification_error_matching(self):
        """Verify that is_cert_verification_error strictly matches certificate verification failures only."""
        dummy_key = ConnectionKey("example.com", 443, True, True, None, None, None, None)

        # 1. ssl.SSLCertVerificationError
        cert_err = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1016)")
        self.assertTrue(bot.is_cert_verification_error(cert_err))

        # 2. aiohttp.ClientConnectorCertificateError
        aio_cert_err = aiohttp.ClientConnectorCertificateError(dummy_key, cert_err)
        self.assertTrue(bot.is_cert_verification_error(aio_cert_err))

        # 3. Text containing CERTIFICATE_VERIFY_FAILED
        custom_err = Exception("Cannot connect to host example.com:443 ssl:True [SSL: CERTIFICATE_VERIFY_FAILED] verify failed")
        self.assertTrue(bot.is_cert_verification_error(custom_err))

        # 4. curl_cffi CertificateVerifyError if available
        if bot.CURL_CFFI_AVAILABLE:
            try:
                from curl_cffi.requests.exceptions import CertificateVerifyError
                c_err = CertificateVerifyError("curl: (60) SSL certificate OpenSSL verify result: unable to get local issuer certificate")
                self.assertTrue(bot.is_cert_verification_error(c_err))
            except ImportError:
                pass

        # 5. NEGATIVE: NON-certificate SSL errors
        non_cert_ssl1 = ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1016)")
        self.assertFalse(bot.is_cert_verification_error(non_cert_ssl1))

        non_cert_ssl2 = aiohttp.ClientConnectorSSLError(dummy_key, non_cert_ssl1)
        self.assertFalse(bot.is_cert_verification_error(non_cert_ssl2))

        handshake_err = aiohttp.ClientConnectorSSLError(dummy_key, ssl.SSLError(1, "[SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] handshake failure"))
        self.assertFalse(bot.is_cert_verification_error(handshake_err))

        # 6. NEGATIVE: Normal connection/network errors
        dns_err = aiohttp.ClientConnectorError(dummy_key, OSError(11001, "getaddrinfo failed"))
        self.assertFalse(bot.is_cert_verification_error(dns_err))

        conn_refused = aiohttp.ClientConnectorError(dummy_key, ConnectionRefusedError(10061, "Connect call failed"))
        self.assertFalse(bot.is_cert_verification_error(conn_refused))

        timeout_err = aiohttp.ServerTimeoutError("Server timeout")
        self.assertFalse(bot.is_cert_verification_error(timeout_err))

    async def test_sslretry_success_after_one_unverified_retry(self):
        """
        Simulation test:
        A fake download connector raises a certificate-verification error on the first attempt
        (when verification is enabled) and serves bytes when called with verification disabled.
        Assert exactly 2 attempts, the second with verification off, and the file delivered
        through the normal validation path with the bilingual notice line in the success message.
        """
        attempts_log = []

        class FakeDownloadConnector(aiohttp.TCPConnector):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                attempts_log.append({
                    "attempt": len(attempts_log) + 1,
                    "ssl": self._ssl,
                })

            async def _create_connection(self, req, traces, timeout):
                if self._ssl is not False and req.ssl is not False:
                    key = req.connection_key
                    raise aiohttp.ClientConnectorCertificateError(
                        key,
                        ssl.SSLCertVerificationError(
                            1,
                            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1016)"
                        )
                    )
                return await super()._create_connection(req, traces, timeout)

        user_msg = MagicMock()
        user_msg.chat.id = 1594244556
        user_msg.from_user.id = 1594244556
        replies = []
        async def reply_text_mock(text, **kwargs):
            replies.append(text)
            msg_mock = AsyncMock()
            msg_mock.edit_text = AsyncMock()
            msg_mock.delete = AsyncMock()
            return msg_mock
        user_msg.reply_text = AsyncMock(side_effect=reply_text_mock)

        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        status_msg.delete = AsyncMock()

        with patch("bot.CURL_CFFI_AVAILABLE", False), \
             patch("aiohttp.TCPConnector", FakeDownloadConnector), \
             patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media, \
             self.assertLogs("bot", level="WARNING") as captured_logs:

            await bot.process_download_and_upload(
                raw_url=self.test_url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        # 1. Exactly 2 attempts were made
        self.assertEqual(len(attempts_log), 2, f"Expected exactly 2 attempts, got {len(attempts_log)}: {attempts_log}")
        # Attempt 1 had verification on
        self.assertIsNot(attempts_log[0]["ssl"], False)
        # Attempt 2 had verification off
        self.assertIs(attempts_log[1]["ssl"], False)

        # 2. File was delivered through normal validation path
        self.assertTrue(mock_send_media.called, "File should have been sent via resilient_send_media")
        self.assertEqual(len(replies), 1, f"Expected 1 success reply, got {len(replies)}: {replies}")
        success_card = replies[0]

        # 3. Final success message contains the bilingual notice line
        self.assertIn(bot.TLS_VERIFICATION_SKIPPED_NOTICE, success_card)
        self.assertIn("🔓 تم تجاوز التحقق من الشهادة لهذا المضيف (سلسلة شهادة ناقصة)", success_card)
        self.assertIn("TLS verification skipped for this host (broken certificate chain)", success_card)

        # 4. Exactly one clear WARNING line was logged with host and reason
        warning_logs = [log for log in captured_logs.output if "TLS certificate verification failed" in log]
        self.assertEqual(len(warning_logs), 1, f"Expected 1 TLS warning log, got {len(warning_logs)}: {warning_logs}")
        self.assertIn(str(self.server_port), warning_logs[0])
        self.assertIn("CERTIFICATE_VERIFY_FAILED", warning_logs[0])

    async def test_sslretry_negative_non_cert_ssl_error(self):
        """
        Negative test:
        A fake connector raises a NON-certificate SSL error (e.g. wrong version / protocol mismatch).
        Assert NO unverified retry happens (single attempt, normal failure).
        """
        attempts_log = []

        class FakeNonCertSSLConnector(aiohttp.TCPConnector):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                attempts_log.append({
                    "attempt": len(attempts_log) + 1,
                    "ssl": self._ssl,
                })

            async def _create_connection(self, req, traces, timeout):
                key = req.connection_key
                raise aiohttp.ClientConnectorSSLError(
                    key,
                    ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1016)")
                )

        user_msg = MagicMock()
        user_msg.chat.id = 1594244556
        user_msg.from_user.id = 1594244556
        replies = []
        user_msg.reply_text = AsyncMock(side_effect=lambda text, **kw: replies.append(text))

        status_msg = AsyncMock()
        status_msg_edits = []
        async def fake_edit_text(text, **kwargs):
            status_msg_edits.append(text)
        status_msg.edit_text = AsyncMock(side_effect=fake_edit_text)
        status_msg.delete = AsyncMock()

        with patch("bot.CURL_CFFI_AVAILABLE", False), \
             patch("aiohttp.TCPConnector", FakeNonCertSSLConnector), \
             patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media:

            await bot.process_download_and_upload(
                raw_url=self.test_url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        # Assert exactly 1 attempt (NO unverified retry)
        self.assertEqual(len(attempts_log), 1, f"Expected exactly 1 attempt, got {len(attempts_log)}")
        # No file upload occurred
        self.assertFalse(mock_send_media.called)
        self.assertEqual(len(replies), 0)
        # Normal error message was displayed in status_msg
        self.assertTrue(any("Network Connection Error" in msg and "WRONG_VERSION_NUMBER" in msg for msg in status_msg_edits),
                        f"Expected Network Connection Error with WRONG_VERSION_NUMBER, got: {status_msg_edits}")

    async def test_sslretry_negative_connection_refused(self):
        """
        Negative test:
        A normal connection error (DNS or refused).
        Assert NO unverified retry happens (single attempt, normal failure).
        """
        attempts_log = []

        class FakeRefusedConnector(aiohttp.TCPConnector):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                attempts_log.append({
                    "attempt": len(attempts_log) + 1,
                    "ssl": self._ssl,
                })

            async def _create_connection(self, req, traces, timeout):
                key = req.connection_key
                raise aiohttp.ClientConnectorError(
                    key,
                    ConnectionRefusedError(10061, "Connect call failed")
                )

        user_msg = MagicMock()
        user_msg.chat.id = 1594244556
        user_msg.from_user.id = 1594244556
        replies = []
        user_msg.reply_text = AsyncMock(side_effect=lambda text, **kw: replies.append(text))

        status_msg = AsyncMock()
        status_msg_edits = []
        async def fake_edit_text(text, **kwargs):
            status_msg_edits.append(text)
        status_msg.edit_text = AsyncMock(side_effect=fake_edit_text)
        status_msg.delete = AsyncMock()

        with patch("bot.CURL_CFFI_AVAILABLE", False), \
             patch("aiohttp.TCPConnector", FakeRefusedConnector), \
             patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media:

            await bot.process_download_and_upload(
                raw_url=self.test_url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        # Assert exactly 1 attempt (NO unverified retry)
        self.assertEqual(len(attempts_log), 1, f"Expected exactly 1 attempt, got {len(attempts_log)}")
        self.assertFalse(mock_send_media.called)
        self.assertEqual(len(replies), 0)
        self.assertTrue(any("Network Connection Error" in msg for msg in status_msg_edits),
                        f"Expected Network Connection Error, got: {status_msg_edits}")

    async def test_sslretry_at_most_one_retry_when_both_fail(self):
        """
        Verify that if the unverified retry ALSO fails, at most 1 unverified retry was attempted
        (total 2 attempts), and the failure is surfaced as today.
        """
        attempts_log = []

        class FakeAlwaysFailCertConnector(aiohttp.TCPConnector):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                attempts_log.append({
                    "attempt": len(attempts_log) + 1,
                    "ssl": self._ssl,
                })

            async def _create_connection(self, req, traces, timeout):
                key = req.connection_key
                raise aiohttp.ClientConnectorCertificateError(
                    key,
                    ssl.SSLCertVerificationError(
                        1,
                        "[SSL: CERTIFICATE_VERIFY_FAILED] persistent certificate error (_ssl.c:1016)"
                    )
                )

        user_msg = MagicMock()
        user_msg.chat.id = 1594244556
        user_msg.from_user.id = 1594244556
        replies = []
        user_msg.reply_text = AsyncMock(side_effect=lambda text, **kw: replies.append(text))

        status_msg = AsyncMock()
        status_msg_edits = []
        async def fake_edit_text(text, **kwargs):
            status_msg_edits.append(text)
        status_msg.edit_text = AsyncMock(side_effect=fake_edit_text)
        status_msg.delete = AsyncMock()

        with patch("bot.CURL_CFFI_AVAILABLE", False), \
             patch("aiohttp.TCPConnector", FakeAlwaysFailCertConnector), \
             patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media:

            await bot.process_download_and_upload(
                raw_url=self.test_url,
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        # Assert exactly 2 attempts (initial + 1 unverified retry)
        self.assertEqual(len(attempts_log), 2, f"Expected exactly 2 attempts, got {len(attempts_log)}")
        self.assertIsNot(attempts_log[0]["ssl"], False)
        self.assertIs(attempts_log[1]["ssl"], False)
        self.assertFalse(mock_send_media.called)
        self.assertEqual(len(replies), 0)
        self.assertTrue(any("Network Connection Error" in msg for msg in status_msg_edits))

    async def test_sslretry_curl_cffi_unverified_retry(self):
        """
        If curl_cffi is available, verify that when curl_cffi fails specifically on certificate verification,
        it retries with verify=False, succeeds, and adds the bilingual notice line to the success card.
        """
        if not bot.CURL_CFFI_AVAILABLE:
            self.skipTest("curl_cffi is not installed in this environment")

        from curl_cffi.requests.exceptions import CertificateVerifyError

        call_records = []

        class FakeCurlResponse:
            def __init__(self, data):
                self.status_code = 200
                self.headers = {"Content-Length": str(len(data)), "Content-Type": "application/pdf"}
                self.data = data
            async def aiter_content(self, chunk_size):
                yield self.data

        class FakeCurlSession:
            def __init__(self, impersonate="chrome124", allow_redirects=True, verify=True):
                self.impersonate = impersonate
                self.allow_redirects = allow_redirects
                self.verify = verify
                call_records.append({"verify": verify})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, headers=None, stream=True):
                if self.verify:
                    raise CertificateVerifyError("curl: (60) SSL certificate OpenSSL verify result: unable to get local issuer certificate")
                return FakeCurlResponse(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

        user_msg = MagicMock()
        user_msg.chat.id = 1594244556
        user_msg.from_user.id = 1594244556
        replies = []
        user_msg.reply_text = AsyncMock(side_effect=lambda text, **kw: replies.append(text))

        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        status_msg.delete = AsyncMock()

        with patch("bot.CURL_CFFI_AVAILABLE", True), \
             patch("bot.unrestrict_direct_link", new_callable=AsyncMock, side_effect=lambda u: u), \
             patch("bot.CurlAsyncSession", FakeCurlSession), \
             patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media, \
             self.assertLogs("bot", level="WARNING") as captured_logs:

            await bot.process_download_and_upload(
                raw_url="https://fs21.uploadrar.com:183/fake/file.pdf",
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

        # Assert exactly 2 curl session calls (first verify=True, second verify=False)
        self.assertEqual(len(call_records), 2, f"Expected 2 curl calls, got {call_records}")
        self.assertTrue(call_records[0]["verify"])
        self.assertFalse(call_records[1]["verify"])

        # Assert file was delivered and bilingual notice line is present
        self.assertTrue(mock_send_media.called)
        self.assertEqual(len(replies), 1)
        self.assertIn(bot.TLS_VERIFICATION_SKIPPED_NOTICE, replies[0])

        # Assert clear WARNING logged
        warning_logs = [log for log in captured_logs.output if "TLS certificate verification failed" in log]
        self.assertEqual(len(warning_logs), 1)
        self.assertIn("fs21.uploadrar.com:183", warning_logs[0])

if __name__ == "__main__":
    unittest.main()
