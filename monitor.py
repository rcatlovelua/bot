import asyncio
import logging
from datetime import datetime

from telethon import TelegramClient, events

from config import (
    API_ID,
    API_HASH,
    MONITOR_CHANNELS,
    AI_ENABLED,
)

from ai import analyze_message


logger = logging.getLogger(__name__)


class TelegramMonitor:

    def __init__(self, alert_callback):
        self.alert_callback = alert_callback

        self.client = TelegramClient(
            "monitor_session",
            API_ID,
            API_HASH,
        )

        self.running = False

    async def start(self):

        if not MONITOR_CHANNELS:
            logger.warning(
                "MONITOR_CHANNELS пустой. "
                "Мониторинг отключен."
            )
            return

        await self.client.start()

        logger.info(
            "Telethon запущен."
        )

        logger.info(
            "Каналы: %s",
            ", ".join(MONITOR_CHANNELS)
        )

        @self.client.on(
            events.NewMessage(
                chats=MONITOR_CHANNELS
            )
        )
        async def handler(event):

            try:
                text = event.raw_text.strip()

                if not text:
                    return

                logger.info(
                    "Новое сообщение: %s",
                    text[:200]
                )

                result = await analyze_message(
                    text
                )

                if not result["alert"]:
                    return

                logger.warning(
                    "🚨 ТРЕВОГА: %s",
                    result
                )

                await self.alert_callback(
                    text=text,
                    result=result,
                    source=str(
                        event.chat_id
                    ),
                    message_id=event.id,
                )

            except Exception:
                logger.exception(
                    "Ошибка обработки сообщения"
                )

        self.running = True

        await self.client.run_until_disconnected()

    async def stop(self):

        if self.client.is_connected():
            await self.client.disconnect()

        self.running = False