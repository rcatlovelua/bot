import json
import logging

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL


logger = logging.getLogger(__name__)

client = None

if OPENAI_API_KEY:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def analyze_message(text: str) -> dict:
    """
    Анализирует сообщение.

    Возвращает:

    {
        "alert": true/false,
        "type": "siren",
        "region": "Санкт-Петербург",
        "confidence": 0.98,
        "reason": "..."
    }
    """

    if not client:
        return keyword_analyze(text)

    prompt = f"""
Ты — фильтр экстренных сообщений для Telegram-бота
«Внимание, П!».

Твоя задача — определить, сообщает ли текст
о реальной угрозе, тревоге, сирене или системе
оповещения населения.

НЕ считай тревогой:
- обсуждения старых событий;
- новости о прошлых тревогах;
- прогнозы;
- инструкции без факта события;
- шутки;
- мемы;
- обычные новости.

Особенно важно отличать Санкт-Петербург
от других регионов.

Верни ТОЛЬКО JSON:

{{
  "alert": true,
  "type": "siren",
  "region": "Санкт-Петербург",
  "confidence": 0.95,
  "reason": "краткое объяснение"
}}

Допустимые type:
- "siren"
- "air_alert"
- "emergency"
- "other"

Если тревоги нет:

{{
  "alert": false,
  "type": "other",
  "region": null,
  "confidence": 0.0,
  "reason": "..."
}}

Сообщение:

{text[:6000]}
"""

    try:
        response = await client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )

        raw = response.output_text.strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()

        result = json.loads(raw)

        return {
            "alert": bool(result.get("alert", False)),
            "type": result.get("type", "other"),
            "region": result.get("region"),
            "confidence": float(
                result.get("confidence", 0)
            ),
            "reason": result.get("reason", ""),
        }

    except Exception:
        logger.exception("Ошибка ИИ")

        return keyword_analyze(text)


def keyword_analyze(text: str) -> dict:
    """
    Резервный анализ без ИИ.
    """

    lowered = text.lower()

    alert_words = [
        "сирен",
        "система оповещения",
        "включена система оповещения",
        "включение сирен",
        "запущена сирена",
        "звучит сирена",
        "звучат сирены",
        "воздушная тревога",
        "тревога",
        "угроза",
        "оповещение населения",
    ]

    negative_words = [
        "отмена",
        "отменена",
        "была включена",
        "ранее",
        "вчера",
        "архив",
        "повторяем",
    ]

    has_alert = any(
        word in lowered
        for word in alert_words
    )

    has_negative = any(
        word in lowered
        for word in negative_words
    )

    if has_alert and not has_negative:
        return {
            "alert": True,
            "type": "siren",
            "region": detect_region(text),
            "confidence": 0.70,
            "reason": "Найдено ключевое слово",
        }

    return {
        "alert": False,
        "type": "other",
        "region": None,
        "confidence": 0,
        "reason": "Признаков тревоги не найдено",
    }


def detect_region(text: str):
    lowered = text.lower()

    if (
        "санкт-петербург" in lowered
        or "петербург" in lowered
        or "спб" in lowered
        or "ленинград" in lowered
    ):
        return "Санкт-Петербург"

    if "москва" in lowered:
        return "Москва"

    return None