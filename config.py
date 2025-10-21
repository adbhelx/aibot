import os
from groq import Groq
from datetime import datetime, timedelta

# المفاتيح الأساسية
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_IDS = [953696547, 7942066919]  # أضف أي دي المشرفين هنا

# تهيئة Groq (سيتم تهيئته في bot.py بناءً على توفر المفتاح)
groq_client = None

# المسارات
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
BACKUP_FILE = "backup.json"

# إعدادات النظام
MAX_USERS = 1000
BACKUP_INTERVAL = 24  # ساعات
CLEANUP_INTERVAL = 7  # أيام للمستخدمين غير النشطين

# إعدادات التبيهات
NOTIFICATION_SETTINGS = {
    "daily_reminder": True,
    "streak_warning": True,
    "goal_achievement": True,
    "weekly_report": True
}

