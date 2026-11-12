import asyncio
import logging

from telegram import BotCommand
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application
from telegram.request import HTTPXRequest

from app.bot.handlers import register_handlers
from app.config import settings
from app.services.archive import set_bot

logger = logging.getLogger(__name__)


def _telegram_request(read_timeout: float, write_timeout: float, media_write_timeout: float) -> HTTPXRequest:
    proxy = settings.telegram_proxy.strip() or None
    return HTTPXRequest(
        connection_pool_size=8,
        proxy=proxy,
        connect_timeout=30,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        media_write_timeout=media_write_timeout,
        pool_timeout=10,
    )


def _build_application() -> Application:
    builder = (
        Application.builder()
        .token(settings.telegram_bot_token.strip())
        .request(_telegram_request(90, 90, 90))
        .get_updates_request(_telegram_request(40, 30, 30))
    )
    application = builder.build()
    register_handlers(application)
    return application


async def _stop_application(application: Application) -> None:
    set_bot(None)
    try:
        if application.updater is not None and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
    except Exception as exc:
        text = str(exc).lower()
        if "not initialized" not in text and "not running" not in text:
            logger.warning("telegram shutdown: %s", exc)


async def run_bot(stop_event: asyncio.Event) -> None:
    if not settings.telegram_bot_token.strip():
        logger.warning("telegram token is empty; bot will not start")
        return

    while not stop_event.is_set():
        application = None
        try:
            application = _build_application()
            await application.initialize()
            await application.start()
            await application.bot.set_my_commands(
                [
                    BotCommand("start", "شروع دوباره"),
                    BotCommand("continue", "ادامه"),
                ]
            )
            set_bot(application.bot)
            if application.updater is None:
                raise RuntimeError("telegram updater is unavailable")
            await application.updater.start_polling(drop_pending_updates=True)
            logger.info("telegram bot is polling")
            await stop_event.wait()
        except (NetworkError, TimedOut, OSError) as exc:
            logger.warning("telegram is unreachable (%s). Retrying in 20 seconds.", exc)
            set_bot(None)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=20)
            except asyncio.TimeoutError:
                pass
        except Exception:
            logger.exception("telegram bot stopped; retrying in 20 seconds")
            set_bot(None)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=20)
            except asyncio.TimeoutError:
                pass
        finally:
            if application is not None:
                await _stop_application(application)
