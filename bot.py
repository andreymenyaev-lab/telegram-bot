from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = "8756792735:AAHWh-YsjaiYursW9eggoP_zfxzlbo6-Nts"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет! Я бот 😊 Напиши что-нибудь")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        text = update.message.text
        await update.message.reply_text("Ты написал: " + text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
