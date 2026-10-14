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

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    keyboard = [
        [
            InlineKeyboardButton(
                "🇷🇺 Санкт-Петербург",
                callback_data="region_spb"
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 Весь СПб",
                callback_data="region_all_spb"
            )
        ],
        [
            InlineKeyboardButton(
                "📍 Другой регион",
                callback_data="region_other"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭ Пропустить",
                callback_data="region_skip"
            )
        ],
    ]

    await update.message.reply_text(
        """
🚨 <b>Внимание, П!</b>

Я буду предупреждать тебя об
экстренных оповещениях.

📍 Где отслеживать сообщения?

Выбери регион ниже:
""",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def choose_region(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    regions = {
        "region_spb": "Санкт-Петербург",
        "region_all_spb": "Весь Санкт-Петербург",
        "region_other": "Другой регион",
        "region_skip": "Весь Санкт-Петербург",
    }

    region = regions[query.data]

    context.user_data["region"] = region

    await query.edit_message_text(
        f"""
✅ <b>Регион выбран!</b>

📍 {region}

Теперь бот будет использовать этот
регион для фильтрации оповещений.

Изменить выбор можно через /start.
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
