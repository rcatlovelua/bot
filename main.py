import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# bothost сам подставляет токен
TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("BOT_API_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("API_TOKEN")
    or os.getenv("TOKEN")
)

if not TOKEN:
    raise RuntimeError("Токен не найден в переменных окружения")

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
