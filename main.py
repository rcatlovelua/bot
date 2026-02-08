import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# bothost обычно кладёт токен сюда
TOKEN = (
  os.getenv("API_TOKEN")
)

if not TOKEN:
    raise RuntimeError("Токен бота не найден в переменных окружения")

IMAGE_URL = "https://example.com/image.png"

TEXT = (
    "Первая строка\n"
    "Вторая строка\n"
    "Третья строка\n\n"
    "Сообщение отправляется\n"
    "по команде /start"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=IMAGE_URL,
        caption=TEXT
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
