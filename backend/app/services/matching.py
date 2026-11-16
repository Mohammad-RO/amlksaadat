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


def _apply_money_bounds(query, column, bounds: tuple[int | None, int | None] | None):
    if bounds is None:
        return query
    low, high = bounds
    query = query.filter(column.is_not(None))
    if low == 0 and high == 0:
        return query.filter(column == 0)
    low, high = _expand_bounds(low, high, lower=False, upper=True)
    if low is not None:
        query = query.filter(column >= low)
    if high is not None:
        query = query.filter(column <= high)
    return query


def match_listings(
    db: Session,
    area: tuple[float | None, float | None] | None = None,
    price: tuple[int | None, int | None] | None = None,
    bedrooms: int | None = None,
    bedrooms_or_more: bool = False,
    age: tuple[int | None, int | None] | None = None,
    now_year: int | None = None,
    category: str | None = None,
    deal_type: str | None = None,
    deposit: tuple[int | None, int | None] | None = None,
    rent: tuple[int | None, int | None] | None = None,
) -> list[Listing]:
    query = db.query(Listing)
    if category:
        query = query.filter(Listing.category == category)
    if deal_type:
        query = query.filter(Listing.deal_type == deal_type)
    if area is not None:
        area = _expand_bounds(*area, lower=True, upper=True)
        low, high = area
        query = query.filter(Listing.area.is_not(None))
        if low is not None:
            query = query.filter(Listing.area >= low)
        if high is not None:
            query = query.filter(Listing.area <= high)
    query = _apply_money_bounds(query, Listing.price, price)
    query = _apply_money_bounds(query, Listing.deposit, deposit)
    query = _apply_money_bounds(query, Listing.rent, rent)
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
