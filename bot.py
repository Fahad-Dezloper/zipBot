import os
import zipfile
from dotenv import load_dotenv
import asyncio
from telegram import Update, PhotoSize, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from concurrent.futures import ThreadPoolExecutor


load_dotenv()  # Load environment variables from .env file


TEMP_PATH = "./temp/"
if not os.path.exists(TEMP_PATH):
    os.makedirs(TEMP_PATH)

# Dictionary to store user sessions and file paths
user_sessions = {}

# Conversation states
SET_NAME = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_sessions[user_id] = []

    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/setname"), KeyboardButton("/zip")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Session started. You can now send documents, videos, or images. Use the options below:",
        reply_markup=reply_markup
    )

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("Please start a session with /start first.")
        return ConversationHandler.END

    await update.message.reply_text("Please provide a name for the ZIP file.")
    return SET_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("Please start a session with /start first.")
        return ConversationHandler.END

    zip_name = update.message.text
    user_sessions[user_id].append("_zip_name:" + zip_name)
    await update.message.reply_text(f"ZIP file name set to: {zip_name}")

    return ConversationHandler.END

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("Please start a session with /start first.")
        return

    if update.message.document:
        document = update.message.document
        file_path = os.path.join(TEMP_PATH, document.file_name)
        new_file = await context.bot.get_file(document.file_id)
        await new_file.download_to_drive(file_path)
        user_sessions[user_id].append(file_path)
        await update.message.reply_text(f"Document received and stored! ({len(user_sessions[user_id])} files stored)")

async def create_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id]:
        await update.message.reply_text("You have no files to zip. Please send some documents, videos, or images first.")
        return

    zip_name = "files.zip"
    session_files = user_sessions[user_id]
    for item in session_files:
        if item.startswith("_zip_name:"):
            zip_name = item.split(":")[1] + ".zip"
            session_files.remove(item)
            break

    zip_path = os.path.join(TEMP_PATH, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in session_files:
            zipf.write(file_path, os.path.basename(file_path))

    await context.bot.send_document(chat_id=update.message.chat_id, document=open(zip_path, 'rb'))

    # Clean up local files
    os.remove(zip_path)
    for file_path in session_files:
        os.remove(file_path)
    
    del user_sessions[user_id]
    await update.message.reply_text(f"ZIP file '{zip_name}' created and sent!")

def main():
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    application.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setname", set_name)],
        states={
            SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[],
    )
    application.add_handler(conv_handler)

    application.add_handler(CommandHandler("zip", create_zip))
    
    file_handler = MessageHandler(filters.Document.ALL, handle_document)
    application.add_handler(file_handler)

    application.run_polling()

if __name__ == '__main__':
    main()