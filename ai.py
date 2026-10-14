import json
import logging
import re
from typing import Any, Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Сохраняем исходные названия переменных из config для полной обратной совместимости
from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

client = None

if OPENAI_API_KEY:
    try:
        client = genai.Client(api_key=OPENAI_API_KEY)
    except Exception:
        logger.exception("Не удалось инициализировать клиент Gemini")


class AlertAnalysisSchema(BaseModel):
    """Строгая схема ответа для гарантированного получения валидного JSON от Gemini."""
    alert: bool = Field(
        description="True, если сообщение сообщает о текущей реальной тревоге, сирене или ЧС прямо сейчас."
    )
    type: Literal["siren", "air_alert", "emergency", "other"] = Field(
        description="Классификация типа тревоги."
    )
    region: Optional[str] = Field(
        default=None,
        description="Стандартизированное название региона (например, 'Санкт-Петербург', 'Ленинградская область') или null."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Уверенность модели в оценке от 0.0 до 1.0."
    )
    reason: str = Field(
        description="Краткое и точное объяснение причины принятого решения на русском языке."
    )


SYSTEM_INSTRUCTION = """
Ты — высокоточный фильтр экстренных сообщений для Telegram-бота «Внимание, П!».

Твоя задача — определить, сообщает ли текст о РЕАЛЬНОЙ ТЕКУЩЕЙ угрозе, тревоге, работающей сирене, закрытии воздушного пространства (план «Ковёр») или включении системы оповещения населения.

СТРОГО НЕ СЧИТАЙ ТРЕВОГОЙ (alert = false):
- обсуждения старых или уже завершившихся событий;
- отбой тревоги («отмена воздушной тревоги», «опасность миновала»);
- анонсы предстоящих плановых проверок систем оповещения в будущем;
- отчёты о сбитых целях в прошлом времени без текущей угрозы;
- прогнозы, аналитику, инструкции без факта текущего события;
- шутки, мемы, метафоры, рекламу и обычные новости.

ОСОБЕННО ВАЖНО:
1. Чётко отличать «Санкт-Петербург» (включая районы: Пушкин, Колпино, Кронштадт, Петергоф, Курортный и др., аэропорт Пулково) от «Ленинградской области» (Гатчина, Выборг, Тосно, Кириши, Сосновый Бор, Всеволожск, Кингисепп, Луга и др.) и других регионов РФ.
2. Если в тексте говорится о Санкт-Петербурге — указывай region: "Санкт-Петербург". Если о Ленобласти — "Ленинградская область".
"""


