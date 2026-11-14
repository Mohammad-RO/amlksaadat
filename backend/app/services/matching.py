from sqlalchemy.orm import Session

from app.models import Listing
from app.utils import current_jalali_year

TOLERANCE = 0.05


def _expand_bounds(low, high, *, lower: bool, upper: bool):
    if lower and low is not None:
        low = low * (1 - TOLERANCE)
    if upper and high is not None:
        high = high * (1 + TOLERANCE)
    return low, high


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
        area = _expand_bounds(*area, lower=True, upper=True)
        low, high = area
        query = query.filter(Listing.area.is_not(None))
        if low is not None:
            query = query.filter(Listing.area >= low)
        if high is not None:
            query = query.filter(Listing.area <= high)
    if price is not None:
        price = _expand_bounds(*price, lower=False, upper=True)
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
        low, high = _expand_bounds(*age, lower=True, upper=True)
        year = current_jalali_year() if now_year is None else now_year
        query = query.filter(Listing.building_year.is_not(None))
        if low is not None:
            query = query.filter(Listing.building_year <= year - low)
        if high is not None:
            query = query.filter(Listing.building_year >= year - high)
    return query.order_by(Listing.created_at.desc()).limit(15).all()
