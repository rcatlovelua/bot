import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# =========================================================
# TOKEN
# Хостинг сам передаёт его через environment variables
# =========================================================

TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("BOT_API_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("API_TOKEN")
    or os.getenv("TOKEN")
)

if not TOKEN:
    raise RuntimeError(
        "Токен не найден в переменных окружения"
    )


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_NAME = "Внимание, П!"

IMAGE_URL = "https://example.com/image.png"


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        f"""
🚨 <b>{BOT_NAME}</b>

Привет!

Я могу предупреждать тебя о сообщениях
о сиренах, тревогах и чрезвычайных ситуациях.

📍 Сначала выбери регион:

🇷🇺 Санкт-Петербург
🌐 Весь Санкт-Петербург
📍 Другой регион

После этого можно подключить
Telegram-канал для дополнительного
мониторинга.

⚠️ Я являюсь информационным ботом.
В экстренной ситуации проверяй
официальные источники.
""",
        parse_mode="HTML",
    )


# =========================================================
# ERROR
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    logging.error(
        "Ошибка:",
        exc_info=context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        f"🚨 {BOT_NAME} запущен!"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
