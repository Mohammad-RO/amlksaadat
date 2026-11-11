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
