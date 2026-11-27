import asyncio
import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.database import SessionLocal
from app.errors import AppError
from app.models import DivarColleague, DivarConnection, Listing
from app.services.divar_panel import (
    DivarLoginRequired,
    fetch_active_posts,
    fetch_public_url,
    match_colleague,
    name_key,
    refresh_colleagues,
)
from app.services.listings import import_agent, refresh_listing_content, register_listing
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
    removed: int = 0
    errors: list[str] = field(default_factory=list)
    message: str = ""
    phase: str = "idle"
    current_index: int = 0
    current_title: str = ""
    current_author: str = ""
    paused: bool = False
    list_ready: bool = False


def blank_sync_report() -> dict:
    return {
        "colleagues_added": [],
        "colleagues_removed": [],
        "colleague_phones": [],
        "colleague_renames": [],
        "ads_added": [],
        "ads_removed": [],
        "unchanged": 0,
        "consultant_changes": [],
        "spec_changes": [],
        "errors": [],
        "deletions_applied": False,
        "list_ready": False,
    }


_status = SyncStatus()
_report = blank_sync_report()
_task: asyncio.Task | None = None
_lock = asyncio.Lock()
_gate = asyncio.Event()
_gate.set()
_generation = 0


def sync_status() -> SyncStatus:
    return _status


async def start_sync() -> SyncStatus:
    global _task, _generation
    async with _lock:
        if _task is not None and not _task.done() and _status.running:
            return _status
        previous = _task
        if previous is not None and not previous.done():
            previous.cancel()
            _gate.set()
            try:
                await previous
            except (asyncio.CancelledError, Exception):
                pass
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
        _generation += 1
        generation = _generation
        _reset(running=True, message="در حال بررسی لیست مشاوران", phase="colleagues")
        _task = asyncio.create_task(_run(generation))
        return _status


def pause_sync() -> SyncStatus:
    if _status.running:
        _status.paused = True
        _gate.clear()
    return _status


def resume_sync() -> SyncStatus:
    if _status.running and _status.paused:
        _status.paused = False
        _gate.set()
    return _status


def sync_result_note(complete: bool, done: int, total: int, listed: bool) -> str:
    if complete:
        return "کامل"
    if listed:
        return f"ناقص: بررسی لیست مشاوران و {done} آگهی از {total}"
    return "ناقص: بررسی لیست مشاوران"


def save_sync_mark(complete: bool, done: int, total: int, listed: bool) -> None:
    payload = copy.deepcopy(_report)
    payload["list_ready"] = listed
    db = SessionLocal()
    try:
        row = db.get(DivarConnection, 1)
        if row is None:
            return
        row.last_sync_at = datetime.now(timezone.utc)
        row.last_sync_complete = complete
        row.last_sync_done = done
        row.last_sync_total = total
        row.last_sync_listed = listed
        row.last_sync_report = payload
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("sync result was not stored")
    finally:
        db.close()


def cancel_sync() -> SyncStatus:
    global _generation
    if _status.running:
        save_sync_mark(False, _status.completed, _status.total, _status.list_ready)
    _generation += 1
    _status.running = False
    _status.paused = False
    _status.phase = "idle"
    _status.message = ""
    _status.current_index = 0
    _status.current_title = ""
    _status.current_author = ""
    _gate.set()
    if _task is not None and not _task.done():
        _task.cancel()
    return _status


async def _wait_if_paused(generation: int | None = None) -> None:
    expected = _generation if generation is None else generation
    await _gate.wait()
    if expected != _generation:
        raise asyncio.CancelledError


def _reset(**kwargs) -> None:
    global _status, _report
    _gate.set()
    _status = SyncStatus(**kwargs)
    _report = blank_sync_report()


