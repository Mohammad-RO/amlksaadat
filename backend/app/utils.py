import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
TO_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTHS = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}


def to_english_digits(value: str) -> str:
    return value.translate(PERSIAN_DIGITS)


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", to_english_digits(raw or ""))
    if digits.startswith("0098"):
        digits = digits[4:]
    if digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if not re.fullmatch(r"09\d{9}", digits):
        raise ValueError("شماره موبایل معتبر نیست.")
    return digits


def extract_divar_token(url: str) -> str | None:
    text = (url or "").strip()
    if not text:
        return None
    match = re.search(r"divar\.ir/(?:v/)?(?:[^/\s?#]+/)*([A-Za-z0-9_-]{5,})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    tail = text.rstrip("/").split("/")[-1].split("?")[0]
    if re.fullmatch(r"[A-Za-z0-9_-]{5,}", tail):
        return tail
    return None


def current_jalali_year() -> int:
    local = datetime.now(TEHRAN).replace(tzinfo=None)
    return jdatetime.datetime.fromgregorian(datetime=local).year


def parse_build_year(raw: str | None, now_year: int | None = None) -> int | None:
    if not raw or not raw.strip():
        return None
    year = current_jalali_year() if now_year is None else now_year
    text = to_english_digits(raw)
    if "نوساز" in raw or "نوساز" in text:
        return year
    match = re.search(r"(?:13|14)\d{2}", text)
    if match:
        return int(match.group(0))
    if "سال" in raw:
        age = parse_number(text)
        if age is not None and 0 <= age < 80:
            return year - int(age)
    return None


def build_year_from_text(text: str, now_year: int | None = None) -> int | None:
    for line in (text or "").splitlines():
        if not any(key in line for key in ("سال ساخت", "سن بنا", "سن ساختمان")):
            continue
        value = line.split(":", 1)[-1] if ":" in line or "：" in line else line
        value = value.split("：", 1)[-1]
        year = parse_build_year(value, now_year)
        if year is not None:
            return year
    return None


def parse_number(raw: str) -> float | None:
    text = to_english_digits(raw or "")
    text = text.replace(",", "").replace("٬", "").replace("،", "").replace(" ", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def format_toman(amount: int) -> str:
    grouped = f"{int(amount):,}".replace(",", "٬")
    return f"{grouped.translate(TO_PERSIAN_DIGITS)} تومان"


def format_toman_range(low: int | None, high: int | None, *, high_first: bool = False) -> str | None:
    if low is None and high is None:
        return None
    if low is None:
        low = high
    if high is None:
        high = low
    assert low is not None and high is not None
    if low == high:
        return format_toman(low)
    first, second = (high, low) if high_first else (low, high)
    return f"از {format_toman(first)} تا {format_toman(second)}"


def as_tehran(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(TEHRAN)


def jalali_stamp(moment: datetime) -> tuple[str, str]:
    local = as_tehran(moment)
    jalali = jdatetime.datetime.fromgregorian(datetime=local.replace(tzinfo=None))
    date_text = f"{jalali.day} {MONTHS[jalali.month]} {jalali.year}"
    time_text = f"{jalali.hour}:{jalali.minute:02d}"
    return date_text, time_text


def duplicate_message(agent_name: str, created_at: datetime) -> str:
    date_text, time_text = jalali_stamp(created_at)
    return (
        f"«{agent_name} در تاریخ {date_text} در ساعت {time_text} "
        "این لینک را قبلاً وارد کرده است. تکراری است.»"
    )


def format_jalali(moment: datetime) -> str:
    date_text, time_text = jalali_stamp(moment)
    return f"{date_text}، {time_text}"


def format_price(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    return f"{value:,}".replace(",", "٬") + " تومان"
