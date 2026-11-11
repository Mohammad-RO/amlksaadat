import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.errors import AppError
from app.utils import parse_build_year, parse_number

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://divar.ir",
}


@dataclass
class DivarPost:
    title: str
    description: str
    area: float | None
    price: int | None
    bedrooms: int | None
    building_year: int | None
    image_urls: list[str]
    specs: list[tuple[str, str]]


def _score_area(title: str) -> int:
    return 3 if title == "متراژ" or title.startswith("متراژ") else 0


def _score_bedrooms(title: str) -> int:
    if "خواب" in title:
        return 3
    if title in {"اتاق", "تعداد اتاق"}:
        return 2
    return 0


def _score_year(title: str) -> int:
    if "سال ساخت" in title:
        return 4
    if title in {"سن بنا", "سن ساختمان"}:
        return 3
    if "ساخت" in title:
        return 2
    return 0


def _score_price(title: str) -> int:
    if any(word in title for word in ("اجاره", "ودیعه", "رهن")):
        return 0
    if "متری" in title or "هر متر" in title:
        return 0
    if "قیمت کل" in title:
        return 4
    if title == "قیمت":
        return 3
    if "قیمت" in title:
        return 2
    return 0


def _best_value(pairs: list[tuple[str, str]], scorer) -> str | None:
    best_score = 0
    best_value = None
    for title, value in pairs:
        score = scorer(title)
        if score > best_score:
            best_score = score
            best_value = value
    return best_value


def _is_photo(url: str) -> bool:
    lower = url.lower()
    if any(word in lower for word in ("logo", "icon", "sprite", "avatar", "emoji")):
        return False
    return "divarcdn" in lower or bool(re.search(r"\.(jpg|jpeg|png|webp)(?:\?|$)", lower))


def _clean_image(url: str) -> str:
    if "divarcdn" in url.lower():
        return url.split("?")[0]
    return url


SPEC_WIDGETS = {
    "GROUP_INFO_ROW",
    "UNEXPANDABLE_ROW",
    "EXPANDABLE_ROW",
    "FEATURE_ROW",
    "GROUP_FEATURE_ROW",
    "INFO_ROW",
    "SELECTOR_ROW",
}
SKIP_SPEC_TITLES = {"توضیحات", "تماس", "چت", "بازگشت", "اشتراک‌گذاری", "اشتراک گذاری"}


def _spec_value(node: dict) -> str:
    value = node.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip()
    available = node.get("available")
    if isinstance(available, bool):
        return "دارد" if available else "ندارد"
    return ""


def _collect(payload: object) -> tuple[list[tuple[str, str]], list[str], list[str], list[str]]:
    pairs: list[tuple[str, str]] = []
    texts: list[str] = []
    images: list[str] = []
    titles: list[str] = []

    def visit(node: object, in_spec: bool = False) -> None:
        if isinstance(node, dict):
            widget = node.get("widget_type")
            if isinstance(widget, str) and "DESCRIPTION" in widget:
                raw = node.get("data", {}).get("text") if isinstance(node.get("data"), dict) else None
                if not isinstance(raw, str):
                    raw = node.get("text")
                if isinstance(raw, str) and raw.strip():
                    texts.append(raw.strip())
            spec_here = in_spec or widget in SPEC_WIDGETS
            title = node.get("title")
            if isinstance(title, str) and widget in {"TITLE_ROW", "LEGEND_TITLE_ROW"}:
                titles.append(title.strip())
            if spec_here and isinstance(title, str):
                value = _spec_value(node)
                title = title.strip()
                if title and value and title not in SKIP_SPEC_TITLES and len(value) <= 80:
                    pairs.append((title, value))
            for key in ("url", "src", "image_url", "thumbnail_url"):
                raw = node.get(key)
                if isinstance(raw, str) and raw.startswith("http") and _is_photo(raw):
                    images.append(_clean_image(raw))
            image = node.get("image")
            if isinstance(image, str) and image.startswith("http") and _is_photo(image):
                images.append(_clean_image(image))
            for child in node.values():
                visit(child, spec_here)
        elif isinstance(node, list):
            for child in node:
                visit(child, in_spec)
        elif isinstance(node, str) and node.startswith("http") and _is_photo(node):
            images.append(_clean_image(node))

    visit(payload)
    if isinstance(payload, dict):
        seo = payload.get("seo")
        if isinstance(seo, dict) and isinstance(seo.get("title"), str):
            titles.insert(0, seo["title"].strip())
    return pairs, texts, images, titles


def parse_divar_post(payload: dict) -> DivarPost:
    pairs, texts, images, titles = _collect(payload)
    area_raw = _best_value(pairs, _score_area)
    price_raw = _best_value(pairs, _score_price)
    bedrooms_raw = _best_value(pairs, _score_bedrooms)
    year_raw = _best_value(pairs, _score_year)

    area = parse_number(area_raw) if area_raw else None
    price_number = parse_number(price_raw) if price_raw else None
    if price_raw and any(word in price_raw for word in ("توافق", "رایگان")):
        price_number = None
    bedrooms_number = parse_number(bedrooms_raw) if bedrooms_raw else None

    seen: set[str] = set()
    unique_images: list[str] = []
    for url in images:
        if url not in seen:
            seen.add(url)
            unique_images.append(url)

    description = max(texts, key=len) if texts else ""
    title = next((item for item in titles if item), "")
    seen_titles: set[str] = set()
    specs: list[tuple[str, str]] = []
    for spec_title, spec_value in pairs:
        if spec_title in seen_titles:
            continue
        seen_titles.add(spec_title)
        specs.append((spec_title, spec_value))
    return DivarPost(
        title=title[:300],
        description=description,
        area=area,
        price=int(price_number) if price_number is not None else None,
        bedrooms=int(bedrooms_number) if bedrooms_number is not None else None,
        building_year=parse_build_year(year_raw),
        image_urls=unique_images[:10],
        specs=specs,
    )


async def fetch_divar_post(token: str) -> DivarPost:
    url = f"https://api.divar.ir/v8/posts-v2/web/{token}"
    headers = {**BROWSER_HEADERS, "Referer": f"https://divar.ir/v/{token}"}
    proxy = settings.divar_proxy.strip() or None
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, proxy=proxy) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("divar status %s for token %s", exc.response.status_code, token)
        raise AppError("دریافت اطلاعات این آگهی از دیوار ممکن نشد.", 502) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("divar request failed for token %s", token)
        raise AppError("ارتباط با دیوار برقرار نشد. کمی بعد دوباره تلاش کنید.", 502) from exc

    if not isinstance(payload, dict):
        raise AppError("پاسخ دیوار قابل خواندن نبود.", 502)
    return parse_divar_post(payload)
