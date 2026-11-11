import random

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Agent, Listing
from app.services.archive import archive_images
from app.services.divar import fetch_divar_post
from app.services.llm import compose_listing_text, rewrite_description
from app.utils import duplicate_message, extract_divar_token


def _unique_code(db: Session) -> str:
    for _ in range(40):
        code = f"{random.randint(0, 99_999_999):08d}"
        exists = db.query(Listing.id).filter(Listing.unique_code == code).first()
        if not exists:
            return code
    raise AppError("ساخت کد یکتا ممکن نشد. دوباره تلاش کنید.", 500)


async def register_listing(db: Session, agent: Agent, divar_url: str) -> tuple[Listing, list[str]]:
    raw_url = divar_url.strip()
    if "divar.ir" not in raw_url.lower():
        raise AppError("لینک دیوار معتبر نیست.", 400)
    token = extract_divar_token(raw_url)
    if not token:
        raise AppError("توکن آگهی از انتهای لینک دیوار خوانده نشد.", 400)

    existing = db.query(Listing).filter(Listing.divar_token == token).one_or_none()
    if existing:
        raise AppError(duplicate_message(existing.agent.name, existing.created_at), 409)

    post = await fetch_divar_post(token)
    rewritten, llm_used = await rewrite_description(post.description)
    code = _unique_code(db)
    structured = compose_listing_text(post, rewritten).rstrip()
    structured = f"{structured}\n\nکد: {code}" if structured else f"کد: {code}"
    file_ids = await archive_images(post.image_urls)

    listing = Listing(
        agent_id=agent.id,
        divar_url=raw_url,
        divar_token=token,
        title=post.title or "آگهی دیوار",
        area=post.area,
        price=post.price,
        bedrooms=post.bedrooms,
        building_year=post.building_year,
        raw_description=post.description,
        structured_text=structured,
        unique_code=code,
        image_file_ids=file_ids,
        image_urls=post.image_urls,
        llm_used=llm_used,
    )
    db.add(listing)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raced = db.query(Listing).filter(Listing.divar_token == token).one_or_none()
        if raced:
            raise AppError(duplicate_message(raced.agent.name, raced.created_at), 409) from exc
        raise
    db.refresh(listing)

    warnings: list[str] = []
    if (
        listing.area is None
        or listing.price is None
        or listing.bedrooms is None
        or listing.building_year is None
    ):
        warnings.append(
            "بعضی از مشخصات از دیوار خوانده نشد. اگر خریدار همان مورد را انتخاب کند، این آگهی در نتایج نمی‌آید."
        )
    if post.description and not listing.llm_used:
        warnings.append("متن توضیحات بدون بازنویسی مدل زبانی ذخیره شد.")
    if post.image_urls and not file_ids:
        warnings.append(
            "عکس‌ها در کانال آرشیو تلگرام ذخیره نشدند. شناسه کانال خصوصی را در TELEGRAM_ARCHIVE_CHAT_ID قرار دهید و ربات را ادمین آن کانال کنید."
        )
    return listing, warnings