async def _run(generation: int) -> None:
    try:
        await asyncio.to_thread(_sync_colleagues)
        if generation != _generation:
            return
        _status.colleagues_ready = True
        _status.message = "لیست مشاوران بررسی شد"
        await _wait_if_paused(generation)
        await asyncio.sleep(1.2)
        await _wait_if_paused(generation)
        _status.phase = "counting"
        _status.message = "در حال خواندن آگهی‌های فعال"
        await _wait_if_paused(generation)
        cookies, front_token, posts_ready = await asyncio.to_thread(_session_flags)
        if not posts_ready:
            await asyncio.to_thread(save_sync_mark, False, 0, 0, False)
            _status.phase = "done"
            _status.message = "بررسی لیست مشاوران. لینک آگهی‌ها ثبت نشده است."
            _status.running = False
            _status.paused = False
            return
        await _wait_if_paused(generation)
        posts = await asyncio.to_thread(fetch_active_posts, cookies, front_token)
        if generation != _generation:
            return
        _status.list_ready = True
        _status.total = len(posts)
        _status.phase = "sending"
        _status.message = ""
        people = await asyncio.to_thread(_colleague_pairs)
        kept: set[str] = set()
        catalog_complete = True
        for index, post in enumerate(posts, start=1):
            await _wait_if_paused(generation)
            _status.current_index = index
            _status.current_title = post.title
            _status.current_author = post.author
            try:
                url, token = await _resolve_post(post, cookies, front_token)
            except DivarLoginRequired:
                raise
            except asyncio.CancelledError:
                raise
            except AppError as exc:
                catalog_complete = False
                _remember_error(post.title, exc.message)
                continue
            except Exception:
                logger.exception("divar post resolve failed")
                catalog_complete = False
                _remember_error(post.title, "شناسهٔ این آگهی از دیوار خوانده نشد.")
                continue
            kept.add(token)
            try:
                outcome = await _import_resolved(post, people, url, token)
            except DivarLoginRequired:
                raise
            except asyncio.CancelledError:
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
        if generation != _generation:
            return
        if catalog_complete:
            removed_rows = await asyncio.to_thread(retain_active_listings, kept)
            _report["ads_removed"] = removed_rows
            _report["deletions_applied"] = True
            _status.removed = len(removed_rows)
        else:
            _remember_error("حذف آگهی‌ها", "چون خواندن بعضی آگهی‌ها ناتمام ماند، آگهی قبلی از بات حذف نشد.", report=False)
        await asyncio.to_thread(save_sync_mark, catalog_complete, _status.completed, _status.total, True)
        _status.current_index = 0
        _status.current_title = ""
        _status.current_author = ""
        _status.phase = "done"
        _status.message = ""
        _status.paused = False
        _status.running = False
    except asyncio.CancelledError:
        if generation == _generation:
            _status.running = False
            _status.paused = False
            _status.phase = "idle"
            _status.message = ""
            _status.current_index = 0
            _status.current_title = ""
            _status.current_author = ""
        return
    except DivarLoginRequired:
        if generation != _generation:
            return
        await asyncio.to_thread(save_sync_mark, False, _status.completed, _status.total, _status.list_ready)
        _status.needs_login = True
        _status.phase = "failed"
        _status.paused = False
        _status.running = False
        _status.message = "ورود به دیوار لازم است."
    except AppError as exc:
        if generation != _generation:
            return
        await asyncio.to_thread(save_sync_mark, False, _status.completed, _status.total, _status.list_ready)
        _status.phase = "failed"
        _status.paused = False
        _status.running = False
        _status.message = exc.message
    except Exception:
        if generation != _generation:
            return
        await asyncio.to_thread(save_sync_mark, False, _status.completed, _status.total, _status.list_ready)
        logger.exception("divar sync failed")
        _status.phase = "failed"
        _status.paused = False
        _status.running = False
        _status.message = "بروزرسانی دیوار ناتمام ماند."


def _sync_colleagues() -> None:
    db = SessionLocal()
    try:
        _, _, _, _, diff = refresh_colleagues(db)
        _report["colleagues_added"] = list(diff.added)
        _report["colleagues_removed"] = list(diff.removed)
        _report["colleague_phones"] = list(diff.phones)
        _report["colleague_renames"] = list(diff.renames)
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


async def _resolve_post(post, cookies: list, front_token: str) -> tuple[str, str]:
    url = await asyncio.to_thread(fetch_public_url, cookies, post.manage_token, front_token)
    token = extract_divar_token(url)
    if not token:
        raise AppError("توکن آگهی از لینک دیوار خوانده نشد.")
    return url, token


async def _import_resolved(post, people: list[tuple[str, str]], url: str, token: str) -> str:
    db = SessionLocal()
    try:
        existing = db.query(Listing).filter(Listing.divar_token == token).one_or_none()
        if existing:
            old_name = existing.consultant_name
            consultant_changed = apply_consultant_change(existing, post.author, people)
            if consultant_changed:
                db.commit()
                _report["consultant_changes"].append(
                    {
                        "title": post.title or existing.title,
                        "old_name": old_name,
                        "new_name": existing.consultant_name,
                    }
                )
            changes = await refresh_listing_content(db, existing)
            if changes:
                _report["spec_changes"].append(
                    {
                        "title": existing.title,
                        "consultant": existing.consultant_name,
                        "changes": changes,
                    }
                )
                return "sent"
            if not consultant_changed:
                _report["unchanged"] += 1
            return "skipped"
        name, phone = match_colleague(post.author, people)
        agent = import_agent(db)
        listing, _warnings = await register_listing(db, agent, url, consultant_name=name, consultant_phone=phone)
        _report["ads_added"].append({"title": listing.title, "consultant": listing.consultant_name})
        return "sent"
    except AppError as exc:
        if exc.status_code == 409:
            _report["unchanged"] += 1
            return "skipped"
        raise
    finally:
        db.close()


def apply_consultant_change(listing: Listing, author: str, people: list[tuple[str, str]]) -> bool:
    if name_key(listing.consultant_name) == name_key(author):
        return False
    name, phone = match_colleague(author, people)
    listing.consultant_name = name
    listing.consultant_phone = phone
    return True


def drop_listings_outside(db, tokens: set[str]) -> list[dict]:
    removed: list[dict] = []
    for row in db.query(Listing).all():
        if row.divar_token not in tokens:
            removed.append({"title": row.title or "آگهی", "consultant": row.consultant_name or ""})
            db.delete(row)
    return removed


def retain_active_listings(tokens: set[str]) -> list[dict]:
    db = SessionLocal()
    try:
        removed = drop_listings_outside(db, tokens)
        db.commit()
        return removed
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _remember_error(title: str, detail: str, *, report: bool = True) -> None:
    if len(_status.errors) < 30:
        _status.errors.append(f"{title}: {detail}")
    if report:
        _report["errors"].append({"title": title, "reason": detail})
