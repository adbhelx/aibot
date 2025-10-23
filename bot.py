
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
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

# حالات المحادثة للمشرفين
ADMIN_SECTION, ADMIN_TITLE, ADMIN_CONTENT, UPLOAD_FILE = range(4)

# دالة معالج الرسائل التي تحتوي على ملفات
async def handle_file_message(update: Update, context):
    message = update.effective_message
    user_id = message.from_user.id

    if not user_manager.is_admin(user_id):
        await message.reply_text("❌ ليس لديك صلاحية المشرف لرفع وتخزين الملفات.")
        return

    file_data = None
    file_type = None
    file_name = None

    if message.document:
        file_data = message.document
        file_type = "document"
        file_name = file_data.file_name
    elif message.photo:
        file_data = message.photo[-1]
        file_type = "photo"
        file_name = f"photo_{file_data.file_unique_id}.jpg"
    elif message.video:
        file_data = message.video
        file_type = "video"
        file_name = file_data.file_name
    elif message.voice:
        file_data = message.voice
        file_type = "voice"
        file_name = f"voice_{file_data.file_unique_id}.ogg"
    elif message.audio:
        file_data = message.audio
        file_type = "audio"
        file_name = file_data.file_name
    
    if file_data:
        content_manager.add_file_data(
            file_id=file_data.file_id,
            file_type=file_type,
            file_name=file_name,
            user_id=user_id
        )
        
        await message.reply_text(
            f"✅ تم تخزين بيانات الملف بنجاح!\n"
            f"النوع: {file_type}\n"
            f"الاسم: {file_name or 'غير متوفر'}\n"
            f"معرف الملف (File ID): `{file_data.file_id}`",
            parse_mode='Markdown'
        )
    else:
        await message.reply_text("لم يتم التعرف على نوع الملف.")

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
        reply_markup=main_menu_keyboard(user_id)
    )

# لوحة المفاتيح الرئيسية
def main_menu_keyboard(user_id):
    items = [
        ("📚 HSK", "MENU_HSK"),
        ("🕌 القرآن", "MENU_Quran"),
        ("🗂️ القاموس", "MENU_Dictionary"),
        ("📖 القصص", "MENU_Stories"),
        ("🔤 قواعد", "MENU_GrammarLessons"),
        ("📑 مراجعة", "MENU_GrammarReview"),
        ("💬 محادثات", "MENU_Dialogues"),
        ("🃏 Flashcards", "MENU_Flashcards"),
        ("❓ كويزات", "MENU_Quizzes"),
        ("📷 معجم صور", "MENU_PictureDictionary"),
        ("📱 التطبيقات", "MENU_Apps"),
    ]
    if user_manager.is_admin(user_id):
        items.append(("⚙️ Admin", "MENU_Admin"))

    kb, row = [], []
    for i, (t, c) in enumerate(items, 1):
        row.append(InlineKeyboardButton(t, callback_data=c))
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb)

