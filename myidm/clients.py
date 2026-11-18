import logging

from pyrogram import Client

import myidm  # noqa: F401
from myidm import config as cfg  # noqa: F401

logger = logging.getLogger("bot.clients")

bot: Client | None = None
user_bot: Client | None = None


def register_clients(bot_client: Client | None, user_bot_client: Client | None = None) -> None:
    global bot, user_bot
    bot = bot_client
    user_bot = user_bot_client


def get_uploader_client():
    if user_bot and getattr(user_bot, "is_connected", False):
        return user_bot
    return bot
