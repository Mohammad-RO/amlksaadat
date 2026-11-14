import asyncio
import logging
import re

from openai import OpenAI

from app.config import settings
from app.services.divar import DivarPost

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


_FACT_FIELDS = (
    ("متراژ", ("متراژ",), ()),
    ("اتاق", ("اتاق", "خواب"), ()),
    ("طبقه", ("طبقه",), ("واحد",)),
    ("تعداد واحد", ("تعداد واحد", "واحد"), ("طبقه",)),
    ("ساخت", ("سال ساخت", "سن بنا", "ساخت"), ()),
    ("قیمت کل", ("قیمت کل", "قیمت"), ("متر",)),
    ("قیمت هر متر", ("هر متر", "متری"), ()),
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


def _is_fact_title(title: str) -> bool:
    for _label, keys, blocked in _FACT_FIELDS:
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


def _fact_value(pairs: list[tuple[str, str]], keys: tuple[str, ...], blocked: tuple[str, ...]) -> str | None:
    for key in keys:
        for title, value in pairs:
            if key in title and not any(word in title for word in blocked):
                return value
    return None


def listing_facts(text: str) -> str:
    pairs = _spec_pairs_from_text(text)
    lines = []
    for label, keys, blocked in _FACT_FIELDS:
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


def _is_kept_detail_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    compact = stripped.replace(" ", "")
    if stripped.startswith("📝") or stripped == "توضیحات" or compact.startswith("کد:") or compact.startswith("کد："):
        return True
    title = _line_title(stripped)
    if title is not None and _is_fact_title(title):
        return False
    return True


def listing_details(text: str) -> str:
    preview = listing_preview(text)
    headline = listing_headline(text)
    rest = []
    for line in text.splitlines():
        if not _is_kept_detail_line(line):
            continue
        if headline and line.strip() == headline:
            continue
        rest.append(line)
    extra = "\n".join(rest).strip()
    if not extra:
        return preview
    return f"{preview}\n\n{extra}"


def compose_listing_text(post: DivarPost, description: str) -> str:
    parts: list[str] = []
    if post.title:
        parts.append(post.title)
    spec_lines = [f"{icon_for(title)} {title}: {value}" for title, value in post.specs]
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
