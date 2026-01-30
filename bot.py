import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Bot token Railway / hosting me environment variable se aayega
TOKEN = os.getenv("8505028242:AAGmGE8TO7_k4u9ozBBKhS014DdgMGme26M")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello 👋\nDV Bot is online and working 24×7 🚀"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - Start bot\n/help - Help menu"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
