import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

class TestDashoff(unittest.TestCase):
    def test_start_keyboard_no_dashboard(self):
        # Admin start keyboard
        kb_admin = bot.make_start_keyboard(lang="ar", is_admin=True)
        all_cb = [btn.callback_data for row in kb_admin.inline_keyboard for btn in row]
        self.assertNotIn("btn_get_dashboard", all_cb)
        self.assertIn("btn_admin_panel", all_cb)
        self.assertIn("btn_god_panel", all_cb)
        self.assertIn("btn_history", all_cb)
        self.assertIn("btn_settings", all_cb)
        self.assertIn("btn_probe_info", all_cb)
        self.assertIn("btn_stats", all_cb)

        # Non-admin start keyboard
        kb_user = bot.make_start_keyboard(lang="ar", is_admin=False)
        all_cb_user = [btn.callback_data for row in kb_user.inline_keyboard for btn in row]
        self.assertNotIn("btn_get_dashboard", all_cb_user)
        self.assertNotIn("btn_admin_panel", all_cb_user)

    def test_admin_panel_callback_keyboard(self):
        # Read bot.py source around btn_admin_panel to check admin_kbd definition
        with open("bot.py", "r", encoding="utf-8") as f:
            src = f.read()

        self.assertNotIn("btn_get_dashboard", src)
        self.assertNotIn("dashboard_command", src)
        self.assertNotIn('BotCommand("dashboard"', src)

        # Confirm admin_kbd structure
        self.assertIn('admin_kbd = InlineKeyboardMarkup([\n                [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="btn_start")]\n            ])', src)

    def test_web_server_routes_preserved(self):
        with open("bot.py", "r", encoding="utf-8") as f:
            src = f.read()

        self.assertIn("async def handle_dashboard_view", src)
        self.assertIn("async def handle_dashboard_stats_api", src)
        self.assertIn("async def handle_dashboard_cancel_task_api", src)
        self.assertIn('app.router.add_get("/dashboard", handle_dashboard_view)', src)
        self.assertIn('app.router.add_get("/api/dashboard/stats", handle_dashboard_stats_api)', src)
        self.assertIn("get_or_create_dashboard_secret", src)

if __name__ == "__main__":
    unittest.main()
