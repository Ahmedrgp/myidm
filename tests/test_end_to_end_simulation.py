import os
import sys
import asyncio
import sqlite3
from aiohttp import web
from unittest.mock import AsyncMock, MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

async def start_local_test_server():
    app = web.Application()

    async def handle_pdf(request):
        data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        return web.Response(body=data, content_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="document.pdf"'})

    async def handle_apk(request):
        with open("tests_apk/golden_v1.apk", "rb") as f:
            data = f.read()
        return web.Response(body=data, content_type="application/vnd.android.package-archive", headers={"Content-Disposition": 'attachment; filename="test_app.apk"'})

    app.router.add_get("/document.pdf", handle_pdf)
    app.router.add_get("/test_app.apk", handle_apk)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8899)
    await site.start()
    return runner

async def run_end_to_end_test():
    print("Starting local HTTP server on 127.0.0.1:8899...")
    runner = await start_local_test_server()

    try:
        with patch("bot.resilient_send_media", new_callable=AsyncMock) as mock_send_media:
            user_msg = MagicMock()
            user_msg.reply_document = AsyncMock()
            user_msg.reply_video = AsyncMock()
            replies = []
            async def reply_text_mock(text, **kwargs):
                replies.append(text)
                msg_mock = AsyncMock()
                msg_mock.edit_text = AsyncMock()
                msg_mock.delete = AsyncMock()
                return msg_mock
            user_msg.reply_text = AsyncMock(side_effect=reply_text_mock)
            user_msg.chat.id = 1594244556
            user_msg.from_user.id = 1594244556

            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.delete = AsyncMock()

            # 1. Non-APK download test (PDF)
            print("\n==========================================")
            print("1. Real HTTP Download of Non-APK (PDF)")
            print("==========================================")
            replies.clear()
            await bot.process_download_and_upload(
                raw_url="http://127.0.0.1:8899/document.pdf",
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            print(f"Non-APK produced {len(replies)} reply messages:")
            for idx, r in enumerate(replies):
                print(f"Reply {idx+1}:\n{r}\n")
            assert len(replies) == 1, f"Expected exactly 1 reply (success card), got {len(replies)}"
            assert "تمت العملية بنجاح" in replies[0]
            assert "🛡️ بطاقة فحص APK" not in replies[0]
            print("CONFIRMED: Exactly 1 success card sent. No APK inspection card.")

            # 2. APK fresh download test
            print("\n==========================================")
            print("2. Real HTTP Download of APK (golden_v1.apk - Fresh)")
            print("==========================================")
            # Clear previous inspection for android.appsecurity.cts.tinyapp to simulate fresh download
            conn = sqlite3.connect(bot.DB_FILE)
            conn.cursor().execute("DELETE FROM apk_inspections WHERE package = 'android.appsecurity.cts.tinyapp'")
            conn.commit()
            conn.close()

            replies.clear()
            await bot.process_download_and_upload(
                raw_url="http://127.0.0.1:8899/test_app.apk",
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )

            print(f"Fresh APK produced {len(replies)} reply messages:")
            for idx, r in enumerate(replies):
                print(f"Reply {idx+1}:\n{r}\n")
            assert len(replies) == 3, f"Expected exactly 3 replies (success card + inspection card + blitzverify block), got {len(replies)}"
            assert "تمت العملية بنجاح" in replies[0]
            assert "🛡️ بطاقة فحص APK | APK Inspection" in replies[1]
            assert "android.appsecurity.cts.tinyapp" in replies[1]
            assert "FB5DBD3C669AF9FC236C6991E6387B7F11FF0590997F22D0F5C74FF40E04FCA8" in replies[1]
            assert "BLITZVERIFY v1" in replies[2]
            assert "package: android.appsecurity.cts.tinyapp" in replies[2]
            assert "version_code: 10" in replies[2]
            assert "fb5dbd3c669af9fc236c6991e6387b7f11ff0590997f22d0f5c74ff40e04fca8" in replies[2]
            assert replies[2].startswith("```\n") and replies[2].endswith("\n```")
            print("CONFIRMED: Success card, inspection card, and BLITZVERIFY block sent in exact order.")

            # 3. Duplicate APK download test (paused before approval)
            print("\n==========================================")
            print("3. Real HTTP Download of SAME APK (Duplicate Detection - Paused)")
            print("==========================================")
            replies.clear()
            await bot.process_download_and_upload(
                raw_url="http://127.0.0.1:8899/test_app.apk",
                custom_name="",
                custom_caption="",
                status_msg=status_msg,
                user_msg=user_msg
            )
            print(f"Duplicate APK produced {len(replies)} reply messages:")
            for idx, r in enumerate(replies):
                print(f"Reply {idx+1}:\n{r}\n")
            assert len(replies) == 1, f"Expected 1 reply (duplicate warning card), got {len(replies)}"
            assert "تنبيه: تم تنزيل هذا التطبيق مسبقاً بنفس الإصدار!" in replies[0]
            assert "android.appsecurity.cts.tinyapp" in replies[0]
            assert "BLITZVERIFY v1" not in replies[0]
            print("CONFIRMED: Duplicate warning card sent with action buttons, upload halted, NO block sent.")

            # 4. Duplicate approval flow
            print("\n==========================================")
            print("4. Duplicate Approval Flow (run_approved_pending_upload)")
            print("==========================================")
            conn = sqlite3.connect(bot.DB_FILE)
            pending_row = conn.cursor().execute("SELECT id FROM pending_downloads WHERE status = 'pending' ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            assert pending_row is not None, "Pending download record not found in database!"
            pending_id = pending_row[0]

            replies.clear()
            await bot.run_approved_pending_upload(pending_id, user_msg)
            print(f"Approved upload produced {len(replies)} reply messages:")
            for idx, r in enumerate(replies):
                print(f"Reply {idx+1}:\n{r}\n")
            # The approval flow sends an initial status message, then success card, and ends with [inspection card, block]
            assert "🛡️ بطاقة فحص APK | APK Inspection" in replies[-2]
            assert "BLITZVERIFY v1" in replies[-1]
            assert "package: android.appsecurity.cts.tinyapp" in replies[-1]
            assert replies[-1].startswith("```\n") and replies[-1].endswith("\n```")
            print("CONFIRMED: Approved duplicate flow ends with inspection card and BLITZVERIFY block.")

            print("\nALL END-TO-END HTTP DOWNLOAD FLOWS PASSED PERFECTLY!")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())
