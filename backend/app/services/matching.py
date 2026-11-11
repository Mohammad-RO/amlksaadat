from sqlalchemy.orm import Session

from app.models import Listing
from app.utils import current_jalali_year


def match_listings(
    db: Session,
    area: tuple[float | None, float | None] | None = None,
    price: tuple[int | None, int | None] | None = None,
    bedrooms: int | None = None,
    bedrooms_or_more: bool = False,
    age: tuple[int | None, int | None] | None = None,
    now_year: int | None = None,
) -> list[Listing]:
    query = db.query(Listing)
    if area is not None:
        low, high = area
        query = query.filter(Listing.area.is_not(None))
        if low is not None:
            query = query.filter(Listing.area >= low)
        if high is not None:
            query = query.filter(Listing.area <= high)
    if price is not None:
        low, high = price
        query = query.filter(Listing.price.is_not(None))
        if low is not None:
            query = query.filter(Listing.price >= low)
        if high is not None:
            query = query.filter(Listing.price <= high)
    if bedrooms is not None:
        if bedrooms_or_more:
            query = query.filter(Listing.bedrooms >= bedrooms)
        else:
            query = query.filter(Listing.bedrooms == bedrooms)
    if age is not None:
        low, high = age
        year = current_jalali_year() if now_year is None else now_year
        query = query.filter(Listing.building_year.is_not(None))
        if low is not None:
            query = query.filter(Listing.building_year <= year - int(low))
        if high is not None:
            query = query.filter(Listing.building_year >= year - int(high))
    return query.order_by(Listing.created_at.desc()).limit(15).all()
