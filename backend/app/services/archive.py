import asyncio
import logging
from io import BytesIO

import httpx
from telegram import Bot
from telegram.error import NetworkError, RetryAfter, TimedOut

from app.config import settings

logger = logging.getLogger(__name__)

_bot: Bot | None = None
_SEND_PAUSES = (0, 3, 8)


def set_bot(bot: Bot | None) -> None:
    global _bot
    _bot = bot


def archive_configured() -> bool:
    return bool(settings.telegram_archive_chat_id.strip() and _bot is not None)


async def _download(client: httpx.AsyncClient, url: str) -> bytes | None:
    for pause in _SEND_PAUSES:
        if pause:
            await asyncio.sleep(pause)
        try:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if response.content:
                return response.content
        except httpx.HTTPError:
            logger.warning("listing image download failed; retrying the same photo")
    return None


async def _send_one(chat_id: str, content: bytes) -> str | None:
    if _bot is None:
        return None
    photo = BytesIO(content)
    if content.startswith(b"\xff\xd8"):
        photo.name = "photo.jpg"
    elif content.startswith(b"\x89PNG"):
        photo.name = "photo.png"
    else:
        photo.name = "photo.webp"
    for pause in _SEND_PAUSES:
        if pause:
            await asyncio.sleep(pause)
        photo.seek(0)
        try:
            message = await _bot.send_photo(chat_id=chat_id, photo=photo)
            if message.photo:
                return message.photo[-1].file_id
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 1)
        except (NetworkError, TimedOut):
            logger.warning("listing image upload stalled; retrying the same photo")
        except Exception:
            logger.exception("listing image was rejected")
            return None
    return None


async def archive_images(urls: list[str]) -> list[str]:
    chat_id = settings.telegram_archive_chat_id.strip()
    if not chat_id or _bot is None or not urls:
        return []

    file_ids: list[str] = []
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
        for url in urls:
            content = await _download(client, url)
            if content is None:
                logger.error("listing image could not be downloaded")
                continue
            file_id = await _send_one(chat_id, content)
            if file_id is None:
                logger.error("listing image could not be uploaded")
                continue
            file_ids.append(file_id)
    return file_ids
