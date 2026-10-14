```python
import os
import logging
import sqlite3

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


# =========================================================
# НАСТРОЙКИ
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


DATA_DIR = os.getenv(
    "DATA_DIR",
    "/app/data"
)

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(
    DATA_DIR,
    "bot.db"
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# DATABASE
# =========================================================

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                region TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)

        db.commit()


def create_user(user_id: int):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, region, enabled)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                None,
                1,
            )
        )

        db.commit()


def set_region(
    user_id: int,
    region: str
):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            UPDATE users
            SET region = ?
            WHERE user_id = ?
            """,
            (
                region,
                user_id,
            )
        )

        db.commit()


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    create_user(user_id)

    keyboard = [
        [
            InlineKeyboardButton(
                "🇷🇺 Санкт-Петербург",
                callback_data="region_spb",
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 Весь СПб",
                callback_data="region_all_spb",
            )
        ],
        [
            InlineKeyboardButton(
                "📍 Другой регион",
                callback_data="region_other",
            )
        ],
        [
            InlineKeyboardButton(
                "⏭ Пропустить",
                callback_data="region_skip",
            )
        ],
    ]

    reply_markup = InlineKeyboardMarkup(
        keyboard
    )

    await update.message.reply_text(
        """
🚨 <b>Внимание, П!</b>

Я предупрежу тебя о сообщениях
о сиренах и других экстренных событиях.

📍 <b>Где отслеживать оповещения?</b>

Выбери регион:
""",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


# =========================================================
# ОБРАБОТКА КНОПОК
# =========================================================

async def region_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    # ОБЯЗАТЕЛЬНО!
    # Без этого Telegram будет бесконечно
    # показывать загрузку после нажатия.
    await query.answer()

    user_id = query.from_user.id

    regions = {
        "region_spb": "Санкт-Петербург",
        "region_all_spb": "Весь Санкт-Петербург",
        "region_other": "Другой регион",
        "region_skip": "Весь Санкт-Петербург",
    }

    region = regions.get(query.data)

    if region is None:
        await query.answer(
            "Неизвестная кнопка",
            show_alert=True,
        )
        return

    create_user(user_id)

    set_region(
        user_id,
        region,
    )

    if query.data == "region_spb":

        text = """
✅ <b>Регион выбран!</b>

📍 Санкт-Петербург

Теперь я буду учитывать оповещения,
относящиеся к Санкт-Петербургу.

Чтобы изменить регион:
<code>/start</code>
"""

    elif query.data == "region_all_spb":

        text = """
🌐 <b>Весь Санкт-Петербург</b>

Готово!

Теперь будут учитываться сообщения
по всему Санкт-Петербургу.

Чтобы изменить регион:
<code>/start</code>
"""

    elif query.data == "region_other":

        text = """
📍 <b>Другой регион</b>

Эта функция пока находится
в разработке.

Сейчас выбери Санкт-Петербург
через <code>/start</code>.
"""

    else:

        text = """
⏭ <b>Готово!</b>

Используется общий режим
по Санкт-Петербургу.

🚨 Если будет обнаружено подходящее
оповещение, я отправлю предупреждение.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
    )


# =========================================================
# /settings
# =========================================================

async def settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    create_user(user_id)

    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            """
            SELECT region
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        )

        row = cursor.fetchone()

    region = (
        row[0]
        if row and row[0]
        else "не выбран"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📍 Изменить регион",
                callback_data="settings_region",
            )
        ],
    ]

    await update.message.reply_text(
        f"""
⚙️ <b>Настройки</b>

📍 Регион:
<b>{region}</b>
""",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# =========================================================
# КНОПКА НАСТРОЕК
# =========================================================

async def settings_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    if query.data == "settings_region":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇷🇺 Санкт-Петербург",
                    callback_data="region_spb",
                )
            ],
            [
                InlineKeyboardButton(
                    "🌐 Весь СПб",
                    callback_data="region_all_spb",
                )
            ],
            [
                InlineKeyboardButton(
                    "📍 Другой регион",
                    callback_data="region_other",
                )
            ],
        ]

        await query.edit_message_text(
            """
📍 <b>Выбери новый регион:</b>
""",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )


# =========================================================
# /help
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        """
🚨 <b>Внимание, П!</b>

Команды:

/start — выбрать регион
/settings — настройки
/help — помощь

⚠️ Бот является информационным
инструментом и не заменяет официальные
источники экстренной информации.
""",
        parse_mode="HTML",
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Ошибка:",
        exc_info=context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    logger.info(
        "🚨 Внимание, П! запускается..."
    )

    logger.info(
        "DB: %s",
        DB_PATH,
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Команды
    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "settings",
            settings,
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    # КНОПКИ
    app.add_handler(
        CallbackQueryHandler(
            region_callback,
            pattern=r"^region_",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            settings_callback,
            pattern=r"^settings_",
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "🚨 Внимание, П! запущен!"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
```
