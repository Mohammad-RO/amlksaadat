import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bot.runner import run_bot
from app.config import settings
from app.database import init_db
from app.errors import AppError
from app.routers import admin, auth, listings
from app.schemas import HealthOut
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop_event = asyncio.Event()
    bot_task = asyncio.create_task(run_bot(stop_event))
    yield
    stop_event.set()
    try:
        await asyncio.wait_for(bot_task, timeout=12)
    except asyncio.TimeoutError:
        bot_task.cancel()
        logger.warning("telegram bot did not stop in time")


app = FastAPI(title="املاک سعادت‌آباد", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def handle_app_error(_, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        ok=True,
        bot_configured=bool(settings.telegram_bot_token.strip()),
        archive_configured=bool(settings.telegram_archive_chat_id.strip()),
    )


app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
