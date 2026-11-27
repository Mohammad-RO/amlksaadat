import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Agent, DivarColleague, DivarConnection, Listing
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    DivarCodeIn,
    DivarColleagueOut,
    DivarColleaguesOut,
    DivarLinkIn,
    DivarSyncReportOut,
    DivarPhoneIn,
    DivarRefreshOut,
    DivarSyncOut,
)
from app.services.divar_import import cancel_sync, pause_sync, resume_sync, start_sync, sync_result_note, sync_status
from app.services.divar_panel import (
    DivarLoginRequired,
    colleague_rows,
    confirm_divar_login,
    refresh_colleagues,
    save_agent_management_link,
    save_posts_link,
    start_divar_login,
)
from app.utils import format_jalali, normalize_phone

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


def _agent_out(agent: Agent, count: int) -> AgentOut:
    return AgentOut(
        id=agent.id,
        name=agent.name,
        phone=agent.phone,
        is_active=agent.is_active,
        listings_count=count,
        created_at=agent.created_at,
    )


@router.get("/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)) -> list[AgentOut]:
    rows = (
        db.query(Agent, func.count(Listing.id))
        .outerjoin(Listing, Listing.agent_id == Agent.id)
        .group_by(Agent.id, Agent.name, Agent.phone, Agent.is_active, Agent.created_at, Agent.updated_at)
        .order_by(Agent.created_at.desc())
        .all()
    )
    return [_agent_out(agent, count) for agent, count in rows]


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(body: AgentCreate, db: Session = Depends(get_db)) -> AgentOut:
    try:
        phone = normalize_phone(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if db.query(Agent).filter(Agent.phone == phone).first():
        raise HTTPException(status_code=409, detail="این شماره قبلاً ثبت شده است.")
    agent = Agent(name=body.name.strip(), phone=phone, is_active=True)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_out(agent, 0)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, body: AgentUpdate, db: Session = Depends(get_db)) -> AgentOut:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="مشاور پیدا نشد.")
    if body.name is not None:
        agent.name = body.name.strip()
    if body.phone is not None:
        try:
            phone = normalize_phone(body.phone)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        taken = db.query(Agent).filter(Agent.phone == phone, Agent.id != agent.id).first()
        if taken:
            raise HTTPException(status_code=409, detail="این شماره برای مشاور دیگری ثبت شده است.")
        agent.phone = phone
    if body.is_active is not None:
        agent.is_active = body.is_active
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    count = db.query(func.count(Listing.id)).filter(Listing.agent_id == agent.id).scalar() or 0
    return _agent_out(agent, int(count))


def _divar_items(db: Session, business_token: str) -> list[DivarColleagueOut]:
    return [DivarColleagueOut(id=row.id, name=row.name, phone=row.phone) for row in colleague_rows(db, business_token)]


def _divar_state(db: Session) -> tuple[str, str, str, list[DivarColleagueOut]]:
    row = db.get(DivarConnection, 1)
    url = row.url if row else ""
    posts_url = row.posts_url if row else ""
    token = row.business_token if row else ""
    return url, posts_url, token, _divar_items(db, token)


def _report_out(raw: object) -> DivarSyncReportOut | None:
    if not isinstance(raw, dict):
        return None
    try:
        return DivarSyncReportOut.model_validate(raw)
    except Exception:
        logger.exception("sync report could not be read")
        return None


def _colleagues_out(db: Session, url: str, posts_url: str, business_token: str) -> DivarColleaguesOut:
    row = db.get(DivarConnection, 1)
    stamp = ""
    note = ""
    report = None
    if row is not None and row.last_sync_at is not None:
        stamp = format_jalali(row.last_sync_at)
        note = sync_result_note(row.last_sync_complete, row.last_sync_done, row.last_sync_total, row.last_sync_listed)
        report = _report_out(row.last_sync_report)
    return DivarColleaguesOut(
        url=url,
        posts_url=posts_url,
        items=_divar_items(db, business_token),
        last_sync_at=stamp,
        last_sync_note=note,
        last_sync_report=report,
    )


