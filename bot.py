
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from user_manager import UserManager
from content_manager import ContentManager
from config import BOT_TOKEN, ADMIN_IDS, GROQ_API_KEY, groq_client, DATA_FILE, CONTENT_FILE
import asyncio
import os
import json
from datetime import datetime, timedelta

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة المديرين
user_manager = UserManager()
content_manager = ContentManager()

# دالة بدء البوت
async def start(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""

    user_manager.create_user(user_id, username, first_name, last_name)
    user_manager.update_user_activity(user_id)

    await update.message.reply_text(
        f"مرحباً بك يا {first_name}! أنا بوت تعلم اللغة الصينية. كيف يمكنني مساعدتك اليوم؟",
        reply_markup=main_menu_keyboard()
    )

# لوحة المفاتيح الرئيسية
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📚 الدروس", callback_data='lessons')],
        [InlineKeyboardButton("🧠 الاختبارات", callback_data='quizzes')],
        [InlineKeyboardButton("🗣️ عبارات شائعة", callback_data='phrases')],
        [InlineKeyboardButton("📊 لوحة المتصدرين", callback_data='leaderboard')],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

# معالج الأزرار المضمنة (الكولباك)
async def button_handler(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    user_manager.update_user_activity(user_id)

    await query.answer()

    if query.data == 'lessons':
        await show_lessons(query, context)
    elif query.data == 'quizzes':
        await show_quizzes(query, context)
    elif query.data == 'phrases':
        await show_phrases(query, context)
    elif query.data == 'leaderboard':
        await show_leaderboard(query, context)
    elif query.data == 'settings':
        await show_settings(query, context)
    elif query.data.startswith('lesson_'):
        lesson_id = query.data.split('_')[1]
        await show_lesson_detail(query, context, lesson_id)
    elif query.data.startswith('start_quiz_'):
        quiz_id = query.data.split('_')[2]
        await start_quiz(query, context, quiz_id)
    elif query.data.startswith('quiz_answer_'):
        quiz_id, question_index, answer_index = map(int, query.data.split('_')[2:])
        await process_quiz_answer(query, context, quiz_id, question_index, answer_index)
    elif query.data == 'back_to_main':
        await query.edit_message_text(
            f"أهلاً بك مرة أخرى! كيف يمكنني مساعدتك؟",
            reply_markup=main_menu_keyboard()
        )
    elif query.data == 'toggle_daily_reminder':
        await toggle_notification_setting(query, context, user_id, 'daily_reminder')
    elif query.data == 'toggle_streak_warning':
        await toggle_notification_setting(query, context, user_id, 'streak_warning')
    elif query.data == 'toggle_goal_achievement':
        await toggle_notification_setting(query, context, user_id, 'goal_achievement')
    elif query.data == 'toggle_weekly_report':
        await toggle_notification_setting(query, context, user_id, 'weekly_report')

# عرض الدروس
async def show_lessons(query, context):
    lessons = content_manager.get_all_lessons()
    if not lessons:
        await query.edit_message_text("لا توجد دروس متاحة حالياً.", reply_markup=back_to_main_keyboard())
        return

    keyboard = []
    for lesson_id, lesson_data in lessons.items():
        keyboard.append([InlineKeyboardButton(lesson_data['title'], callback_data=f'lesson_{lesson_id}')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("اختر درساً:", reply_markup=reply_markup)

# عرض تفاصيل الدرس
async def show_lesson_detail(query, context, lesson_id):
    lesson = content_manager.get_lesson(lesson_id)
    if not lesson:
        await query.edit_message_text("الدرس المطلوب غير موجود.", reply_markup=back_to_main_keyboard())
        return

    text = f"*📚 الدرس: {lesson['title']}*\n\n"
    text += f"{lesson['description']}\n\n"
    text += f"*{lesson['content']}*\n\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع للدروس", callback_data='lessons')]]
    if lesson.get('quiz_id'):
       keyboard.append([InlineKeyboardButton("🧠 ابدأ الاختبار", callback_data=f'start_quiz_{lesson["quiz_id"]}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# دالة مساعدة للعودة إلى القائمة الرئيسية
def back_to_main_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='back_to_main')]]
    return InlineKeyboardMarkup(keyboard)

# عرض الاختبارات
async def show_quizzes(query, context):
    quizzes = content_manager.get_all_quizzes()
    if not quizzes:
        await query.edit_message_text("لا توجد اختبارات متاحة حالياً.", reply_markup=back_to_main_keyboard())
        return

    keyboard = []
    for quiz_id, quiz_data in quizzes.items():
        keyboard.append([InlineKeyboardButton(quiz_data["title"], callback_data=f'start_quiz_{quiz_id}')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("اختر اختباراً:", reply_markup=reply_markup)

# بدء الاختبار
async def start_quiz(query, context, quiz_id):
    quiz = content_manager.get_quiz(quiz_id)
    if not quiz:
        await query.edit_message_text("الاختبار المطلوب غير موجود.", reply_markup=back_to_main_keyboard())
        return

    user_data = user_manager.get_user(query.from_user.id)
    user_data["temporary"]["current_quiz"] = quiz_id
    user_data["temporary"]["quiz_answers"] = []
    user_manager.save_data()

    await send_quiz_question(query, context, quiz_id, 0)

# إرسال سؤال الاختبار
async def send_quiz_question(query, context, quiz_id, question_index):
    quiz = content_manager.get_quiz(quiz_id)
    if not quiz or question_index >= len(quiz["questions"]):
        await end_quiz(query, context, quiz_id)
        return

    question_data = quiz["questions"][question_index]
    text = f"*🧠 سؤال {question_index + 1} من {len(quiz['questions'])}:*\n\n{question_data['question']}"

    keyboard = []
    for i, option in enumerate(question_data["options"]):
        keyboard.append([InlineKeyboardButton(option, callback_data=f'quiz_answer_{quiz_id}_{question_index}_{i}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# معالجة إجابة الاختبار
async def process_quiz_answer(query, context, quiz_id, question_index, answer_index):
    user_id = query.from_user.id
    user_data = user_manager.get_user(user_id)
    quiz = content_manager.get_quiz(quiz_id)

    if not user_data or not quiz or user_data["temporary"]["current_quiz"] != quiz_id:
        await query.edit_message_text("حدث خطأ في الاختبار. يرجى البدء من جديد.", reply_markup=back_to_main_keyboard())
        return

    correct_answer_index = quiz["questions"][question_index]["answer_index"]
    is_correct = (answer_index == correct_answer_index)
    user_data["temporary"]["quiz_answers"].append(is_correct)
    user_manager.save_data()

    next_question_index = question_index + 1
    await send_quiz_question(query, context, quiz_id, next_question_index)

# إنهاء الاختبار
async def end_quiz(query, context, quiz_id):
    user_id = query.from_user.id
    user_data = user_manager.get_user(user_id)
    quiz = content_manager.get_quiz(quiz_id)

    if not user_data or not quiz:
        await query.edit_message_text("حدث خطأ في إنهاء الاختبار.", reply_markup=back_to_main_keyboard())
        return

    total_questions = len(quiz["questions"])
    correct_answers = user_data["temporary"]["quiz_answers"].count(True)
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    text = f"*✅ لقد أكملت الاختبار '{quiz['title']}'!*\n\n"
    text += f"عدد الأسئلة الصحيحة: {correct_answers} من {total_questions}\n"
    text += f"درجتك: {score:.2f}%\n\n"

    # تحديث إحصائيات المستخدم
    user_data["stats"]["total_quizzes"] += 1
    user_data["stats"]["total_correct"] += correct_answers
    user_data["stats"]["total_wrong"] += (total_questions - correct_answers)
    user_data["stats"]["accuracy"] = (user_data["stats"]["total_correct"] / (user_data["stats"]["total_correct"] + user_data["stats"]["total_wrong"])) * 100
    
    # إضافة نقاط خبرة بناءً على الأداء
    xp_earned = correct_answers * 10  # 10 XP لكل إجابة صحيحة
    user_manager.add_xp(user_id, xp_earned, f"أكمل اختبار {quiz['title']}")

    user_data["temporary"]["current_quiz"] = None
    user_data["temporary"]["quiz_answers"] = []
    user_manager.save_data()

    await query.edit_message_text(text, reply_markup=back_to_main_keyboard(), parse_mode='Markdown')

# عرض العبارات الشائعة
async def show_phrases(query, context):
    phrase = content_manager.get_random_phrase()
    if not phrase:
        await query.edit_message_text("لا توجد عبارات شائعة متاحة حالياً.", reply_markup=back_to_main_keyboard())
        return

    text = f"*🗣️ عبارة عشوائية:*\n\n"
    text += f"الصينية: {phrase['text']}\n"
    text += f"الترجمة: {phrase['translation']}"

    keyboard = [
        [InlineKeyboardButton("🔄 عبارة أخرى", callback_data='phrases')],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# عرض لوحة المتصدرين
async def show_leaderboard(query, context):
    leaderboard_data = user_manager.get_leaderboard()
    if not leaderboard_data:
        await query.edit_message_text("لا توجد بيانات في لوحة المتصدرين حالياً.", reply_markup=back_to_main_keyboard())
        return

    text = "*📊 لوحة المتصدرين (أعلى 10)*\n\n"
    for i, entry in enumerate(leaderboard_data):
        username = entry["username"] or entry["first_name"] or f"مستخدم {entry['user_id']}"
        text += f"{i+1}. {username} - نقاط الخبرة: {entry['xp']} - السلسلة: {entry['streak']} أيام\n"

    await query.edit_message_text(text, reply_markup=back_to_main_keyboard(), parse_mode='Markdown')

# عرض الإعدادات
async def show_settings(query, context):
    user_id = query.from_user.id
    user_data = user_manager.get_user(user_id)

    if not user_data:
        await query.edit_message_text("تعذر تحميل إعدادات المستخدم.", reply_markup=back_to_main_keyboard())
        return

    notifications = user_data["notifications"]

    keyboard = [
        [InlineKeyboardButton(f"تذكير يومي: {'✅' if notifications.get('daily_reminder') else '❌'}", callback_data='toggle_daily_reminder')],
        [InlineKeyboardButton(f"تحذير السلسلة: {'✅' if notifications.get('streak_warning') else '❌'}", callback_data='toggle_streak_warning')],
        [InlineKeyboardButton(f"إنجاز الهدف: {'✅' if notifications.get('goal_achievement') else '❌'}", callback_data='toggle_goal_achievement')],
        [InlineKeyboardButton(f"تقرير أسبوعي: {'✅' if notifications.get('weekly_report') else '❌'}", callback_data='toggle_weekly_report')],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("إعدادات الإشعارات:", reply_markup=reply_markup)

# تبديل إعداد الإشعارات
async def toggle_notification_setting(query, context, user_id, setting_key):
    user_data = user_manager.get_user(user_id)
    if not user_data:
        await query.edit_message_text("تعذر تحديث الإعدادات.", reply_markup=back_to_main_keyboard())
        return

    current_value = user_data["notifications"].get(setting_key, True)
    user_manager.update_user_setting(user_id, f'notifications.{setting_key}' , not current_value)
    await query.answer(f"تم تحديث الإعداد: {setting_key}")
    await show_settings(query, context) # Refresh settings menu

# أوامر المشرفين
async def admin_stats(update: Update, context):
    user_id = update.effective_user.id
    if not user_manager.is_admin(user_id):
        await update.message.reply_text("ليس لديك صلاحية الوصول لهذا الأمر.")
        return
    
    analytics = user_manager.get_system_analytics()
    total_users = user_manager.get_total_users()
    active_today = user_manager.get_active_users_today()

    text = f"*📊 إحصائيات النظام: *\n\n"
    text += f"إجمالي المستخدمين: {total_users}\n"
    text += f"المستخدمون النشطون اليوم: {active_today}\n"
    text += f"إجمالي الدروس: {len(content_manager.get_all_lessons())}\n"
    text += f"إجمالي الاختبارات: {len(content_manager.get_all_quizzes())}\n"
    text += f"إجمالي الأرباح: {analytics.get('total_earnings', 0):.2f} $ (هذا مثال، قد لا يكون مفعلاً بالكامل)"

    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_add_lesson(update: Update, context):
    user_id = update.effective_user.id
    if not user_manager.is_admin(user_id):
        await update.message.reply_text("ليس لديك صلاحية الوصول لهذا الأمر.")
        return
    
    # مثال لإضافة درس (يجب أن يتم تطوير واجهة أفضل لهذا)
    # content_manager.add_lesson("lesson1", "التحيات", "تعلم التحيات الأساسية في اللغة الصينية", "محتوى الدرس هنا")
    await update.message.reply_text("هذه وظيفة إدارية. يرجى استخدام واجهة إدارية أو توفير البيانات بشكل منظم.")

async def admin_add_quiz(update: Update, context):
    user_id = update.effective_user.id
    if not user_manager.is_admin(user_id):
        await update.message.reply_text("ليس لديك صلاحية الوصول لهذا الأمر.")
        return
    
    # مثال لإضافة اختبار
    # questions = [
    #     {'question': 'ما معنى '你好'؟', 'options': ['مرحباً', 'وداعاً', 'شكراً'], 'answer_index': 0},
    #     {'question': 'ما معنى '谢谢'؟', 'options': ['نعم', 'لا', 'شكراً'], 'answer_index': 2}
    # ]
    # content_manager.add_quiz("quiz1", "اختبار التحيات", questions)
    await update.message.reply_text("هذه وظيفة إدارية. يرجى استخدام واجهة إدارية أو توفير البيانات بشكل منظم.")

# دالة main لتشغيل البوت
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("adminstats", admin_stats))
    application.add_handler(CommandHandler("addlesson", admin_add_lesson))
    application.add_handler(CommandHandler("addquiz", admin_add_quiz))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # تهيئة بعض المحتوى التجريبي إذا لم يكن موجوداً
    if not os.path.exists(CONTENT_FILE) or os.path.getsize(CONTENT_FILE) == 0:
        content_manager.add_lesson("intro", "مقدمة للغة الصينية", "تعلم أساسيات اللغة الصينية", "مرحباً بكم في عالم اللغة الصينية! ابدأ رحلتك بتعلم النغمات والحروف الأساسية.", quiz_id="quiz1")
        content_manager.add_quiz("quiz1", "اختبار المقدمة", [
            {'question': 'ما هو عدد النغمات في لغة الماندرين الصينية؟', 'options': ['3', '4', '5', '6'], 'answer_index': 1},
            {'question': 'ما معنى كلمة "你好" (nǐ hǎo)؟', 'options': ['شكراً', 'مع السلامة', 'مرحباً', 'آسف'], 'answer_index': 2}
        ])
        content_manager.add_phrase("phrase1", "你好", "مرحباً")
        content_manager.add_phrase("phrase2", "谢谢", "شكراً")
        content_manager.add_phrase("phrase3", "再见", "مع السلامة")
        content_manager.save_content()
        print("تم إضافة محتوى تجريبي.")
    
    main()

