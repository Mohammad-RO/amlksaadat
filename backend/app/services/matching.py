import math

from sqlalchemy.orm import Session

from app.models import Listing


def match_listings(
    db: Session,
    area: float,
    price: int,
    bedrooms: int,
    bedrooms_or_more: bool = False,
) -> list[Listing]:
    low_price = math.floor(price * 0.85)
    high_price = math.ceil(price * 1.15)
    low_area = area * 0.85
    high_area = area * 1.15
    bedroom_filter = Listing.bedrooms >= bedrooms if bedrooms_or_more else Listing.bedrooms == bedrooms
    return (
        db.query(Listing)
        .filter(
            Listing.area.is_not(None),
            Listing.price.is_not(None),
            bedroom_filter,
            Listing.area >= low_area,
            Listing.area <= high_area,
            Listing.price >= low_price,
            Listing.price <= high_price,
        )
        .order_by(Listing.created_at.desc())
        .limit(15)
        .all()
    )
