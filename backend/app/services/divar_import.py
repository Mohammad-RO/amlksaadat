import asyncio
import logging
from dataclasses import dataclass, field

from app.database import SessionLocal
from app.errors import AppError
from app.models import DivarColleague, DivarConnection, Listing
from app.services.divar_panel import (
    DivarLoginRequired,
    fetch_active_posts,
    fetch_public_url,
    match_colleague,
    refresh_colleagues,
)
from app.services.listings import import_agent, register_listing
from app.utils import extract_divar_token

logger = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    running: bool = False
    needs_login: bool = False
    colleagues_ready: bool = False
    total: int = 0
    completed: int = 0
    sent: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    message: str = ""
    phase: str = "idle"


_status = SyncStatus()
_task: asyncio.Task | None = None
_lock = asyncio.Lock()


def sync_status() -> SyncStatus:
    return _status


async def start_sync() -> SyncStatus:
    global _task
    async with _lock:
        if _task is not None and not _task.done():
            return _status
        db = SessionLocal()
        try:
            row = db.get(DivarConnection, 1)
            if row is None or not row.cookies:
                _reset(needs_login=True, message="ورود به دیوار لازم است.")
                return _status
            if not row.business_token:
                _reset(message="اول لینک مدیریت همکاران را ثبت کنید.")
                return _status
        finally:
            db.close()
        _reset(running=True, message="در حال بررسی لیست مشاوران", phase="colleagues")
        _task = asyncio.create_task(_run())
        return _status


def _reset(**kwargs) -> None:
    global _status
    _status = SyncStatus(**kwargs)


async def _run() -> None:
    try:
        await asyncio.to_thread(_sync_colleagues)
        _status.colleagues_ready = True
        _status.phase = "counting"
        _status.message = "بررسی لیست مشاوران"
        cookies, front_token, posts_ready = await asyncio.to_thread(_session_flags)
        if not posts_ready:
            _status.phase = "done"
            _status.message = "بررسی لیست مشاوران. لینک آگهی‌ها ثبت نشده است."
            _status.running = False
            return
        posts = await asyncio.to_thread(fetch_active_posts, cookies, front_token)
        _status.total = len(posts)
        _status.phase = "sending"
        people = await asyncio.to_thread(_colleague_pairs)
        for post in posts:
            try:
                outcome = await _import_post(post, people, cookies, front_token)
            except DivarLoginRequired:
                raise
            except AppError as exc:
                _remember_error(post.title, exc.message)
                continue
            except Exception:
                logger.exception("divar post import failed")
                _remember_error(post.title, "ارسال این آگهی انجام نشد.")
                continue
            if outcome == "sent":
                _status.sent += 1
            else:
                _status.skipped += 1
            _status.completed = _status.sent + _status.skipped
        _status.phase = "done"
        _status.message = "بررسی لیست مشاوران"
        _status.running = False
    except DivarLoginRequired:
        _status.needs_login = True
        _status.phase = "failed"
        _status.running = False
        _status.message = "ورود به دیوار لازم است."
    except AppError as exc:
        _status.phase = "failed"
        _status.running = False
        _status.message = exc.message
    except Exception:
        logger.exception("divar sync failed")
        _status.phase = "failed"
        _status.running = False
        _status.message = "بروزرسانی دیوار ناتمام ماند."


def _sync_colleagues() -> None:
    db = SessionLocal()
    try:
        refresh_colleagues(db)
    finally:
        db.close()


def _session_flags() -> tuple[list, str, bool]:
    db = SessionLocal()
    try:
        row = db.get(DivarConnection, 1)
        if row is None or not row.cookies:
            raise DivarLoginRequired
        return list(row.cookies or []), row.front_token or "", bool(row.posts_url)
    finally:
        db.close()


def _colleague_pairs() -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        row = db.get(DivarConnection, 1)
        token = row.business_token if row else ""
        rows = db.query(DivarColleague).filter(DivarColleague.business_token == token).all()
        return [(item.name, item.phone) for item in rows]
    finally:
        db.close()


async def _import_post(post, people: list[tuple[str, str]], cookies: list, front_token: str) -> str:
    url = await asyncio.to_thread(fetch_public_url, cookies, post.manage_token, front_token)
    token = extract_divar_token(url)
    if not token:
        raise AppError("توکن آگهی از لینک دیوار خوانده نشد.")
    db = SessionLocal()
    try:
        existing = db.query(Listing.id).filter(Listing.divar_token == token).first()
        if existing:
            return "skipped"
        name, phone = match_colleague(post.author, people)
        agent = import_agent(db)
        await register_listing(db, agent, url, consultant_name=name, consultant_phone=phone)
        return "sent"
    except AppError as exc:
        if exc.status_code == 409:
            return "skipped"
        raise
    finally:
        db.close()


def _remember_error(title: str, detail: str) -> None:
    if len(_status.errors) >= 30:
        return
    _status.errors.append(f"{title}: {detail}")
