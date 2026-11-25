import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.errors import AppError
from app.models import DivarColleague, DivarConnection
from app.utils import normalize_phone, to_english_digits

logger = logging.getLogger(__name__)

API_ROOT = "https://api.divar.ir"
LINK_RE = re.compile(
    r"^https?://(?:www\.)?divar\.ir/my-divar/my-business/([A-Za-z0-9_-]+)/agent-management/?(?:\?.*)?$",
    re.IGNORECASE,
)
POSTS_RE = re.compile(
    r"^https?://(?:www\.)?divar\.ir/my-divar/my-posts/?(?:\?.*)?$",
    re.IGNORECASE,
)
PUBLIC_POST_RE = re.compile(r"https://divar\.ir/v/([A-Za-z0-9_-]{5,})")
CHALLENGE_TTL = timedelta(minutes=10)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}
AUTH_HEADERS = {**BROWSER_HEADERS, "rid": "passwordless", "st-auth-mode": "cookie"}


class DivarLoginRequired(Exception):
    pass


@dataclass
class ColleagueSnapshot:
    relation_token: str
    name: str
    phone: str
    role: str


def parse_agent_management_url(raw: str) -> tuple[str, str]:
    text = (raw or "").strip()
    if text.startswith("divar.ir/"):
        text = "https://" + text
    match = LINK_RE.match(text)
    if match is None:
        raise AppError("لینک باید صفحهٔ مدیریت همکاران دیوار باشد.")
    token = match.group(1)
    url = f"https://divar.ir/my-divar/my-business/{token}/agent-management"
    return url, token


