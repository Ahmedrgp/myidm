import os
import sys

# ملف توجيهي طوارئ لتشغيل bot.py تلقائياً في حال بحث Render عن main.py
if __name__ == "__main__":
    os.execv(sys.executable, [sys.executable, "bot.py"])
