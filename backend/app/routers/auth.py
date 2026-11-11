from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_password_matches, get_current_payload, require_agent
from app.models import Agent
from app.schemas import AdminLogin, AgentLogin, TokenOut
from app.security import create_token
from app.utils import normalize_phone

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/admin", response_model=TokenOut)
def login_admin(body: AdminLogin) -> TokenOut:
    if not admin_password_matches(body.username.strip(), body.password):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="نام کاربری یا رمز ادمین نادرست است.")
    return TokenOut(
        token=create_token("admin", "admin", "ادمین"),
        role="admin",
        name="ادمین",
    )


@router.post("/agent", response_model=TokenOut)
def login_agent(body: AgentLogin, db: Session = Depends(get_db)) -> TokenOut:
    from fastapi import HTTPException

    try:
        phone = normalize_phone(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    agent = db.query(Agent).filter(Agent.phone == phone).one_or_none()
    if agent is None or not agent.is_active:
        raise HTTPException(status_code=403, detail="این شماره مجاز نیست یا غیرفعال شده است.")
    return TokenOut(token=create_token(str(agent.id), "agent", agent.name), role="agent", name=agent.name)


@router.get("/me", response_model=TokenOut)
def me(payload: dict = Depends(get_current_payload), db: Session = Depends(get_db)) -> TokenOut:
    from fastapi import HTTPException

    role = payload.get("role")
    if role == "admin":
        return TokenOut(token="", role="admin", name="ادمین")
    agent = require_agent(payload, db)
    return TokenOut(token="", role="agent", name=agent.name)
