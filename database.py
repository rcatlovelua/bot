import aiosqlite

import os

DATA_DIR = os.getenv("DATA_DIR", "/app/data")

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                region TEXT NOT NULL DEFAULT 'Санкт-Петербург',
                custom_channel TEXT,
                ai_enabled INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
        """, (user_id,))

        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, region, custom_channel, ai_enabled, enabled
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        row = await cursor.fetchone()

        if not row:
            return None

        return {
            "user_id": row[0],
            "region": row[1],
            "custom_channel": row[2],
            "ai_enabled": bool(row[3]),
            "enabled": bool(row[4]),
        }


async def set_region(user_id: int, region: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET region = ?
            WHERE user_id = ?
        """, (region, user_id))

        await db.commit()


async def set_channel(user_id: int, channel: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET custom_channel = ?
            WHERE user_id = ?
        """, (channel, user_id))

        await db.commit()


async def set_ai(user_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET ai_enabled = ?
            WHERE user_id = ?
        """, (int(enabled), user_id))

        await db.commit()


async def set_enabled(user_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET enabled = ?
            WHERE user_id = ?
        """, (int(enabled), user_id))

        await db.commit()


async def get_all_enabled_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, region, custom_channel, ai_enabled
            FROM users
            WHERE enabled = 1
        """)

        rows = await cursor.fetchall()

        return [
            {
                "user_id": row[0],
                "region": row[1],
                "custom_channel": row[2],
                "ai_enabled": bool(row[3]),
            }
            for row in rows
        ]
        print("ДБ:ОК ✅")
