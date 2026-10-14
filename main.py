import logging
import os
import sqlite3
from typing import Optional

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
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

# По умолчанию используем локальную папку data, если /app/data недоступна
DEFAULT_DATA_DIR = "/app/data" if os.access("/app", os.W_OK) else os.path.join(os.getcwd(), "data")
DATA_DIR = os.getenv("DATA_DIR", DEFAULT_DATA_DIR)

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot.db")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# Снижаем шум от httpx-запросов Telegram
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# =========================================================
# DATABASE
# =========================================================

def get_db_connection() -> sqlite3.Connection:
    """Создаёт подключение к SQLite с оптимизированным режимом WAL и таймаутом."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    """Инициализирует таблицу пользователей и индексы."""
    with get_db_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                region TEXT,
                enabled INTEGER DEFAULT 1
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_enabled_region
            ON users (enabled, region)
            """
        )
        db.commit()


def create_user(user_id: int) -> None:
    """Добавляет пользователя в БД, если его ещё нет."""
    with get_db_connection() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, region, enabled)
            VALUES (?, ?, ?)
            """,
            (user_id, None, 1),
        )
        db.commit()


def set_region(user_id: int, region: str) -> None:
    """Обновляет выбранный регион пользователя."""
    create_user(user_id)
    with get_db_connection() as db:
        db.execute(
            """
            UPDATE users
            SET region = ?
            WHERE user_id = ?
            """,
            (region, user_id),
        )
        db.commit()


def set_enabled(user_id: int, enabled: bool) -> None:
    """Включает или выключает уведомления для пользователя."""
    create_user(user_id)
    with get_db_connection() as db:
        db.execute(
            """
            UPDATE users
            SET enabled = ?
            WHERE user_id = ?
            """,
            (1 if enabled else 0, user_id),
        )
        db.commit()


def get_user(user_id: int) -> dict:
    """Возвращает настройки пользователя (region, enabled)."""
    create_user(user_id)
    with get_db_connection() as db:
        cursor = db.execute(
            """
            SELECT user_id, region, enabled
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()

    if not row:
        return {"user_id": user_id, "region": None, "enabled": True}

    return {
        "user_id": row["user_id"],
        "region": row["region"],
        "enabled": bool(row["enabled"]),
    }


def get_active_subscribers(region: Optional[str] = None) -> list[int]:
    """
    Возвращает список user_id с включёнными уведомлениями (enabled = 1)
    для рассылки тревог из модуля анализатора.
    """
    with get_db_connection() as db:
        if region == "Санкт-Петербург":
            cursor = db.execute(
                """
                SELECT user_id FROM users
                WHERE enabled = 1
                  AND (region IN ('Санкт-Петербург', 'Весь Санкт-Петербург') OR region IS NULL)
                """
            )
        elif region == "Ленинградская область":
            cursor = db.execute(
                """
                SELECT user_id FROM users
                WHERE enabled = 1
                  AND region IN ('Ленинградская область', 'Весь Санкт-Петербург')
                """
            )
        elif region:
            cursor = db.execute(
                """
                SELECT user_id FROM users
                WHERE enabled = 1
                  AND (region = ? OR region = 'Другой регион')
                """,
                (region,),
            )
        else:
            cursor = db.execute(
                "SELECT user_id FROM users WHERE enabled = 1"
            )

        return [row["user_id"] for row in cursor.fetchall()]


# =========================================================
# UI КЛАВИАТУРЫ И ПОМОЩНИКИ
# =========================================================

def build_region_keyboard(include_skip: bool = True, include_back: bool = False) -> InlineKeyboardMarkup:
    """Формирует единую клавиатуру выбора региона (для /start и /settings)."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🇷🇺 Санкт-Петербург",
                callback_data="region_spb",
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 Весь СПб и область",
                callback_data="region_all_spb",
            )
        ],
        [
            InlineKeyboardButton(
                "🌲 Ленинградская область",
                callback_data="region_lo",
            )
        ],
        [
            InlineKeyboardButton(
                "📍 Другой регион",
                callback_data="region_other",
            )
        ],
    ]

    if include_skip:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⏭ Пропустить",
                    callback_data="region_skip",
                )
            ]
        )

    if include_back:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ Назад в настройки",
                    callback_data="settings_main",
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


def build_settings_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Формирует текст и клавиатуру для экрана настроек."""
    user_data = get_user(user_id)
    region = user_data["region"] or "не выбран (по умолчанию СПб)"
    enabled = user_data["enabled"]

    status_text = "🟢 Включены" if enabled else "🔴 Отключены"
    toggle_btn_text = "🔕 Отключить уведомления" if enabled else "🔔 Включить уведомления"

    text = (
        "⚙️ <b>Настройки оповещений</b>\n\n"
        f"📍 Регион: <b>{region}</b>\n"
        f"🔔 Уведомления: <b>{status_text}</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📍 Изменить регион",
                callback_data="settings_region",
            )
        ],
        [
            InlineKeyboardButton(
                toggle_btn_text,
                callback_data="settings_toggle",
            )
        ],
    ]

    return text, InlineKeyboardMarkup(keyboard)


