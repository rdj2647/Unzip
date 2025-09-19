import os
import zipfile
import rarfile
import py7zr
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes,
    filters, CommandHandler
)

# Bot token environment variable se lega
TOKEN = os.getenv("BOT_TOKEN", "")
DOWNLOAD_PATH = "downloads"

# Password requests ke liye
pending_passwords = {}

os.makedirs(DOWNLOAD_PATH, exist_ok=True)


async def handle_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    filename = document.file_name.lower()

    if not (filename.endswith(".zip") or filename.endswith(".rar") or filename.endswith(".7z")):
        await update.message.reply_text("❌ Sirf .zip, .rar, aur .7z files supported hain.")
        return

    # File download
    file = await context.bot.get_file(document.file_id)
    file_path = os.path.join(DOWNLOAD_PATH, document.file_name)
    await file.download_to_drive(file_path)

    ext = filename.rsplit(".", 1)[-1]
    extract_path = os.path.join(DOWNLOAD_PATH, filename.rsplit(".", 1)[0])
    os.makedirs(extract_path, exist_ok=True)

    try:
        # Try extraction without password
        if ext == "zip":
            with zipfile.ZipFile(file_path, "r") as archive:
                try:
                    archive.extractall(extract_path)
                except RuntimeError:
                    pending_passwords[update.effective_user.id] = {
                        "file_path": file_path, "ext": ext, "extract_path": extract_path
                    }
                    await update.message.reply_text("🔒 Yeh ZIP file password protected hai. Password bhejo:")
                    return

        elif ext == "rar":
            with rarfile.RarFile(file_path, "r") as archive:
                try:
                    archive.extractall(extract_path)
                except rarfile.BadRarFile:
                    pending_passwords[update.effective_user.id] = {
                        "file_path": file_path, "ext": ext, "extract_path": extract_path
                    }
                    await update.message.reply_text("🔒 Yeh RAR file password protected hai. Password bhejo:")
                    return

        elif ext == "7z":
            try:
                with py7zr.SevenZipFile(file_path, "r") as archive:
                    archive.extractall(extract_path)
            except py7zr.Bad7zFile:
                pending_passwords[update.effective_user.id] = {
                    "file_path": file_path, "ext": ext, "extract_path": extract_path
                }
                await update.message.reply_text("🔒 Yeh 7Z file password protected hai. Password bhejo:")
                return

        # Send extracted files
        await send_files(update, context, extract_path)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Extraction Error: {e}")


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_passwords:
        return

    password = update.message.text.strip().encode("utf-8")
    info = pending_passwords.pop(user_id)
    file_path, ext, extract_path = info["file_path"], info["ext"], info["extract_path"]

    try:
        if ext == "zip":
            with zipfile.ZipFile(file_path, "r") as archive:
                archive.extractall(extract_path, pwd=password)

        elif ext == "rar":
            with rarfile.RarFile(file_path, "r") as archive:
                archive.extractall(extract_path, pwd=password)

        elif ext == "7z":
            with py7zr.SevenZipFile(file_path, "r", password=password.decode("utf-8")) as archive:
                archive.extractall(extract_path)

        await send_files(update, context, extract_path)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Wrong password ya extraction error: {e}")


async def send_files(update: Update, context: ContextTypes.DEFAULT_TYPE, extract_path: str):
    # Walk through all extracted files
    for root, dirs, files in os.walk(extract_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=open(fpath, "rb"),
                    filename=fname
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ File {fname} bhejne mein error: {e}")

    await update.message.reply_text("✅ Saare files extract karke bhej diye gaye.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 Mujhe .zip, .rar ya .7z file bhejo. Agar file password protected hogi to main tumse password maangunga."
    )


def main():
    if not TOKEN:
        print("❌ BOT_TOKEN environment variable missing!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_archive))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password))

    print("🤖 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