def parse_posts_url(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("divar.ir/"):
        text = "https://" + text
    if POSTS_RE.match(text) is None:
        raise AppError("لینک باید صفحهٔ آگهی‌های من در دیوار باشد.")
    return "https://divar.ir/my-divar/my-posts"


def save_posts_link(db, raw_url: str) -> DivarConnection:
    url = parse_posts_url(raw_url)
    row = _connection(db)
    row.posts_url = url
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def save_agent_management_link(db, raw_url: str) -> DivarConnection:
    url, token = parse_agent_management_url(raw_url)
    row = _connection(db)
    row.url = url
    row.business_token = token
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def colleague_rows(db, business_token: str) -> list[DivarColleague]:
    if not business_token:
        return []
    return (
        db.query(DivarColleague)
        .filter(DivarColleague.business_token == business_token)
        .order_by(DivarColleague.name, DivarColleague.id)
        .all()
    )


def start_divar_login(db, phone: str) -> None:
    normalized = normalize_phone(phone)
    client = _client()
    try:
        response = client.post(
            f"{API_ROOT}/v8/authenticate/signinup/code",
            json={"phoneNumber": _divar_phone(normalized)},
            headers=AUTH_HEADERS,
        )
    except httpx.HTTPError as exc:
        logger.warning("divar otp start failed: %s", exc.__class__.__name__)
        raise AppError("ارتباط با دیوار برای ارسال کد برقرار نشد.", status_code=502) from exc
    _raise_for_auth(response, "ارسال کد دیوار انجام نشد.")
    payload = _json_object(response)
    device_id = str(payload.get("deviceId") or "")
    pre_auth = str(payload.get("preAuthSessionId") or "")
    if not device_id or not pre_auth:
        raise AppError("دیوار شناسهٔ ورود را برنگرداند.", status_code=502)
    row = _connection(db)
    row.pending_phone = normalized
    row.pending_device_id = device_id
    row.pending_pre_auth = pre_auth
    row.pending_cookies = _export_cookies(client)
    row.pending_at = _now()
    db.commit()


def confirm_divar_login(db, code: str) -> None:
    row = db.get(DivarConnection, 1)
    if row is None or not row.pending_pre_auth or row.pending_at is None:
        raise AppError("اول شماره را وارد کنید تا کد دیوار ارسال شود.")
    issued = row.pending_at
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    if _now() - issued > CHALLENGE_TTL:
        _clear_pending(row)
        db.commit()
        raise AppError("مهلت کد تمام شده است. دوباره شماره را وارد کنید.")
    digits = re.sub(r"\D", "", to_english_digits(code or ""))
    if not re.fullmatch(r"\d{4,8}", digits):
        raise AppError("کد پیامک معتبر نیست.")
    client = _client(row.pending_cookies)
    try:
        response = client.post(
            f"{API_ROOT}/v8/authenticate/signinup/code/consume",
            json={
                "preAuthSessionId": row.pending_pre_auth,
                "deviceId": row.pending_device_id,
                "userInputCode": digits,
            },
            headers=AUTH_HEADERS,
        )
    except httpx.HTTPError as exc:
        logger.warning("divar otp confirm failed: %s", exc.__class__.__name__)
        raise AppError("ارتباط با دیوار برای تأیید کد برقرار نشد.", status_code=502) from exc
    _raise_for_auth(response, "کد دیوار پذیرفته نشد.")
    cookies = _export_cookies(client)
    if not cookies:
        raise AppError("دیوار نشست ورود را برنگرداند.", status_code=502)
    row.phone = row.pending_phone
    row.cookies = cookies
    row.front_token = response.headers.get("front-token") or ""
    _clear_pending(row)
    row.updated_at = _now()
    db.commit()


def refresh_colleagues(db) -> tuple[bool, int, int, int]:
    row = db.get(DivarConnection, 1)
    if row is None or not row.business_token:
        raise AppError("اول لینک مدیریت همکاران را ثبت کنید.")
    if not row.cookies:
        raise DivarLoginRequired
    client = _client(row.cookies, row.front_token)
    try:
        people = _fetch_people(client, row.business_token)
    except DivarLoginRequired:
        raise
    except httpx.HTTPError as exc:
        logger.warning("divar colleague refresh failed: %s", exc.__class__.__name__)
        raise AppError("ارتباط با دیوار برقرار نشد.", status_code=502) from exc
    added, removed, updated = apply_colleague_snapshot(db, row.business_token, people)
    db.commit()
    return False, added, removed, updated


def apply_colleague_snapshot(db, business_token: str, people: list[ColleagueSnapshot]) -> tuple[int, int, int]:
    if not people:
        raise AppError("دیوار لیست همکاران را برنگرداند.")
    existing = {
        item.relation_token: item
        for item in db.query(DivarColleague).filter(DivarColleague.business_token == business_token)
    }
    seen: set[str] = set()
    added = 0
    updated = 0
    now = _now()
    for person in people:
        seen.add(person.relation_token)
        current = existing.get(person.relation_token)
        if current is None:
            db.add(
                DivarColleague(
                    business_token=business_token,
                    relation_token=person.relation_token,
                    name=person.name,
                    phone=person.phone,
                    role=person.role,
                )
            )
            added += 1
            continue
        if current.name != person.name or current.phone != person.phone or current.role != person.role:
            current.name = person.name
            current.phone = person.phone
            current.role = person.role
            current.updated_at = now
            updated += 1
    removed = 0
    for token, current in existing.items():
        if token not in seen:
            db.delete(current)
            removed += 1
    return added, removed, updated


def _fetch_people(client: httpx.Client, business_token: str) -> list[ColleagueSnapshot]:
    listing = client.get(
        f"{API_ROOT}/v8/premium-user/web/business/{business_token}/agent-management",
        headers=BROWSER_HEADERS,
    )
    if listing.status_code in {401, 403}:
        raise DivarLoginRequired
    if listing.status_code != 200:
        raise AppError("خواندن لیست همکاران از دیوار انجام نشد.", status_code=502)
    agents = _agent_refs(_json_object(listing))
    if not agents:
        raise AppError("دیوار لیست همکاران را برنگرداند.", status_code=502)
    people: list[ColleagueSnapshot] = []
    for name, relation_token in agents:
        details = client.post(
            f"{API_ROOT}/v8/premium-user/business/agent-details/{relation_token}",
            json={},
            headers=BROWSER_HEADERS,
        )
        if details.status_code in {401, 403}:
            raise DivarLoginRequired
        if details.status_code != 200:
            raise AppError("خواندن شمارهٔ یکی از همکاران از دیوار انجام نشد.", status_code=502)
        person_name, phone, role = _person_from_details(_json_object(details), name)
        people.append(
            ColleagueSnapshot(
                relation_token=relation_token,
                name=person_name,
                phone=normalize_phone(phone),
                role=role,
            )
        )
    return people


@dataclass
class ActivePost:
    manage_token: str
    title: str
    author: str


def author_from_label(text: str) -> str:
    compact = (text or "").replace("\u200c", "").replace("\u200d", "").strip()
    match = re.match(r"^توسط\s*:\s*(.+)$", compact)
    return match.group(1).strip() if match else ""


def name_key(value: str) -> str:
    text = (value or "").replace("\u200c", "").replace("\u200d", "").replace("\u0640", "")
    text = (
        text.replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("ة", "ه")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
    )
    return re.sub(r"\s+", "", text)


def match_colleague(author: str, people: list[tuple[str, str]]) -> tuple[str, str]:
    key = name_key(author)
    if not key:
        raise AppError("نام مشاور روی این آگهی نیست.")
    found = [(name, phone) for name, phone in people if name_key(name) == key]
    if len(found) == 1:
        return found[0]
    if not found:
        raise AppError(f"مشاور «{author}» در لیست همکاران نیست.")
    raise AppError(f"چند همکار با نام «{author}» ثبت شده است.")


def active_posts_from_page(payload: dict) -> tuple[list[ActivePost], str, bool]:
    widgets = ((payload.get("page") or {}).get("widget_list") or [])
    tab = ((payload.get("tab_bar") or {}).get("current_tab_identifier") or "")
    if tab and tab != "ongoing":
        raise AppError("پاسخ دیوار تب آگهی‌های فعال نبود.", status_code=502)
    posts: list[ActivePost] = []
    for widget in widgets:
        if widget.get("widget_type") != "CONTENT_CONTAINER":
            continue
        inner = ((widget.get("data") or {}).get("widgets") or [])
        row = next((item for item in inner if item.get("widget_type") == "POST_ROW"), None)
        if row is None:
            continue
        data = row.get("data") or {}
        action = data.get("action") or {}
        manage_token = str((action.get("payload") or {}).get("manage_token") or "").strip()
        if not manage_token:
            continue
        posts.append(
            ActivePost(
                manage_token=manage_token,
                title=str(data.get("title") or "").strip() or "آگهی دیوار",
                author=author_from_label(str(data.get("top_description_text") or "")),
            )
        )
    scroll = (payload.get("page") or {}).get("infinite_scroll_response") or {}
    cursor = str(scroll.get("last_item_identifier") or "")
    return posts, cursor, bool(scroll.get("has_next"))


def public_post_url(payload: dict) -> str:
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, str):
            match = PUBLIC_POST_RE.search(node)
            if match:
                found.append(f"https://divar.ir/v/{match.group(1)}")
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    if not found:
        raise AppError("لینک عمومی آگهی در دیوار پیدا نشد.", status_code=502)
    return found[0]