async def safe_edit_message(
    query,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Безопасно редактирует сообщение, игнорируя ошибку 'Message is not modified'."""
    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    create_user(user_id)

    reply_markup = build_region_keyboard(include_skip=True)

    await update.message.reply_text(
        "🚨 <b>Внимание, П!</b>\n\n"
        "Я предупрежу тебя о сообщениях о сиренах, плане «Ковёр», угрозах БПЛА и других экстренных событиях.\n\n"
        "📍 <b>Где отслеживать оповещения?</b>\n\n"
        "Выбери регион:",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


# =========================================================
# ОБРАБОТКА КНОПОК РЕГИОНА
# =========================================================

async def region_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return

    user_id = query.from_user.id

    regions = {
        "region_spb": "Санкт-Петербург",
        "region_all_spb": "Весь Санкт-Петербург",
        "region_lo": "Ленинградская область",
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

    await query.answer("Регион сохранён!")

    create_user(user_id)
    set_region(user_id, region)

    if query.data == "region_spb":
        text = (
            "✅ <b>Регион выбран!</b>\n\n"
            "📍 <b>Санкт-Петербург</b>\n\n"
            "Теперь я буду присылать экстренные оповещения, относящиеся к Санкт-Петербургу.\n\n"
            "Управление параметрами: <code>/settings</code>"
        )
    elif query.data == "region_all_spb":
        text = (
            "🌐 <b>Весь Санкт-Петербург и область</b>\n\n"
            "Готово! Теперь будут учитываться экстренные сообщения по всему Санкт-Петербургу и пригородам.\n\n"
            "Управление параметрами: <code>/settings</code>"
        )
    elif query.data == "region_lo":
        text = (
            "🌲 <b>Регион выбран!</b>\n\n"
            "📍 <b>Ленинградская область</b>\n\n"
            "Теперь я буду присылать оповещения по районам Ленинградской области (47 регион).\n\n"
            "Управление параметрами: <code>/settings</code>"
        )
    elif query.data == "region_other":
        text = (
            "📍 <b>Другой регион</b>\n\n"
            "Эта функция пока находится в разработке.\n\n"
            "Сейчас рекомендуем выбрать Санкт-Петербург или Ленобласть через <code>/settings</code>."
        )
    else:
        text = (
            "⏭ <b>Готово!</b>\n\n"
            "Используется общий режим по Санкт-Петербургу.\n\n"
            "🚨 Если будет обнаружено подходящее оповещение, я оперативно отправлю предупреждение."
        )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚙️ Открыть настройки",
                    callback_data="settings_main",
                )
            ]
        ]
    )

    await safe_edit_message(query, text, reply_markup=keyboard)


# =========================================================
# /settings И КНОПКИ НАСТРОЕК
# =========================================================

async def settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    text, reply_markup = build_settings_view(user_id)

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def settings_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return

    user_id = query.from_user.id

    if query.data == "settings_region":
        await query.answer()
        await safe_edit_message(
            query,
            "📍 <b>Выбери новый регион отслеживания:</b>",
            reply_markup=build_region_keyboard(include_skip=False, include_back=True),
        )

    elif query.data == "settings_toggle":
        user_data = get_user(user_id)
        new_state = not user_data["enabled"]
        set_enabled(user_id, new_state)

        toast_text = (
            "🔔 Уведомления включены"
            if new_state
            else "🔕 Уведомления приостановлены"
        )
        await query.answer(toast_text)

        text, reply_markup = build_settings_view(user_id)
        await safe_edit_message(query, text, reply_markup=reply_markup)

    elif query.data == "settings_main":
        await query.answer()
        text, reply_markup = build_settings_view(user_id)
        await safe_edit_message(query, text, reply_markup=reply_markup)


# =========================================================
# /help
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "🚨 <b>Внимание, П!</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start — начальная настройка и выбор региона\n"
        "/settings — управление регионом и уведомлениями\n"
        "/help — справка о работе бота\n\n"
        "⚠️ <i>Бот является информационным инструментом и не заменяет официальные источники экстренной информации (МЧС, 112).</i>",
        parse_mode="HTML",
    )


# =========================================================
# ERROR HANDLER & POST INIT
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Исключение при обработке обновления Telegram:",
        exc_info=context.error,
    )


async def post_init(application: Application) -> None:
    """Автоматически регистрирует меню команд в интерфейсе Telegram при запуске."""
    commands = [
        BotCommand("start", "Выбрать регион"),
        BotCommand("settings", "Настройки уведомлений"),
        BotCommand("help", "Справка и помощь"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Меню команд бота успешно установлено")
    except Exception:
        logger.warning("Не удалось установить меню команд бота", exc_info=True)


# =========================================================
# MAIN
# =========================================================

def main() -> None:
    init_db()

    logger.info("🚨 Внимание, П! запускается...")
    logger.info("DB: %s", DB_PATH)

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("help", help_command))

    # Кнопки
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

    app.add_error_handler(error_handler)

    print("🚨 Внимание, П! запущен!")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
