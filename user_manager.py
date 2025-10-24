import json
import threading
from datetime import datetime, timedelta
from config import *

class UserManager:
    def __init__(self):
        self.data = self.load_data()
        self.lock = threading.Lock()
        # self.setup_cleanup_job() # Temporarily disabled until implemented

    def setup_cleanup_job(self):
        pass # Placeholder for cleanup job setup
    
    def load_data(self):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "users": {},
                "admins": ADMIN_IDS,
                "leaderboard": {
                    "daily": {},
                    "weekly": {},
                    "monthly": {},
                    "all_time": {}
                },
                "notifications": {},
                "analytics": {
                    "total_users": 0,
                    "active_today": 0,
                    "total_lessons": 0,
                    "total_quizzes": 0,
                    "user_growth": []
                },
                "system": {
                    "last_backup": None,
                    "last_cleanup": None,
                    "total_earnings": 0
                }
            }
    
    def save_data(self):
        with self.lock:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def backup_data(self):
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "data": self.data
        }
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        self.data["system"]["last_backup"] = datetime.now().isoformat()
        self.save_data()
    
    def create_user(self, user_id, username="", first_name="", last_name=""):
        user_id = str(user_id)
        
        if user_id in self.data["users"]:
            return self.data["users"][user_id]
        
        if len(self.data["users"]) >= MAX_USERS:
            self.cleanup_inactive_users()
        
        user_data = {
            "info": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "join_date": datetime.now().isoformat(),
                "language": "ar",
                "is_premium": False
            },
            "learning": {
                "level": "مبتدئ",
                "current_streak": 0,
                "longest_streak": 0,
                "total_xp": 0,
                "daily_goal": 3,
                "lessons_today": 0,
                "last_activity": datetime.now().isoformat()
            },
            "progress": {
                "completed_lessons": [],
                "completed_quizzes": [],
                "weak_areas": ["المفردات", "القواعد"],
                "strong_areas": [],
                "achievements": []
            },
            "stats": {
                "total_days": 1,
                "total_lessons": 0,
                "total_quizzes": 0,
                "total_correct": 0,
                "total_wrong": 0,
                "accuracy": 0
            },
            "notifications": {
                "daily_reminder": True,
                "streak_warning": True,
                "goal_achievement": True,
                "weekly_report": True,
                "last_notification": None
            },
            "temporary": {
                "current_lesson": None,
                "current_quiz": None,
                "quiz_answers": [],
                "waiting_for": None
            }
        }
        
        self.data["users"][user_id] = user_data
        self.data["analytics"]["total_users"] += 1
        self.update_user_growth()
        self.save_data()
        return user_data
    
    def get_user(self, user_id):
        user_id = str(user_id)
        return self.data["users"].get(user_id)
    
    def update_user_activity(self, user_id):
        user_data = self.get_user(user_id)
        if not user_data:
            return
        
        # التأكد من وجود الهياكل الأساسية
        if 'learning' not in user_data:
            user_data['learning'] = {}
        if 'stats' not in user_data:
            user_data['stats'] = {}
        
        # تهيئة الحقول المطلوبة إذا لم تكن موجودة
        user_data['learning'].setdefault('last_activity', datetime.now().isoformat())
        user_data['learning'].setdefault('current_streak', 0)
        user_data['learning'].setdefault('longest_streak', 0)
        user_data['learning'].setdefault('lessons_today', 0)
        user_data['stats'].setdefault('total_days', 1)
        
        now = datetime.now()
        today = now.date().isoformat()
        last_activity = datetime.fromisoformat(user_data['learning']['last_activity']).date().isoformat()
        
        # تحديث السلسلة والأيام
        if today != last_activity:
            if (now - datetime.fromisoformat(user_data['learning']['last_activity'])).days == 1:
                user_data['learning']['current_streak'] += 1
                user_data['learning']['longest_streak'] = max(
                    user_data['learning']['longest_streak'],
                    user_data['learning']['current_streak']
                )
            else:
                user_data['learning']['current_streak'] = 1
            
            user_data['learning']['lessons_today'] = 0
            user_data['stats']['total_days'] += 1
        
        user_data['learning']['last_activity'] = now.isoformat()
        self.update_leaderboard(user_id)
        self.save_data()
    
    def add_xp(self, user_id, xp_amount, reason=""):
        user_data = self.get_user(user_id)
        if not user_data:
            return
        
        # التأكد من وجود الحقول المطلوبة
        user_data['learning'].setdefault('total_xp', 0)
        user_data['learning'].setdefault('lessons_today', 0)
        user_data['learning'].setdefault('daily_goal', 3)
        
        user_data['learning']['total_xp'] += xp_amount
        user_data['learning']['lessons_today'] += 1
        
        # إشعار تحقيق الهدف اليومي
        if user_data['learning']['lessons_today'] >= user_data['learning']['daily_goal']:
            self.send_notification(user_id, "goal_achieved", {
                "goal": user_data['learning']['daily_goal'],
                "completed": user_data['learning']['lessons_today']
            })
        
        self.update_leaderboard(user_id)
        self.save_data()
    
    def update_leaderboard(self, user_id):
        user_data = self.get_user(user_id)
        if not user_data:
            return
        
        # التأكد من وجود الحقول المطلوبة
        user_data['learning'].setdefault('total_xp', 0)
        user_data['learning'].setdefault('current_streak', 0)
        user_data['stats'].setdefault('total_lessons', 0)
        user_data['stats'].setdefault('accuracy', 0)
        
        xp = user_data['learning']['total_xp']
        streak = user_data['learning']['current_streak']
        
        # تحديث جميع لوحات المتصدرين
        timeframes = ["daily", "weekly", "monthly", "all_time"]
        for timeframe in timeframes:
            if user_id not in self.data["leaderboard"][timeframe]:
                self.data["leaderboard"][timeframe][user_id] = {
                    "xp": 0,
                    "streak": 0,
                    "lessons": 0,
                    "accuracy": 0
                }
            
            self.data["leaderboard"][timeframe][user_id].update({
                "xp": xp,
                "streak": streak,
                "lessons": user_data['stats']['total_lessons'],
                "accuracy": user_data['stats']['accuracy']
            })
        
        self.cleanup_leaderboard()
        self.save_data()
    
    def cleanup_leaderboard(self):
        """تنظيف لوحة المتصدرين من المستخدمين المحذوفين"""
        for timeframe in self.data["leaderboard"]:
            users_to_remove = []
            for user_id in self.data["leaderboard"][timeframe]:
                if user_id not in self.data["users"]:
                    users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                del self.data["leaderboard"][timeframe][user_id]
    
    def get_leaderboard(self, timeframe="all_time", limit=10):
        if timeframe not in self.data["leaderboard"]:
            return []
        
        leaderboard_data = []
        for user_id, data in self.data["leaderboard"][timeframe].items():
            user_info = self.get_user(user_id)
            if user_info:
                leaderboard_data.append({
                    "user_id": user_id,
                    "username": user_info['info'].get('username', 'مستخدم'),
                    "first_name": user_info['info'].get('first_name', ''),
                    "xp": data['xp'],
                    "streak": data['streak'],
                    "lessons": data['lessons'],
                    "accuracy": data['accuracy']
                })
        
        # ترتيب حسب XP
        leaderboard_data.sort(key=lambda x: x['xp'], reverse=True)
        return leaderboard_data[:limit]
    
    def send_notification(self, user_id, notification_type, data=None):
        user_data = self.get_user(user_id)
        if not user_data or not user_data['notifications'].get(notification_type, True):
            return
        
        notifications = {
            "daily_reminder": "⏰ تذكر مذاكرة الصينية اليوم! حافظ على سلسلتك 🔥",
            "streak_warning": "⚠️ سلسلتك في خطر! واصل التعلم للحفاظ عليها",
            "goal_achieved": f"🎉 لقد حققت هدفك اليومي! أكملت {data['completed']} نشاط",
            "level_up": f"🚀 تهانينا! لقد تقدمت لمستوى {data['new_level']}",
            "weekly_report": f"📊 تقريرك الأسبوعي: {data['lessons']} درس، {data['xp']} نقطة",
            "new_achievement": f"🏆 فزت بإنجاز جديد: {data['achievement']}"
        }
        
        if notification_type in notifications:
            # تخزين الإشعار لإرساله لاحقاً
            if user_id not in self.data["notifications"]:
                self.data["notifications"][user_id] = []
            
            self.data["notifications"][user_id].append({
                "type": notification_type,
                "message": notifications[notification_type],
                "timestamp": datetime.now().isoformat(),
                "read": False
            })
            self.save_data()

    def get_unread_notifications(self, user_id):
        user_data = self.get_user(user_id)
        if not user_data or user_id not in self.data["notifications"]:
            return []
        
        unread_notifications = [n for n in self.data["notifications"][user_id] if not n["read"]]
        return unread_notifications

    def mark_notifications_as_read(self, user_id):
        if user_id in self.data["notifications"]:
            for n in self.data["notifications"][user_id]:
                n["read"] = True
            self.save_data()

    def get_admin_ids(self):
        return self.data["admins"]

    def is_admin(self, user_id):
        return user_id in self.data["admins"]

    def add_admin(self, user_id):
        if user_id not in self.data["admins"]:
            self.data["admins"].append(user_id)
            self.save_data()
            return True
        return False

    def remove_admin(self, user_id):
        if user_id in self.data["admins"]:
            self.data["admins"].remove(user_id)
            self.save_data()
            return True
        return False

    def update_user_setting(self, user_id, setting_key, setting_value):
        user_data = self.get_user(user_id)
        if not user_data:
            return False
        
        keys = setting_key.split('.')
        current_dict = user_data
        for i, key in enumerate(keys):
            if key not in current_dict:
                return False # Key path does not exist
            if i == len(keys) - 1:
                current_dict[key] = setting_value
            else:
                current_dict = current_dict[key]
        self.save_data()
        return True

    def get_total_users(self):
        return self.data["analytics"]["total_users"]

    def get_active_users_today(self):
        today = datetime.now().date().isoformat()
        active_today = 0
        for user_id, user_data in self.data["users"].items():
            last_activity_str = user_data['learning']['last_activity']
            if last_activity_str:
                last_activity_date = datetime.fromisoformat(last_activity_str).date().isoformat()
                if last_activity_date == today:
                    active_today += 1
        self.data["analytics"]["active_today"] = active_today
        self.save_data()
        return active_today

    def update_user_growth(self):
        today = datetime.now().date().isoformat()
        growth_data = self.data["analytics"]["user_growth"]
        
        if not growth_data or growth_data[-1]["date"] != today:
            growth_data.append({"date": today, "new_users": 0, "total_users": self.data["analytics"]["total_users"]})
        
        # Update new users for today (this logic might need refinement based on how new users are tracked)
        # For now, let's assume new users are added only when create_user is called.
        # This method is called after create_user, so we can increment new_users for today.
        if len(growth_data) > 0 and growth_data[-1]["date"] == today:
            growth_data[-1]["new_users"] = len(self.data["users"]) - (growth_data[-2]["total_users"] if len(growth_data) > 1 else 0)
            growth_data[-1]["total_users"] = self.data["analytics"]["total_users"]
        
        self.save_data()

    def get_user_growth_data(self, days=30):
        return self.data["analytics"]["user_growth"][-days:]

    def cleanup_inactive_users(self):
        now = datetime.now()
        inactive_threshold = now - timedelta(days=CLEANUP_INTERVAL)
        users_to_remove = []
        for user_id, user_data in self.data["users"].items():
            last_activity = datetime.fromisoformat(user_data['learning']['last_activity'])
            if last_activity < inactive_threshold:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.data["users"][user_id]
            # Optionally, remove from leaderboard and notifications as well
            if user_id in self.data["notifications"]:
                del self.data["notifications"][user_id]
            for timeframe in self.data["leaderboard"]:
                if user_id in self.data["leaderboard"][timeframe]:
                    del self.data["leaderboard"][timeframe][user_id]
        
        if users_to_remove:
            self.data["analytics"]["total_users"] -= len(users_to_remove)
            self.save_data()
            self.update_user_growth()

    def setup_cleanup_job(self):
        # This would typically be a scheduled task, not run directly in __init__
        # For a simple bot, you might run it on startup or periodically.
        # For demonstration, let's just call it once here.
        # In a real bot, you'd use a library like APScheduler.
        pass # self.cleanup_inactive_users() # Don't run on init, needs proper scheduling

    def get_user_stats(self, user_id):
        user_data = self.get_user(user_id)
        if user_data:
            return user_data["stats"]
        return None

    def update_user_stats(self, user_id, stat_key, value):
        user_data = self.get_user(user_id)
        if user_data and stat_key in user_data["stats"]:
            user_data["stats"][stat_key] = value
            self.save_data()
            return True
        return False

    def get_user_learning_progress(self, user_id):
        user_data = self.get_user(user_id)
        if user_data:
            return user_data["learning"]
        return None

    def update_user_learning_progress(self, user_id, progress_key, value):
        user_data = self.get_user(user_id)
        if user_data and progress_key in user_data["learning"]:
            user_data["learning"][progress_key] = value
            self.save_data()
            return True
        return False

    def get_user_achievements(self, user_id):
        user_data = self.get_user(user_id)
        if user_data:
            return user_data["progress"]["achievements"]
        return []

    def add_achievement(self, user_id, achievement_name):
        user_data = self.get_user(user_id)
        if user_data and achievement_name not in user_data["progress"]["achievements"]:
            user_data["progress"]["achievements"].append(achievement_name)
            self.send_notification(user_id, "new_achievement", {"achievement": achievement_name})
            self.save_data()
            return True
        return False

    def get_system_analytics(self):
        return self.data["analytics"]

    def update_total_earnings(self, amount):
        self.data["system"]["total_earnings"] += amount
        self.save_data()

    def get_total_earnings(self):
        return self.data["system"]["total_earnings"]
