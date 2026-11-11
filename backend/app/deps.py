import hmac

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Agent
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="ابتدا وارد شوید.")
    try:
        return decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_admin(payload: dict = Depends(get_current_payload)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="دسترسی ادمین لازم است.")
    return payload


def require_agent(
    payload: dict = Depends(get_current_payload),
    db: Session = Depends(get_db),
) -> Agent:
    if payload.get("role") != "agent":
        raise HTTPException(status_code=403, detail="دسترسی مشاور لازم است.")
    agent = db.get(Agent, int(payload["sub"]))
    if agent is None or not agent.is_active:
        raise HTTPException(status_code=401, detail="این شماره مجاز نیست یا غیرفعال شده است.")
    return agent


def _same(left: str, right: str) -> bool:
    left_bytes = left.encode()
    right_bytes = right.encode()
    if len(left_bytes) != len(right_bytes):
        return False
    return hmac.compare_digest(left_bytes, right_bytes)


def admin_password_matches(username: str, password: str) -> bool:
    return _same(username, settings.admin_username) and _same(password, settings.admin_password)