# معالج الأزرار المضمنة (الكولباك)
async def button_handler(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    user_manager.update_user_activity(user_id)

    await query.answer()

    data = query.data

    if data == 'back_to_main':
        await query.edit_message_text(
            f"أهلاً بك مرة أخرى! كيف يمكنني مساعدتك؟",
            reply_markup=main_menu_keyboard(user_id)
        )
    elif data.startswith("MENU_"):
        await handle_menu(query, context)
    elif data.startswith("SEC_"):
        await handle_section(query, context)
    else:
        # Fallback to old handlers for now
        if data == 'lessons':
            await show_lessons(query, context)
        elif data == 'quizzes':
            await show_quizzes(query, context)
        elif data == 'phrases':
            await show_phrases(query, context)
        elif data == 'leaderboard':
            await show_leaderboard(query, context)
        elif data == 'settings':
            await show_settings(query, context)
        elif data.startswith('lesson_'):
            lesson_id = data.split('_')[1]
            await show_lesson_detail(query, context, lesson_id)
        elif data.startswith('start_quiz_'):
            quiz_id = data.split('_')[1]
            await start_quiz(query, context, quiz_id)
        elif data.startswith('quiz_answer_'):
            _, quiz_id, question_index, answer_index = data.split('_')
            await process_quiz_answer(query, context, quiz_id, int(question_index), int(answer_index))

async def handle_menu(query, context):
    data = query.data
    user_id = query.from_user.id

    if data == "MENU_Admin":
        if not user_manager.is_admin(user_id):
            return await query.edit_message_text("⛔ للمشرفين فقط.")
        kb = [
            [InlineKeyboardButton("➕ إضافة", callback_data="ADM_ADD")],
            [InlineKeyboardButton("📝 استعراض", callback_data="ADM_VIEW")],
            [InlineKeyboardButton("❌ حذف", callback_data="ADM_DEL")],
            [InlineKeyboardButton("📁 رفع ملف", callback_data="ADM_UP")],
            [InlineKeyboardButton("◀️ رجوع", callback_data="back_to_main")]
        ]
        return await query.edit_message_text("لوحة المشرف:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "MENU_HSK":
        kb, row = [], []
        for i in range(1, 7):
            row.append(InlineKeyboardButton(f"HSK{i}", callback_data=f"SEC_HSK{i}"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        kb.append([InlineKeyboardButton("◀️ رجوع", callback_data="back_to_main")])
        return await query.edit_message_text("اختر مستوى HSK:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        sec = data.split("_",1)[1]
        return await query.edit_message_text(f"{sec}: قريبًا🔥", reply_markup=back_to_main_keyboard())

async def handle_section(query, context):
    sec = query.data.split("_",1)[1]
    items = content_manager.get_all_lessons() # Simplified for now
    kb, row = [], []
    for lesson_id, lesson_data in items.items():
        row.append(InlineKeyboardButton(lesson_data['title'], callback_data=f"lesson_{lesson_id}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("◀️ رجوع", callback_data="back_to_main")])
    return await query.edit_message_text(f"قسم {sec}:", reply_markup=InlineKeyboardMarkup(kb))

# ... (Keep all the old functions like show_lessons, show_quizzes, etc.)

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

    xp_earned = correct_answers * 10
    user_manager.add_xp(user_id, xp_earned, f"أكمل اختبار {quiz['title']}")

    user_data["temporary"]["current_quiz"] = None
    user_data["temporary"]["quiz_answers"] = []
    user_manager.save_data()

    await query.edit_message_text(text, reply_markup=back_to_main_keyboard(), parse_mode='Markdown')


# ... (Other functions like show_phrases, show_leaderboard, show_settings remain the same)

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


# ... (Admin Conversation Handler functions)

async def adm_add_start(update: Update, context):
    query = update.callback_query
    await query.answer()
    # Simplified for now, we'll just allow adding lessons
    context.user_data["section"] = "lessons"
    await query.edit_message_text("✏️ أرسل عنوان الدرس:")
    return ADMIN_TITLE

async def adm_add_title(update: Update, context):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("🌐 أرسل محتوى الدرس:")
    return ADMIN_CONTENT

async def adm_add_content(update: Update, context):
    section = context.user_data["section"]
    title = context.user_data["title"]
    content = update.message.text.strip()
    
    # Simplified: generate a new lesson ID
    lesson_id = f"lesson{len(content_manager.get_all_lessons()) + 1}"
    content_manager.add_lesson(lesson_id, title, "", content)
    
    await update.message.reply_text(f"✅ أضيف إلى {section}: {title}")
    return ConversationHandler.END

async def cancel(update: Update, context) -> int:
    await update.message.reply_text("تم الإلغاء.", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for admin functions
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_start, pattern='^ADM_ADD$')],
        states={
            ADMIN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_title)],
            ADMIN_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_content)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(admin_conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ATTACHMENT, handle_file_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

