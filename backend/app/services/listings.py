import random
import re

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Agent, Listing
from app.services.archive import archive_configured, archive_images, archive_text
from app.services.divar import DivarPost, fetch_divar_post
from app.services.llm import compose_listing_text, images_belong_to_listing, rewrite_description
from app.utils import duplicate_message, extract_divar_token, format_price, format_toman, format_toman_range


IMPORT_PHONE = "09000000000"
IMPORT_NAME = "ورود دیوار"


def import_agent(db: Session) -> Agent:
    agent = db.query(Agent).filter(Agent.phone == IMPORT_PHONE).one_or_none()
    if agent is None:
        agent = Agent(name=IMPORT_NAME, phone=IMPORT_PHONE, is_active=False)
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent


def _unique_code(db: Session) -> str:
    for _ in range(40):
        code = f"{random.randint(0, 99_999_999):08d}"
        exists = db.query(Listing.id).filter(Listing.unique_code == code).first()
        if not exists:
            return code
    raise AppError("ساخت کد یکتا ممکن نشد. دوباره تلاش کنید.", 500)


def visible_image_urls(post: DivarPost) -> list[str]:
    if not images_belong_to_listing(post.specs):
        return []
    return list(post.image_urls)


def stored_fact_text(structured: str) -> str:
    lines = [line for line in (structured or "").splitlines() if not re.match(r"^\s*کد\s*[:：]", line)]
    text = "\n".join(lines).strip()
    marker = "📝 توضیحات"
    if marker in text:
        text = text.split(marker, 1)[0].strip()
    return text


def listing_content_changed(listing: Listing, post: DivarPost) -> bool:
    title = post.title or "آگهی دیوار"
    same_fields = (
        (listing.title or "") == title
        and listing.area == post.area
        and listing.price == post.price
        and listing.bedrooms == post.bedrooms
        and listing.building_year == post.building_year
        and (listing.category or "") == (post.category or "")
        and (listing.deal_type or "") == (post.deal_type or "")
        and listing.deposit == post.deposit
        and listing.rent == post.rent
        and listing.deposit_min == post.deposit_min
        and listing.deposit_max == post.deposit_max
        and listing.rent_min == post.rent_min
        and listing.rent_max == post.rent_max
        and bool(listing.rent_convertible) == bool(post.rent_convertible)
        and list(listing.image_urls or []) == visible_image_urls(post)
    )
    if not same_fields:
        return True
    return stored_fact_text(listing.structured_text) != compose_listing_text(post, "").strip()


def _plain_number(value: float | int | None) -> str:
    if value is None:
        return "نامشخص"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _money_span(low: int | None, high: int | None, single: int | None, *, high_first: bool = False) -> str:
    text = format_toman_range(low, high, high_first=high_first)
    if text:
        return text
    if single is not None:
        return format_toman(single)
    return "نامشخص"


def _spec_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        sep = ":" if ":" in raw else ("：" if "：" in raw else "")
        if not sep:
            continue
        left, right = raw.split(sep, 1)
        match = re.search(r"[\w\u0600-\u06FF].*", left.strip())
        title = match.group(0).strip() if match else left.strip()
        value = right.strip()
        if title and value:
            rows.append((title, value))
    return rows


def _spec_cover(title: str) -> str | None:
    if "متراژ" in title:
        return "area"
    if "خواب" in title or "اتاق" in title:
        return "rooms"
    if "ساخت" in title:
        return "year"
    if "قیمت" in title:
        return "price"
    if "ودیعه" in title and "اجاره" in title:
        return "convertible"
    if "ودیعه" in title:
        return "deposit"
    if "اجاره" in title:
        return "rent"
    return None


def describe_listing_changes(listing: Listing, post: DivarPost) -> list[dict]:
    if not listing_content_changed(listing, post):
        return []
    changes: list[dict] = []
    emitted: set[str] = set()

    def add(key: str, label: str, old: str, new: str) -> None:
        if old == new:
            return
        emitted.add(key)
        changes.append({"label": label, "old": old, "new": new})

    add("title", "عنوان", listing.title or "", post.title or "آگهی دیوار")
    add("area", "متراژ", _plain_number(listing.area), _plain_number(post.area))
    add("price", "قیمت", format_price(listing.price), format_price(post.price))
    add("rooms", "خواب", _plain_number(listing.bedrooms), _plain_number(post.bedrooms))
    add("year", "سال ساخت", _plain_number(listing.building_year), _plain_number(post.building_year))
    add(
        "deposit",
        "ودیعه",
        _money_span(listing.deposit_min, listing.deposit_max, listing.deposit),
        _money_span(post.deposit_min, post.deposit_max, post.deposit),
    )
    add(
        "rent",
        "اجاره",
        _money_span(listing.rent_min, listing.rent_max, listing.rent, high_first=True),
        _money_span(post.rent_min, post.rent_max, post.rent, high_first=True),
    )
    add(
        "convertible",
        "قابل تبدیل",
        "قابل تبدیل" if listing.rent_convertible else "غیر قابل تبدیل",
        "قابل تبدیل" if post.rent_convertible else "غیر قابل تبدیل",
    )
    categories = {"residential": "مسکونی", "commercial": "اداری"}
    deals = {"sell": "فروش", "rent": "اجاره"}
    add(
        "category",
        "دسته",
        categories.get(listing.category or "", listing.category or "نامشخص"),
        categories.get(post.category or "", post.category or "نامشخص"),
    )
    add(
        "deal",
        "نوع معامله",
        deals.get(listing.deal_type or "", listing.deal_type or "نامشخص"),
        deals.get(post.deal_type or "", post.deal_type or "نامشخص"),
    )
    old_specs: dict[str, list[str]] = {}
    new_specs: dict[str, list[str]] = {}
    order: list[str] = []
    for title, value in _spec_rows(stored_fact_text(listing.structured_text)):
        old_specs.setdefault(title, []).append(value)
        if title not in order:
            order.append(title)
    for title, value in _spec_rows(compose_listing_text(post, "").strip()):
        new_specs.setdefault(title, []).append(value)
        if title not in order:
            order.append(title)
    for title in order:
        cover = _spec_cover(title)
        if cover and cover in emitted:
            continue
        old_values = old_specs.get(title, [])
        new_values = new_specs.get(title, [])
        for index in range(max(len(old_values), len(new_values))):
            old = old_values[index] if index < len(old_values) else "نبود"
            new = new_values[index] if index < len(new_values) else "حذف شد"
            if old != new:
                changes.append({"label": title, "old": old, "new": new})
    if list(listing.image_urls or []) != visible_image_urls(post):
        changes.append({"label": "عکس‌ها", "old": "", "new": "عوض شد"})
    if not changes:
        changes.append({"label": "مشخصات", "old": "نسخه ذخیره‌شده", "new": "نسخه دیوار"})
    return changes


