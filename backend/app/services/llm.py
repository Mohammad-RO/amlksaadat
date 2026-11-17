import asyncio
import logging
import re

from openai import OpenAI

from app.config import settings
from app.services.divar import DivarPost
from app.utils import format_toman_range

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
«لطفاً متن زیر را با دقت بخوان و آن را به یک لیست بولت‌دار (نقطه‌ای) خلاصه و ساختاریافته تبدیل کن.

قوانین:

فقط نکات کلیدی، مفاهیم اصلی و اطلاعات مهم را استخراج کن.

جملات را کوتاه، خوانا و واضح بنویس و از توضیحات اضافی بپرهیز.

هر نکته را با یک بولت (-) مشخص کن.

لحن و معنای اصلی متن را تغییر نده.

"""

ICON_RULES = (
    ("هر متر", "📏"),
    ("متری", "📏"),
    ("متراژ", "📐"),
    ("خواب", "🛏"),
    ("اتاق", "🛏"),
    ("سال ساخت", "🏗️"),
    ("ساخت", "🏗️"),
    ("سن بنا", "🏗️"),
    ("قیمت کل", "💰"),
    ("قیمت", "💰"),
    ("ودیعه و اجاره", "🔄"),
    ("ودیعه", "💰"),
    ("اجاره", "💵"),
    ("طبقه", "🏢"),
    ("آسانسور", "🛗"),
    ("پارکینگ", "🅿️"),
    ("انبار", "📦"),
    ("بالکن", "🪟"),
    ("تراس", "🪟"),
    ("سرویس", "🚿"),
    ("بهداشت", "🚿"),
    ("جهت", "🧭"),
    ("نما", "🧭"),
    ("سند", "📄"),
    ("آشپز", "🍳"),
    ("کابینت", "🗄️"),
    ("گرمایش", "🔥"),
    ("سرمایش", "❄️"),
    ("کولر", "❄️"),
    ("وام", "🏦"),
    ("واحد", "🚪"),
    ("موقعیت", "📍"),
    ("محله", "📍"),
)


def icon_for(title: str) -> str:
    for keyword, icon in ICON_RULES:
        if keyword in title:
            return icon
    return "•"


_SHARED_FACT_FIELDS = (
    ("متراژ", ("متراژ",), ()),
    ("اتاق", ("اتاق", "خواب"), ()),
    ("طبقه", ("طبقه",), ("واحد",)),
    ("تعداد واحد", ("تعداد واحد", "واحد"), ("طبقه",)),
    ("ساخت", ("سال ساخت", "سن بنا", "ساخت"), ()),
)
_SELL_FACT_FIELDS = _SHARED_FACT_FIELDS + (
    ("قیمت کل", ("قیمت کل", "قیمت"), ("متر",)),
    ("قیمت هر متر", ("هر متر", "متری"), ()),
)
_RENT_FACT_FIELDS = _SHARED_FACT_FIELDS + (
    ("ودیعه", ("ودیعه",), ("اجاره",)),
    ("اجاره ماهانه", ("اجاره ماهانه", "اجارهٔ ماهانه", "اجاره"), ("ودیعه", "تبدیل")),
    ("ودیعه و اجاره", ("ودیعه و اجاره",), ()),
)


def _line_title(line: str) -> str | None:
    separator = "：" if "：" in line else ":"
    if separator not in line:
        return None
    left, _right = line.split(separator, 1)
    parts = left.strip().split()
    if parts and not re.search(r"[\u0600-\u06FF]", parts[0]):
        parts = parts[1:]
    title = " ".join(parts).strip()
    return title or None


def _is_fact_title(title: str, fields: tuple = _SELL_FACT_FIELDS) -> bool:
    for _label, keys, blocked in fields:
        if any(key in title for key in keys) and not any(word in title for word in blocked):
            return True
    return False


def _spec_pairs_from_text(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        compact = stripped.replace(" ", "")
        if stripped.startswith("📝") or stripped == "توضیحات" or compact.startswith("کد:") or compact.startswith("کد："):
            break
        title = _line_title(stripped)
        if title is None:
            continue
        value = stripped.split("：" if "：" in stripped else ":", 1)[1].strip()
        if value:
            pairs.append((title, value))
    return pairs


def _looks_like_rent(pairs: list[tuple[str, str]]) -> bool:
    for title, _value in pairs:
        if "ودیعه" in title:
            return True
        if "اجاره" in title and "قیمت" not in title:
            return True
    return False


def _fact_fields_for(pairs: list[tuple[str, str]]):
    return _RENT_FACT_FIELDS if _looks_like_rent(pairs) else _SELL_FACT_FIELDS


def _fact_value(pairs: list[tuple[str, str]], keys: tuple[str, ...], blocked: tuple[str, ...]) -> str | None:
    for key in keys:
        for title, value in pairs:
            if key in title and not any(word in title for word in blocked):
                return value
    return None


def listing_facts(text: str) -> str:
    pairs = _spec_pairs_from_text(text)
    lines = []
    for label, keys, blocked in _fact_fields_for(pairs):
        value = _fact_value(pairs, keys, blocked) or "نامشخص"
        lines.append(f"{icon_for(label)} {label}: {value}")
    return "\n".join(lines)


def listing_headline(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        compact = stripped.replace(" ", "")
        if stripped.startswith("📝") or stripped == "توضیحات" or compact.startswith("کد:") or compact.startswith("کد："):
            return ""
        if _line_title(stripped) is not None:
            return ""
        return stripped
    return ""


def listing_preview(text: str) -> str:
    facts = listing_facts(text)
    headline = listing_headline(text)
    if not headline:
        return facts
    return f"{headline}\n\n{facts}"


def _match_text(text: str) -> str:
    folded = (
        text.replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\u200e", "")
        .replace("\u200f", "")
        .replace("\u0640", "")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ة", "ه")
    )
    return re.sub(r"[^\w]", "", folded, flags=re.UNICODE)


def _is_image_ownership_title(title: str) -> bool:
    folded = _match_text(title)
    return ("تصویر" in folded or "تصاویر" in folded) and "همینملک" in folded


def _answer_rejects_images(value: str) -> bool:
    answer = _match_text(value)
    return answer.startswith("منفی") or answer.startswith("خیر") or answer == "نه"


def images_belong_to_listing(specs: list[tuple[str, str]]) -> bool:
    for title, value in specs:
        if not _is_image_ownership_title(title):
            continue
        if _answer_rejects_images(value):
            return False
        return True
    return True


def _is_image_ownership_line(line: str) -> bool:
    return _is_image_ownership_title(line)


def _is_kept_detail_line(line: str, fact_fields: tuple) -> bool:
    stripped = line.strip()
    if not stripped or _is_image_ownership_line(stripped):
        return False
    compact = stripped.replace(" ", "")
    if stripped.startswith("📝") or stripped == "توضیحات" or compact.startswith("کد:") or compact.startswith("کد："):
        return True
    title = _line_title(stripped)
    if title is not None and _is_fact_title(title, fact_fields):
        return False
    return True


def listing_details(text: str) -> str:
    preview = listing_preview(text)
    headline = listing_headline(text)
    fact_fields = _fact_fields_for(_spec_pairs_from_text(text))
    rest = []
    for line in text.splitlines():
        if not _is_kept_detail_line(line, fact_fields):
            continue
        if headline and line.strip() == headline:
            continue
        rest.append(line)
    extra = "\n".join(rest).strip()
    if not extra:
        return preview
    return f"{preview}\n\n{extra}"


def _is_rent_money_title(title: str) -> bool:
    if "ودیعه" in title:
        return True
    if "اجاره" in title and "قیمت" not in title:
        return True
    return False


def _rent_money_specs(post: DivarPost) -> list[tuple[str, str]]:
    deposit_text = format_toman_range(post.deposit_min, post.deposit_max)
    rent_text = format_toman_range(post.rent_min, post.rent_max, high_first=True)
    rows: list[tuple[str, str]] = []
    if deposit_text:
        rows.append(("ودیعه", deposit_text))
    if rent_text:
        rows.append(("اجاره ماهانه", rent_text))
    rows.append(("ودیعه و اجاره", "قابل تبدیل" if post.rent_convertible else "غیر قابل تبدیل"))
    return rows


def compose_listing_text(post: DivarPost, description: str) -> str:
    parts: list[str] = []
    if post.title:
        parts.append(post.title)
    visible_specs = [
        (title, value)
        for title, value in post.specs
        if not _is_image_ownership_title(title)
    ]
    if post.deal_type == "rent":
        visible_specs = [(title, value) for title, value in visible_specs if not _is_rent_money_title(title)]
        money_specs = _rent_money_specs(post)
        insert_at = 0
        for index, (title, _value) in enumerate(visible_specs):
            if any(key in title for key in ("متراژ", "اتاق", "خواب", "ساخت")):
                insert_at = index + 1
        visible_specs = visible_specs[:insert_at] + money_specs + visible_specs[insert_at:]
    spec_lines = [f"{icon_for(title)} {title}: {value}" for title, value in visible_specs]
    if spec_lines:
        parts.append("\n".join(spec_lines))
    cleaned = description.strip()
    if cleaned:
        parts.append(f"📝 توضیحات\n{cleaned}")
    return "\n\n".join(parts).strip()


def _strip_model_code(text: str) -> str:
    kept = [line for line in text.splitlines() if not re.match(r"^\s*کد\s*[:：]", line)]
    return "\n".join(kept).strip()


def _complete(description: str) -> str:
    client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ],
    )
    content = response.choices[0].message.content or ""
    return _strip_model_code(content)


async def rewrite_description(description: str) -> tuple[str, bool]:
    plain = description.strip()
    if not plain:
        return "", False
    if not settings.llm_api_key.strip() or settings.llm_api_key.strip() == "aaa":
        return plain, False
    try:
        text = await asyncio.to_thread(_complete, plain)
    except Exception:
        logger.exception("llm rewrite failed")
        return plain, False
    if len(text) < 8:
        return plain, False
    return text, True