async def analyze_message(text: str) -> dict[str, Any]:
    """
    Анализирует сообщение с помощью Gemini API (с резервным переходом на ключевые слова).

    Возвращает:
    {
        "alert": true/false,
        "type": "siren" | "air_alert" | "emergency" | "other",
        "region": "Санкт-Петербург",
        "confidence": 0.98,
        "reason": "..."
    }
    """
    if not text or not text.strip():
        return {
            "alert": False,
            "type": "other",
            "region": None,
            "confidence": 0.0,
            "reason": "Пустое сообщение",
        }

    if not client:
        return keyword_analyze(text)

    # Если в config осталась старая модель от OpenAI (например, "gpt-4o-mini"),
    # автоматически подставляем актуальную быструю модель Gemini
    model_name = (
        OPENAI_MODEL
        if OPENAI_MODEL and "gemini" in OPENAI_MODEL.lower()
        else "gemini-2.5-flash"
    )

    prompt = f"Проанализируй следующее сообщение:\n\n{text[:6000]}"

    try:
        # Используем асинхронный вызов .aio и Structured Outputs (response_schema)
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=AlertAnalysisSchema,
                temperature=0.1,  # Низкая температура для детерминированности и точности
            ),
        )

        raw = (response.text or "").strip()

        # Дополнительная защита на случай обёрток markdown
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()

        result = json.loads(raw)

        # Нормализация и валидация полей перед возвратом
        allowed_types = {"siren", "air_alert", "emergency", "other"}
        alert_type = result.get("type", "other")
        if alert_type not in allowed_types:
            alert_type = "other"

        confidence = float(result.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return {
            "alert": bool(result.get("alert", False)),
            "type": alert_type,
            "region": result.get("region") or detect_region(text),
            "confidence": confidence,
            "reason": str(result.get("reason", "")).strip(),
        }

    except Exception:
        logger.exception("Ошибка ИИ (Gemini), переключаюсь на резервный алгоритм")
        return keyword_analyze(text)


def keyword_analyze(text: str) -> dict[str, Any]:
    """
    Улучшенный резервный анализ без ИИ на основе категорий угроз и стоп-выражений.
    """
    lowered = text.lower().replace("ё", "е")

    # Словарь паттернов по типам тревоги
    type_patterns = {
        "siren": [
            "сирен",
            "система оповещения",
            "включена система оповещения",
            "включение сирен",
            "запущена сирена",
            "звучит сирена",
            "звучат сирены",
            "оповещение населения",
            "внимание всем",
        ],
        "air_alert": [
            "воздушная тревога",
            "опасность бпла",
            "угроза бпла",
            "атака бпла",
            "беспилотная опасность",
            "ракетная опасность",
            "план ковер",
            "план «ковер»",
            "закрыто небо",
        ],
        "emergency": [
            "экстренное предупреждение",
            "чрезвычайная ситуация",
            "эвакуация",
            "тревога",
            "угроза",
        ],
    }

    # Стоп-слова, указывающие на отбой, прошлое время или плановую учебную проверку
    negative_words = [
        "отмена",
        "отменена",
        "отбой",
        "снята",
        "миновала",
        "была включена",
        "ранее",
        "вчера",
        "архив",
        "повторяем",
        "плановая проверка",
        "комплексная проверка",
        "учебная",
        "учения",
        "состоится проверка",
        "пройдет проверка",
    ]

    has_negative = any(word in lowered for word in negative_words)
    if has_negative:
        return {
            "alert": False,
            "type": "other",
            "region": detect_region(text),
            "confidence": 0.15,
            "reason": "Обнаружены признаки отмены, архива или плановой проверки",
        }

    # Определяем конкретный тип тревоги и сработавший триггер
    detected_type = None
    matched_word = None

    for alert_type, words in type_patterns.items():
        for word in words:
            if word in lowered:
                detected_type = alert_type
                matched_word = word
                break
        if detected_type:
            break

    if detected_type:
        return {
            "alert": True,
            "type": detected_type,
            "region": detect_region(text),
            "confidence": 0.75,
            "reason": f"Найдено ключевое выражение: «{matched_word}»",
        }

    return {
        "alert": False,
        "type": "other",
        "region": None,
        "confidence": 0.0,
        "reason": "Признаков тревоги не найдено",
    }


def detect_region(text: str) -> Optional[str]:
    """
    Определяет регион по ключевым топонимам с разграничением СПб и Ленобласти.
    """
    lowered = text.lower().replace("ё", "е")

    # Точные маркеры Санкт-Петербурга (включая пригороды в составе города и аэропорт)
    spb_markers = [
        "санкт-петербург",
        "петербург",
        "спб",
        "питер",
        "пулково",
        "кронштадт",
        "колпин",
        "пушкинск",
        "петергоф",
        "сестрорецк",
        "красное село",
        "финляндский",
        "васильевск",
    ]

    # Маркеры Ленинградской области (чтобы не путать с самим городом из-за корня «ленинград»)
    lenoblast_markers = [
        "ленинградская область",
        "ленинградской области",
        "ленобласт",
        "лен. обл",
        "47 регион",
        "гатчин",
        "выборг",
        "всеволожск",
        "кириш",
        "сосновый бор",
        "кингисепп",
        "тосн",
        "луг",
        "приозерск",
        "волхов",
        "тихвин",
    ]

    if any(marker in lowered for marker in spb_markers):
        return "Санкт-Петербург"

    if any(marker in lowered for marker in lenoblast_markers):
        return "Ленинградская область"

    if "ленинград" in lowered:
        return "Санкт-Петербург"

    if "москва" in lowered or "москве" in lowered or "мск" in lowered:
        return "Москва"

    return None
