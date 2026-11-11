import logging

import httpx
from telegram import Bot

from app.config import settings

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def set_bot(bot: Bot | None) -> None:
    global _bot
    _bot = bot


def archive_configured() -> bool:
    return bool(settings.telegram_archive_chat_id.strip() and _bot is not None)


async def archive_images(urls: list[str]) -> list[str]:
    chat_id = settings.telegram_archive_chat_id.strip()
    if not chat_id or _bot is None or not urls:
        return []

    file_ids: list[str] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in urls[:8]:
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                message = await _bot.send_photo(chat_id=chat_id, photo=response.content)
                if message.photo:
                    file_ids.append(message.photo[-1].file_id)
            except Exception:
                logger.exception("could not archive image")
    return file_ids
