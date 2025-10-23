
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
ADMIN_SECTION, ADMIN_TITLE, ADMIN_CONTENT, UPLOAD_FILE_SECTION, UPLOAD_FILE_RECEIVE = range(5)

# دالة مساعدة للعودة إلى القائمة الرئيسية
def back_to_main_keyboard():
    keyboard = [[InlineKeyboardButton("◀️ رجوع", callback_data='BACK')]]
    return InlineKeyboardMarkup(keyboard)

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

# دالة بدء البوت
async def start(update: Update, context):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""

    user_manager.create_user(user_id, update.effective_user.username, first_name, update.effective_user.last_name)
    user_manager.update_user_activity(user_id)

    await update.message.reply_text(
        f"مرحباً بك يا {first_name}! اختر قسمًا:",
        reply_markup=main_menu_keyboard(user_id)
    )

# معالج الأزرار المضمنة (الكولباك)
async def button_handler(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    user_manager.update_user_activity(user_id)

    await query.answer()

    data = query.data

    if data == 'BACK':
        await query.edit_message_text(
            "مرحبًا! اختر قسمًا:",
            reply_markup=main_menu_keyboard(user_id)
        )
    elif data.startswith("MENU_"):
        await handle_menu(query, context)
    elif data.startswith("SEC_"):
        await handle_section(query, context)
    elif data.startswith("SKIP_"):
        sec = data.split("_", 1)[1]
        await query.edit_message_text(f"قسم {sec}: قريبًا🔥", reply_markup=back_to_main_keyboard())
    
    # Fallback for old quiz buttons
    elif data.startswith('quiz_answer_'):
        await query.edit_message_text("وظيفة الاختبار غير مفعلة حاليًا في هذه الواجهة.", reply_markup=back_to_main_keyboard())

async def handle_menu(query, context):
    data = query.data
    user_id = query.from_user.id

    if data == "MENU_Admin":
        if not user_manager.is_admin(user_id):
            return await query.edit_message_text("⛔ للمشرفين فقط.", reply_markup=back_to_main_keyboard())
        kb = [
            [InlineKeyboardButton("➕ إضافة محتوى", callback_data="ADM_ADD")],
            [InlineKeyboardButton("📁 رفع ملف", callback_data="ADM_UP")],
            [InlineKeyboardButton("◀️ رجوع", callback_data="BACK")]
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
        kb.append([InlineKeyboardButton("◀️ رجوع", callback_data="BACK")])
        return await query.edit_message_text("اختر مستوى HSK:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        sec = data.split("_",1)[1]
        return await query.edit_message_text(f"قسم {sec}: قريبًا🔥", reply_markup=back_to_main_keyboard())

async def handle_section(query, context):
    sec = query.data.split("_",1)[1]
    kb = [[InlineKeyboardButton(f"محتوى تجريبي لـ {sec}", callback_data="SKIP_Content")]]
    kb.append([InlineKeyboardButton("◀️ رجوع", callback_data="BACK")])
    return await query.edit_message_text(f"قسم {sec}:", reply_markup=InlineKeyboardMarkup(kb))

# ----------------- Admin Handlers -----------------

async def cancel(update: Update, context) -> int:
    await update.message.reply_text("تم الإلغاء.", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ADM_ADD handlers (Keep simplified for now)
async def adm_add_start(update: Update, context):
    query = update.callback_query
    await query.answer()
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
    
    lesson_id = f"lesson{len(content_manager.get_all_lessons()) + 1}"
    content_manager.add_lesson(lesson_id, title, "", content)
    
    await update.message.reply_text(f"✅ أضيف إلى {section}: {title}", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ADM_UP handlers (New File Upload Conversation)
async def adm_up_start(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Get all available sections from content_manager (simplified to main menu items for now)
    sections = [
        ("HSK", "HSK"), ("القرآن", "Quran"), ("القاموس", "Dictionary"), 
        ("القصص", "Stories"), ("قواعد", "GrammarLessons"), ("مراجعة", "GrammarReview"),
        ("محادثات", "Dialogues"), ("Flashcards", "Flashcards"), ("كويزات", "Quizzes"), 
        ("صور", "PictureDictionary"), ("تطبيقات", "Apps")
    ]
    
    kb = []
    for name, key in sections:
        kb.append([InlineKeyboardButton(name, callback_data=f"UPSEC_{key}")])
    kb.append([InlineKeyboardButton("◀️ إلغاء", callback_data="cancel_upload")])

    await query.edit_message_text("اختر القسم الذي تريد رفع الملف إليه:", reply_markup=InlineKeyboardMarkup(kb))
    return UPLOAD_FILE_SECTION

async def select_upload_section(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_upload":
        await query.edit_message_text("تم إلغاء عملية رفع الملف.", reply_markup=main_menu_keyboard(query.from_user.id))
        return ConversationHandler.END

    section_key = query.data.split("_")[1]
    context.user_data["upload_section"] = section_key
    
    await query.edit_message_text(f"✅ تم اختيار القسم: *{section_key}*.\n\nالآن، أرسل الملف (صورة، مستند، صوت، إلخ) الذي تريد تخزينه.", parse_mode='Markdown')
    return UPLOAD_FILE_RECEIVE

async def receive_file_and_store(update: Update, context):
    message = update.effective_message
    user_id = message.from_user.id
    section_key = context.user_data.get("upload_section")

    file_data = None
    file_type = None
    file_name = None

    if message.document:
        file_data = message.document
        file_type = "document"
        file_name = message.document.file_name
    elif message.photo:
        file_data = message.photo[-1]
        file_type = "photo"
        file_name = f"photo_{file_data.file_unique_id}.jpg"
    elif message.video:
        file_data = message.video
        file_type = "video"
        file_name = message.video.file_name
    elif message.voice:
        file_data = message.voice
        file_type = "voice"
        file_name = f"voice_{file_data.file_unique_id}.ogg"
    elif message.audio:
        file_data = message.audio
        file_type = "audio"
        file_name = message.audio.file_name
    
    if file_data:
        # Store file data with the section key
        content_manager.add_file_data(
            file_id=file_data.file_id,
            file_type=file_type,
            file_name=file_name,
            user_id=user_id,
            section=section_key # Store the section key
        )
        
        await message.reply_text(
            f"✅ تم تخزين بيانات الملف بنجاح في قسم *{section_key}*!\n"
            f"النوع: {file_type}\n"
            f"الاسم: {file_name or 'غير متوفر'}\n"
            f"معرف الملف (File ID): `{file_data.file_id}`",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard(user_id)
        )
        return ConversationHandler.END
    else:
        await message.reply_text("لم يتم التعرف على نوع الملف. يرجى إرسال ملف صالح.")
        return UPLOAD_FILE_RECEIVE # Stay in this state until a file is received

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for adding content
    add_content_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_start, pattern='^ADM_ADD$')],
        states={
            ADMIN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_title)],
            ADMIN_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_content)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Conversation handler for file upload
    file_upload_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_up_start, pattern='^ADM_UP$')],
        states={
            UPLOAD_FILE_SECTION: [CallbackQueryHandler(select_upload_section, pattern='^UPSEC_')],
            UPLOAD_FILE_RECEIVE: [MessageHandler(filters.ATTACHMENT, receive_file_and_store)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(cancel, pattern='^cancel_upload$')],
    )

    application.add_handler(add_content_conv_handler)
    application.add_handler(file_upload_conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Note: The general MessageHandler(filters.ATTACHMENT) is removed, as file upload is now handled by ConversationHandler
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

