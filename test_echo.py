import os
import sys
from dotenv import load_dotenv
from pyrogram import Client, filters

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

print(f"API_ID: {API_ID}")
print(f"API_HASH: {API_HASH}")
print(f"BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "BOT_TOKEN: None")

if not API_ID or not API_HASH or not BOT_TOKEN or API_ID == "12345678":
    print("❌ يرجى التأكد من وضع بياناتك الحقيقية في ملف .env أولاً!")
    sys.exit(1)

app = Client("test_session", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message()
async def echo(client, message):
    print(f"🔔 [تم الاستقبال]: {message.text or message.caption}")
    await message.reply_text(f"✅ البوت شغال وشغّل الاستجابة!\n\nنص الرسالة: {message.text or message.caption}")

print("🚀 جاري بدء الاختبار بـ app.run()...")
app.run()
