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


def _intersect(a: tuple[float, float] | None, b: tuple[float, float] | None) -> tuple[float, float] | None:
    if a is None or b is None:
        return None
    left = max(a[0], b[0])
    right = min(a[1], b[1])
    if left > right + 1e-9:
        return None
    return (left, right)


def _interval_leq(v1: float, v2: float, limit: float | None) -> tuple[float, float] | None:
    if limit is None:
        return (0.0, 1.0)
    delta = v2 - v1
    if abs(delta) < 1e-9:
        return (0.0, 1.0) if v1 <= limit + 1e-6 else None
    if delta > 0:
        t_max = (limit - v1) / delta
        if t_max < 0:
            return None
        return (0.0, min(1.0, t_max))
    t_min = (limit - v1) / delta
    if t_min > 1:
        return None
    return (max(0.0, t_min), 1.0)


def _interval_geq(v1: float, v2: float, limit: float | None) -> tuple[float, float] | None:
    if limit is None:
        return (0.0, 1.0)
    delta = v2 - v1
    if abs(delta) < 1e-9:
        return (0.0, 1.0) if v1 >= limit - 1e-6 else None
    if delta > 0:
        t_min = (limit - v1) / delta
        if t_min > 1:
            return None
        return (max(0.0, t_min), 1.0)
    t_max = (limit - v1) / delta
    if t_max < 0:
        return None
    return (0.0, min(1.0, t_max))


def _interval_eq_zero(v1: float, v2: float) -> tuple[float, float] | None:
    if abs(v1) <= 1e-6 and abs(v2) <= 1e-6:
        return (0.0, 1.0)
    if abs(v1) <= 1e-6:
        return (0.0, 0.0)
    if abs(v2) <= 1e-6:
        return (1.0, 1.0)
    if v1 == v2:
        return None
    t = -v1 / (v2 - v1)
    if 0.0 - 1e-9 <= t <= 1.0 + 1e-9:
        t = min(1.0, max(0.0, t))
        return (t, t)
    return None


def _bounds_intervals(
    v1: float,
    v2: float,
    bounds: tuple[int | None, int | None] | None,
) -> tuple[float, float] | None:
    if bounds is None:
        return (0.0, 1.0)
    low, high = bounds
    if low == 0 and high == 0:
        return _interval_eq_zero(v1, v2)
    low, high = _expand_bounds(low, high, lower=False, upper=True)
    interval = (0.0, 1.0)
    interval = _intersect(interval, _interval_geq(v1, v2, float(low) if low is not None else None))
    interval = _intersect(interval, _interval_leq(v1, v2, float(high) if high is not None else None))
    return interval


def _convert_endpoints(listing: Listing) -> tuple[tuple[float, float], tuple[float, float]] | None:
    d_min = listing.deposit_min
    d_max = listing.deposit_max
    r_min = listing.rent_min
    r_max = listing.rent_max
    if d_min is None or d_max is None or r_min is None or r_max is None:
        return None
    if listing.rent_convertible and (d_min != d_max or r_min != r_max):
        # Divar convert: lower deposit pairs with higher rent.
        return (float(d_min), float(r_max)), (float(d_max), float(r_min))
    return (float(d_min), float(r_min)), (float(d_max), float(r_max))


def _rent_money_matches(
    listing: Listing,
    deposit: tuple[int | None, int | None] | None,
    rent: tuple[int | None, int | None] | None,
) -> bool:
    if deposit is None and rent is None:
        return True
    endpoints = _convert_endpoints(listing)
    if endpoints is None:
        return False
    (d1, r1), (d2, r2) = endpoints
    interval = (0.0, 1.0)
    interval = _intersect(interval, _bounds_intervals(d1, d2, deposit))
    interval = _intersect(interval, _bounds_intervals(r1, r2, rent))
    return interval is not None


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

    if deposit is not None or rent is not None:
        query = query.filter(Listing.deposit_min.is_not(None), Listing.rent_min.is_not(None))
        # Necessary loose filters to shrink candidates before exact line check.
        if deposit is not None:
            d_low, d_high = deposit
            if not (d_low == 0 and d_high == 0):
                d_low, d_high = _expand_bounds(d_low, d_high, lower=False, upper=True)
                if d_high is not None:
                    query = query.filter(Listing.deposit_min <= d_high)
                if d_low is not None:
                    query = query.filter(Listing.deposit_max >= d_low)
        if rent is not None:
            r_low, r_high = rent
            if r_low == 0 and r_high == 0:
                query = query.filter(Listing.rent_min == 0)
            else:
                r_low, r_high = _expand_bounds(r_low, r_high, lower=False, upper=True)
                if r_high is not None:
                    query = query.filter(Listing.rent_min <= r_high)
                if r_low is not None:
                    query = query.filter(Listing.rent_max >= r_low)

    rows = query.order_by(Listing.created_at.desc()).limit(80).all()
    if deposit is None and rent is None:
        return rows[:15]
    matched = [row for row in rows if _rent_money_matches(row, deposit, rent)]
    return matched[:15]
