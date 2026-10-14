import os
from dotenv import load_dotenv


load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Не задана переменная {name} в .env"
        )

    return value


BOT_TOKEN = required("BOT_TOKEN")

API_ID = int(required("API_ID"))
API_HASH = required("API_HASH")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"

MONITOR_CHANNELS = [
    x.strip()
    for x in os.getenv("MONITOR_CHANNELS", "").split(";")
    if x.strip()
]

ALERT_REPEAT_COUNT = int(
    os.getenv("ALERT_REPEAT_COUNT", "6")
)

ALERT_DELAYS = [
    int(x.strip())
    for x in os.getenv(
        "ALERT_DELAYS",
        "0,15,30,60,120,300"
    ).split(",")
]

if len(ALERT_DELAYS) < ALERT_REPEAT_COUNT:
    last = ALERT_DELAYS[-1] if ALERT_DELAYS else 60

    while len(ALERT_DELAYS) < ALERT_REPEAT_COUNT:
        ALERT_DELAYS.append(last)


REGIONS = [
    "Санкт-Петербург",
    "Ленинградская область",
    "Москва",
    "Московская область",
    "Другой регион",
    "🌐 Весь СПб",
]