def _sync_out() -> DivarSyncOut:
    status = sync_status()
    return DivarSyncOut(
        running=status.running,
        needs_login=status.needs_login,
        colleagues_ready=status.colleagues_ready,
        total=status.total,
        completed=status.completed,
        sent=status.sent,
        skipped=status.skipped,
        removed=status.removed,
        errors=list(status.errors),
        message=status.message,
        phase=status.phase,
        current_index=status.current_index,
        current_title=status.current_title,
        current_author=status.current_author,
        paused=status.paused,
    )


@router.get("/divar/colleagues", response_model=DivarColleaguesOut)
def list_divar_colleagues(db: Session = Depends(get_db)) -> DivarColleaguesOut:
    url, posts_url, token, _ = _divar_state(db)
    return _colleagues_out(db, url, posts_url, token)


@router.post("/divar/link", response_model=DivarColleaguesOut)
def save_divar_link(body: DivarLinkIn, db: Session = Depends(get_db)) -> DivarColleaguesOut:
    row = save_agent_management_link(db, body.url)
    return _colleagues_out(db, row.url, row.posts_url, row.business_token)


@router.post("/divar/posts-link", response_model=DivarColleaguesOut)
def save_divar_posts_link(body: DivarLinkIn, db: Session = Depends(get_db)) -> DivarColleaguesOut:
    row = save_posts_link(db, body.url)
    return _colleagues_out(db, row.url, row.posts_url, row.business_token)


@router.post("/divar/refresh", response_model=DivarRefreshOut)
def refresh_divar_colleagues(db: Session = Depends(get_db)) -> DivarRefreshOut:
    url, _, _, items = _divar_state(db)
    try:
        _, added, removed, updated, _diff = refresh_colleagues(db)
    except DivarLoginRequired:
        return DivarRefreshOut(needs_login=True, url=url, items=items)
    _, _, _, items = _divar_state(db)
    return DivarRefreshOut(added=added, removed=removed, updated=updated, url=url, items=items)


@router.post("/divar/sync", response_model=DivarSyncOut)
async def begin_divar_sync() -> DivarSyncOut:
    await start_sync()
    return _sync_out()


@router.get("/divar/sync", response_model=DivarSyncOut)
def read_divar_sync() -> DivarSyncOut:
    return _sync_out()


@router.post("/divar/sync/pause", response_model=DivarSyncOut)
def pause_divar_sync() -> DivarSyncOut:
    pause_sync()
    return _sync_out()


@router.post("/divar/sync/resume", response_model=DivarSyncOut)
def resume_divar_sync() -> DivarSyncOut:
    resume_sync()
    return _sync_out()


@router.post("/divar/sync/cancel", response_model=DivarSyncOut)
def cancel_divar_sync() -> DivarSyncOut:
    cancel_sync()
    return _sync_out()


@router.delete("/divar/data", response_model=DivarColleaguesOut)
def delete_divar_data(db: Session = Depends(get_db)) -> DivarColleaguesOut:
    if sync_status().running:
        raise HTTPException(status_code=409, detail="اول بروزرسانی را ببندید، بعد اطلاعات را حذف کنید.")
    db.query(Listing).delete(synchronize_session=False)
    db.query(DivarColleague).delete(synchronize_session=False)
    row = db.get(DivarConnection, 1)
    if row is not None:
        row.last_sync_at = None
        row.last_sync_complete = False
        row.last_sync_done = 0
        row.last_sync_total = 0
        row.last_sync_listed = False
        row.last_sync_report = None
    db.commit()
    url, posts_url, token, _ = _divar_state(db)
    return _colleagues_out(db, url, posts_url, token)


@router.post("/divar/login/start")
def start_divar_otp(body: DivarPhoneIn, db: Session = Depends(get_db)) -> dict:
    start_divar_login(db, body.phone)
    return {"ok": True}


@router.post("/divar/login/confirm")
def confirm_divar_otp(body: DivarCodeIn, db: Session = Depends(get_db)) -> dict:
    confirm_divar_login(db, body.code)
    return {"ok": True}
