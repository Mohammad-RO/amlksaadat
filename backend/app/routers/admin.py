from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Agent, DivarConnection, Listing
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    DivarCodeIn,
    DivarColleagueOut,
    DivarColleaguesOut,
    DivarLinkIn,
    DivarPhoneIn,
    DivarRefreshOut,
    ReportOut,
    ReportRow,
)
from app.services.divar_panel import (
    DivarLoginRequired,
    colleague_rows,
    confirm_divar_login,
    refresh_colleagues,
    save_agent_management_link,
    start_divar_login,
)
from app.utils import normalize_phone, parse_report_bound

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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


@router.get("/reports", response_model=ReportOut)
def reports(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> ReportOut:
    join_on = Listing.agent_id == Agent.id
    try:
        start = parse_report_bound(date_from, end_of_day=False) if date_from else None
        end = parse_report_bound(date_to, end_of_day=True) if date_to else None
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail="بازه تاریخ معتبر نیست. نمونه: 1404/08/01") from exc
    if start and end and start >= end:
        raise HTTPException(status_code=400, detail="تاریخ شروع باید قبل از تاریخ پایان باشد.")
    if start:
        join_on = and_(join_on, Listing.created_at >= start)
    if end:
        join_on = and_(join_on, Listing.created_at < end)

    rows = (
        db.query(Agent, func.count(Listing.id))
        .outerjoin(Listing, join_on)
        .group_by(Agent.id, Agent.name, Agent.phone, Agent.is_active, Agent.created_at, Agent.updated_at)
        .order_by(func.count(Listing.id).desc(), Agent.name)
        .all()
    )
    return ReportOut(
        date_from=date_from,
        date_to=date_to,
        items=[
            ReportRow(
                agent_id=agent.id,
                name=agent.name,
                phone=agent.phone,
                is_active=agent.is_active,
                listings_count=count,
            )
            for agent, count in rows
        ],
    )


def _divar_items(db: Session, business_token: str) -> list[DivarColleagueOut]:
    return [DivarColleagueOut(id=row.id, name=row.name, phone=row.phone) for row in colleague_rows(db, business_token)]


def _divar_state(db: Session) -> tuple[str, str, list[DivarColleagueOut]]:
    row = db.get(DivarConnection, 1)
    url = row.url if row else ""
    token = row.business_token if row else ""
    return url, token, _divar_items(db, token)


@router.get("/divar/colleagues", response_model=DivarColleaguesOut)
def list_divar_colleagues(db: Session = Depends(get_db)) -> DivarColleaguesOut:
    url, _, items = _divar_state(db)
    return DivarColleaguesOut(url=url, items=items)


@router.post("/divar/link", response_model=DivarColleaguesOut)
def save_divar_link(body: DivarLinkIn, db: Session = Depends(get_db)) -> DivarColleaguesOut:
    row = save_agent_management_link(db, body.url)
    return DivarColleaguesOut(url=row.url, items=_divar_items(db, row.business_token))


@router.post("/divar/refresh", response_model=DivarRefreshOut)
def refresh_divar_colleagues(db: Session = Depends(get_db)) -> DivarRefreshOut:
    url, _, items = _divar_state(db)
    try:
        _, added, removed, updated = refresh_colleagues(db)
    except DivarLoginRequired:
        return DivarRefreshOut(needs_login=True, url=url, items=items)
    _, token, items = _divar_state(db)
    return DivarRefreshOut(added=added, removed=removed, updated=updated, url=url, items=items)


@router.post("/divar/login/start")
def start_divar_otp(body: DivarPhoneIn, db: Session = Depends(get_db)) -> dict:
    start_divar_login(db, body.phone)
    return {"ok": True}


@router.post("/divar/login/confirm")
def confirm_divar_otp(body: DivarCodeIn, db: Session = Depends(get_db)) -> dict:
    confirm_divar_login(db, body.code)
    return {"ok": True}