def fetch_active_posts(cookies: list, front_token: str = "") -> list[ActivePost]:
    client = _client(cookies, front_token)
    posts: list[ActivePost] = []
    cursor = ""
    seen: set[str] = set()
    finished = False
    for _ in range(40):
        specification: dict[str, str] = {"tab_identifier": "ongoing"}
        if cursor:
            specification["last_item_identifier"] = cursor
        try:
            response = client.post(
                f"{API_ROOT}/v8/my-posts/w/list-v2",
                json={"specification": specification},
                headers=BROWSER_HEADERS,
            )
        except httpx.HTTPError as exc:
            logger.warning("divar active posts failed: %s", exc.__class__.__name__)
            raise AppError("ارتباط با دیوار برای خواندن آگهی‌ها برقرار نشد.", status_code=502) from exc
        if response.status_code in {401, 403}:
            raise DivarLoginRequired
        if response.status_code != 200:
            raise AppError("خواندن آگهی‌های فعال از دیوار انجام نشد.", status_code=502)
        page_posts, next_cursor, has_next = active_posts_from_page(_json_object(response))
        posts.extend(page_posts)
        if not has_next:
            finished = True
            break
        if not next_cursor or next_cursor in seen:
            break
        seen.add(next_cursor)
        cursor = next_cursor
    if not finished:
        raise AppError("خواندن همهٔ آگهی‌های فعال ناتمام ماند.", status_code=502)
    return posts