async def refresh_listing_content(db: Session, listing: Listing) -> list[dict]:
    post = await fetch_divar_post(listing.divar_token)
    if post.category not in {"residential", "commercial"} or post.deal_type not in {"sell", "rent"}:
        raise AppError("دسته این آگهی در دیوار جزو فروش یا اجارهٔ مسکونی و اداری نیست.", 400)
    changes = describe_listing_changes(listing, post)
    if not changes:
        return []
    rewritten, llm_used = await rewrite_description(post.description)
    structured = compose_listing_text(post, rewritten).rstrip()
    structured = f"{structured}\n\nکد: {listing.unique_code}" if structured else f"کد: {listing.unique_code}"
    image_urls = visible_image_urls(post)
    if image_urls != list(listing.image_urls or []):
        file_ids = await archive_images(image_urls)
    else:
        file_ids = list(listing.image_file_ids or [])
    listing.title = post.title or "آگهی دیوار"
    listing.area = post.area
    listing.price = post.price
    listing.bedrooms = post.bedrooms
    listing.building_year = post.building_year
    listing.category = post.category
    listing.deal_type = post.deal_type
    listing.deposit = post.deposit
    listing.rent = post.rent
    listing.deposit_min = post.deposit_min
    listing.deposit_max = post.deposit_max
    listing.rent_min = post.rent_min
    listing.rent_max = post.rent_max
    listing.rent_convertible = bool(post.rent_convertible)
    listing.raw_description = post.description
    listing.structured_text = structured
    listing.image_urls = image_urls
    listing.image_file_ids = file_ids
    listing.llm_used = llm_used
    db.commit()
    await archive_text(structured)
    return changes


def _searchable(listing: Listing) -> bool:
    if listing.category not in {"residential", "commercial"}:
        return False
    if listing.deal_type not in {"sell", "rent"}:
        return False
    if listing.area is None or listing.bedrooms is None or listing.building_year is None:
        return False
    if listing.deal_type == "sell":
        return listing.price is not None
    return listing.deposit_min is not None and listing.rent_min is not None


async def register_listing(
    db: Session,
    agent: Agent,
    divar_url: str,
    consultant_name: str = "",
    consultant_phone: str = "",
) -> tuple[Listing, list[str]]:
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
    if post.category not in {"residential", "commercial"} or post.deal_type not in {"sell", "rent"}:
        raise AppError("دسته این آگهی در دیوار جزو فروش یا اجارهٔ مسکونی و اداری نیست.", 400)
    rewritten, llm_used = await rewrite_description(post.description)
    code = _unique_code(db)
    structured = compose_listing_text(post, rewritten).rstrip()
    structured = f"{structured}\n\nکد: {code}" if structured else f"کد: {code}"
    image_urls = visible_image_urls(post)
    file_ids = await archive_images(image_urls)

    listing = Listing(
        agent_id=agent.id,
        divar_url=raw_url,
        divar_token=token,
        title=post.title or "آگهی دیوار",
        area=post.area,
        price=post.price,
        bedrooms=post.bedrooms,
        building_year=post.building_year,
        category=post.category,
        deal_type=post.deal_type,
        deposit=post.deposit,
        rent=post.rent,
        deposit_min=post.deposit_min,
        deposit_max=post.deposit_max,
        rent_min=post.rent_min,
        rent_max=post.rent_max,
        rent_convertible=bool(post.rent_convertible),
        raw_description=post.description,
        structured_text=structured,
        unique_code=code,
        image_file_ids=file_ids,
        image_urls=image_urls,
        consultant_name=consultant_name,
        consultant_phone=consultant_phone,
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
    if not _searchable(listing):
        warnings.append(
            "بعضی از مشخصات از دیوار خوانده نشد. اگر خریدار همان مورد را انتخاب کند، این آگهی در نتایج نمی‌آید."
        )
    if post.description and not listing.llm_used:
        warnings.append("متن توضیحات بدون بازنویسی مدل زبانی ذخیره شد.")
    if image_urls and len(file_ids) < len(image_urls):
        missing = len(image_urls) - len(file_ids)
        if archive_configured():
            warnings.append(f"{missing} عکس از {len(image_urls)} بعد از چند بار تلاش به کانال نرسید.")
        else:
            warnings.append(
                "عکس‌ها در کانال آرشیو تلگرام ذخیره نشدند. شناسه کانال خصوصی را در TELEGRAM_ARCHIVE_CHAT_ID قرار دهید و ربات را ادمین آن کانال کنید."
            )
    return listing, warnings
