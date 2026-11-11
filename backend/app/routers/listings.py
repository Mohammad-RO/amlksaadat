from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_agent
from app.errors import AppError
from app.models import Agent, Listing
from app.schemas import ListingCreate, ListingOut
from app.services.listings import register_listing
from app.utils import format_jalali

router = APIRouter(prefix="/listings", tags=["listings"])


def _out(listing: Listing, warnings: list[str] | None = None) -> ListingOut:
    return ListingOut(
        id=listing.id,
        title=listing.title,
        divar_url=listing.divar_url,
        divar_token=listing.divar_token,
        area=listing.area,
        price=listing.price,
        bedrooms=listing.bedrooms,
        structured_text=listing.structured_text,
        unique_code=listing.unique_code,
        llm_used=listing.llm_used,
        searchable=listing.area is not None and listing.price is not None and listing.bedrooms is not None,
        image_count=max(len(listing.image_file_ids or []), len(listing.image_urls or [])),
        archived=bool(listing.image_file_ids),
        created_at_jalali=format_jalali(listing.created_at),
        warnings=warnings or [],
    )


@router.get("", response_model=list[ListingOut])
def my_listings(agent: Agent = Depends(require_agent), db: Session = Depends(get_db)) -> list[ListingOut]:
    rows = (
        db.query(Listing)
        .filter(Listing.agent_id == agent.id)
        .order_by(Listing.created_at.desc())
        .all()
    )
    return [_out(row) for row in rows]


@router.post("", response_model=ListingOut, status_code=201)
async def create_listing(
    body: ListingCreate,
    agent: Agent = Depends(require_agent),
    db: Session = Depends(get_db),
) -> ListingOut:
    try:
        listing, warnings = await register_listing(db, agent, body.divar_url)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _out(listing, warnings)


@router.delete("/{listing_id}", status_code=204)
def delete_listing(
    listing_id: int,
    agent: Agent = Depends(require_agent),
    db: Session = Depends(get_db),
) -> None:
    listing = db.get(Listing, listing_id)
    if listing is None or listing.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="این آگهی در فهرست شما نیست.")
    db.delete(listing)
    db.commit()