def fetch_public_url(cookies: list, manage_token: str, front_token: str = "") -> str:
    client = _client(cookies, front_token)
    try:
        response = client.get(
            f"{API_ROOT}/v8/post-management/page/{manage_token}",
            headers=BROWSER_HEADERS,
        )
    except httpx.HTTPError as exc:
        logger.warning("divar manage page failed: %s", exc.__class__.__name__)
        raise AppError("ارتباط با دیوار برای خواندن آگهی برقرار نشد.", status_code=502) from exc
    if response.status_code in {401, 403}:
        raise DivarLoginRequired
    if response.status_code != 200:
        raise AppError("خواندن صفحهٔ آگهی از دیوار انجام نشد.", status_code=502)
    return public_post_url(_json_object(response))


def _agent_refs(payload: dict) -> list[tuple[str, str]]:
    widgets = ((payload.get("page") or {}).get("widget_list") or [])
    refs: list[tuple[str, str]] = []
    for widget in widgets:
        if widget.get("widget_type") != "SELECTOR_ROW":
            continue
        data = widget.get("data") or {}
        action = data.get("action") or {}
        if action.get("type") != "PREMIUM_PANEL_AGENT_DETAILS":
            continue
        relation_token = str((action.get("payload") or {}).get("relation_token") or "")
        if relation_token:
            refs.append((str(data.get("title") or "").strip(), relation_token))
    return refs


def _person_from_details(payload: dict, fallback_name: str) -> tuple[str, str, str]:
    widgets = ((payload.get("page") or {}).get("widget_list") or [])
    name = ""
    phone = ""
    role = ""
    for widget in widgets:
        data = widget.get("data") or {}
        if widget.get("widget_type") == "TITLE_ROW" and not name:
            text = str(data.get("text") or "").strip()
            if text and "سقف" not in text:
                name = text
        title = _compact(str(data.get("title") or ""))
        value = str(data.get("value") or "").strip()
        if "موبایل" in title or title.startswith("تلفن"):
            phone = value
        elif "دسترسی" in title:
            role = value
    if not name:
        name = fallback_name
    if not name:
        raise AppError("نام یکی از همکاران در پاسخ دیوار نبود.", status_code=502)
    if not phone:
        raise AppError("شمارهٔ یکی از همکاران در پاسخ دیوار نبود.", status_code=502)
    return name, phone, role


def _compact(value: str) -> str:
    return value.replace("\u200c", "").replace("\u200d", "").replace(" ", "")


def _connection(db) -> DivarConnection:
    row = db.get(DivarConnection, 1)
    if row is None:
        row = DivarConnection(id=1)
        db.add(row)
        db.flush()
    return row


def _client(cookies: list | None = None, front_token: str = "") -> httpx.Client:
    proxy = settings.divar_proxy.strip() or None
    headers = dict(BROWSER_HEADERS)
    if front_token:
        headers["front-token"] = front_token
    client = httpx.Client(proxy=proxy, timeout=40, follow_redirects=True, headers=headers)
    for item in cookies or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        client.cookies.set(
            item["name"],
            item.get("value") or "",
            domain=item.get("domain") or "api.divar.ir",
            path=item.get("path") or "/",
        )
    return client


def _export_cookies(client: httpx.Client) -> list[dict]:
    exported = []
    for cookie in client.cookies.jar:
        if not cookie.value:
            continue
        exported.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path or "/",
            }
        )
    return exported


def _raise_for_auth(response: httpx.Response, fallback: str) -> None:
    if response.status_code < 400:
        return
    payload = _json_object(response)
    message = str(payload.get("message") or payload.get("detail") or "").strip()
    if response.status_code in {400, 401, 403} and message:
        raise AppError(message, status_code=400)
    raise AppError(fallback, status_code=502)


def _json_object(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _divar_phone(phone: str) -> str:
    return "+98" + phone[1:]


def _clear_pending(row: DivarConnection) -> None:
    row.pending_phone = ""
    row.pending_device_id = ""
    row.pending_pre_auth = ""
    row.pending_cookies = []
    row.pending_at = None


def _now() -> datetime:
    return datetime.now(timezone.utc)
