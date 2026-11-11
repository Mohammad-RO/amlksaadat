import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.database import SessionLocal
from app.models import BuyerSession, Listing
from app.services.matching import match_listings
from app.utils import to_english_digits

logger = logging.getLogger(__name__)

BUY = "خرید خانه"
RESTART = "شروع دوباره"
CONTINUE = "ادامه"
ANY = "مهم نیست"
BILLION = 1_000_000_000
AREA_CHOICES: dict[str, tuple[float, float | None] | None] = {
    "70 تا 90 متر": (70, 90),
    "90 تا 110 متر": (90, 110),
    "110 تا 130 متر": (110, 130),
    "130 تا 160 متر": (130, 160),
    "160 تا 190 متر": (160, 190),
    "190 تا 230 متر": (190, 230),
    "230 تا 270 متر": (230, 270),
    "270 متر به بالا": (270, None),
    ANY: None,
}
PRICE_CHOICES: dict[str, tuple[int, int | None] | None] = {
    "30 تا 50 میلیارد": (30 * BILLION, 50 * BILLION),
    "50 تا 70 میلیارد": (50 * BILLION, 70 * BILLION),
    "70 تا 90 میلیارد": (70 * BILLION, 90 * BILLION),
    "90 تا 110 میلیارد": (90 * BILLION, 110 * BILLION),
    "110 تا 140 میلیارد": (110 * BILLION, 140 * BILLION),
    "140 تا 170 میلیارد": (140 * BILLION, 170 * BILLION),
    "170 تا 200 میلیارد": (170 * BILLION, 200 * BILLION),
    "200 تا 250 میلیارد": (200 * BILLION, 250 * BILLION),
    "250 تا 300 میلیارد": (250 * BILLION, 300 * BILLION),
    "300 میلیارد به بالا": (300 * BILLION, None),
    ANY: None,
}
AGE_CHOICES: dict[str, tuple[int, int | None] | None] = {
    "نوساز": (0, 1),
    "کمتر از 5 سال": (0, 4),
    "5 تا 10 سال": (5, 10),
    "10 تا 15 سال": (10, 15),
    "15 تا 20 سال": (15, 20),
    "20 تا 30 سال": (20, 30),
    "30 سال به بالا": (30, None),
    ANY: None,
}
BEDROOM_CHOICES = {
    "تک خواب": (1, False),
    "دو خواب": (2, False),
    "سه خواب": (3, False),
    "چهار خواب و بیشتر": (4, True),
    ANY: None,
}
AREA_PROMPT = "بازه متراژ را انتخاب کنید."
PRICE_PROMPT = "بازه قیمت را انتخاب کنید."
AGE_PROMPT = "سن بنا را انتخاب کنید."
BEDROOM_PROMPT = "تعداد خواب را انتخاب کنید."


def _rtl_row(labels: list[str]) -> list[KeyboardButton]:
    return [KeyboardButton(label) for label in reversed(labels)]


def _choice_keyboard(labels: list[str], columns: int) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    row: list[str] = []
    for label in labels:
        if label == ANY:
            if row:
                rows.append(_rtl_row(row))
                row = []
            rows.append([KeyboardButton(ANY)])
            continue
        row.append(label)
        if len(row) == columns:
            rows.append(_rtl_row(row))
            row = []
    if row:
        rows.append(_rtl_row(row))
    rows.append(_rtl_row([RESTART, CONTINUE]))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BUY)],
        _rtl_row([RESTART, CONTINUE]),
    ],
    resize_keyboard=True,
)
AREA_KEYBOARD = _choice_keyboard(list(AREA_CHOICES), 2)
PRICE_KEYBOARD = _choice_keyboard(list(PRICE_CHOICES), 1)
AGE_KEYBOARD = _choice_keyboard(list(AGE_CHOICES), 2)
BEDROOM_KEYBOARD = _choice_keyboard(list(BEDROOM_CHOICES), 2)


def _session(user_id: int, chat_id: int) -> BuyerSession:
    db = SessionLocal()
    try:
        row = db.query(BuyerSession).filter(BuyerSession.telegram_user_id == user_id).one_or_none()
        if row is None:
            row = BuyerSession(telegram_user_id=user_id, chat_id=chat_id, step="idle")
            db.add(row)
        row.chat_id = chat_id
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def _save(row: BuyerSession) -> None:
    db = SessionLocal()
    try:
        current = db.query(BuyerSession).filter(BuyerSession.telegram_user_id == row.telegram_user_id).one()
        current.step = row.step
        current.area = row.area
        current.price = row.price
        current.bedrooms = row.bedrooms
        current.bedrooms_or_more = row.bedrooms_or_more
        current.bedrooms_skipped = row.bedrooms_skipped
        current.area_min = row.area_min
        current.area_max = row.area_max
        current.area_skipped = row.area_skipped
        current.price_min = row.price_min
        current.price_max = row.price_max
        current.price_skipped = row.price_skipped
        current.age_min = row.age_min
        current.age_max = row.age_max
        current.age_skipped = row.age_skipped
        current.chat_id = row.chat_id
        db.commit()
    finally:
        db.close()


def _bounds(skipped: bool, low, high):
    if skipped or (low is None and high is None):
        return None
    return (low, high)


def _clip(text: str) -> str:
    if len(text) <= 3800:
        return text
    lines = text.splitlines()
    tail = lines[-1] if lines else ""
    head = "\n".join(lines[:-1])[:3600].rstrip()
    return f"{head}\n…\n{tail}"


async def _send_details(chat_id: int, code: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        listing = db.query(Listing).filter(Listing.unique_code == code).one_or_none()
        if listing is None:
            await context.bot.send_message(chat_id, "آگهی با این کد پیدا نشد.")
            return
        agent = listing.agent
        text = _clip(listing.structured_text)
        text = f"{text}\n\nمشاور: {agent.name}\nشماره تماس: {agent.phone}"
        await context.bot.send_message(chat_id, text)
        file_ids = list(listing.image_file_ids or [])
        urls = list(listing.image_urls or [])
    finally:
        db.close()

    photos: list[str | bytes] = file_ids
    if not photos and urls:
        photos = await _download_images(urls)
    if not photos:
        await context.bot.send_message(chat_id, "عکسی برای این آگهی موجود نیست.")
        return
    if len(photos) == 1:
        await context.bot.send_photo(chat_id, photos[0])
        return
    media = [InputMediaPhoto(item) for item in photos[:10]]
    await context.bot.send_media_group(chat_id, media)


async def _download_images(urls: list[str]) -> list[bytes]:
    photos: list[bytes] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in urls[:8]:
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                photos.append(response.content)
            except httpx.HTTPError:
                logger.warning("could not download listing image")
    return photos


async def _show_matches(chat_id: int, row: BuyerSession, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        found = match_listings(
            db,
            area=_bounds(row.area_skipped, row.area_min, row.area_max),
            price=_bounds(row.price_skipped, row.price_min, row.price_max),
            bedrooms=None if row.bedrooms_skipped else row.bedrooms,
            bedrooms_or_more=bool(row.bedrooms_or_more),
            age=_bounds(row.age_skipped, row.age_min, row.age_max),
        )
        payload = [(item.unique_code, item.structured_text) for item in found]
    finally:
        db.close()

    if not payload:
        await context.bot.send_message(
            chat_id,
            "خانه‌ای در بازه‌های انتخاب‌شده پیدا نشد.\n"
            "می‌توانید دوباره «خرید خانه» را بزنید.",
            reply_markup=MENU,
        )
        return

    await context.bot.send_message(
        chat_id,
        f"{len(payload)} خانه نزدیک به درخواست شما پیدا شد.\n"
        "در این مرحله عکس و شماره مشاور نمایش داده نمی‌شود.\n"
        "برای جزئیات، دکمه زیر آگهی را بزنید یا کد ۸ رقمی را بفرستید.",
        reply_markup=MENU,
    )
    for code, text in payload:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("اطلاعات بیشتر و تماس", callback_data=f"more:{code}")]]
        )
        await context.bot.send_message(chat_id, _clip(text), reply_markup=keyboard)


def _reset_search(row: BuyerSession) -> None:
    row.step = "area"
    row.area = None
    row.price = None
    row.bedrooms = None
    row.bedrooms_or_more = False
    row.bedrooms_skipped = False
    row.area_min = None
    row.area_max = None
    row.area_skipped = False
    row.price_min = None
    row.price_max = None
    row.price_skipped = False
    row.age_min = None
    row.age_max = None
    row.age_skipped = False
    _save(row)


def _store_range(row: BuyerSession, prefix: str, value) -> None:
    if value is None:
        setattr(row, f"{prefix}_skipped", True)
        setattr(row, f"{prefix}_min", None)
        setattr(row, f"{prefix}_max", None)
        return
    low, high = value
    setattr(row, f"{prefix}_skipped", False)
    setattr(row, f"{prefix}_min", low)
    setattr(row, f"{prefix}_max", high)


async def _resume(message, row: BuyerSession) -> None:
    if row.step == "price":
        await message.reply_text(PRICE_PROMPT, reply_markup=PRICE_KEYBOARD)
        return
    if row.step == "age":
        await message.reply_text(AGE_PROMPT, reply_markup=AGE_KEYBOARD)
        return
    if row.step == "bedrooms":
        await message.reply_text(BEDROOM_PROMPT, reply_markup=BEDROOM_KEYBOARD)
        return
    if row.step == "area":
        await message.reply_text(AREA_PROMPT, reply_markup=AREA_KEYBOARD)
        return
    await message.reply_text(
        "جستجویی در جریان نیست.\nبرای شروع، «شروع دوباره» یا «خرید خانه» را بزنید.",
        reply_markup=MENU,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_user is None or update.message is None:
        return
    if update.effective_chat.type != "private":
        return
    row = _session(update.effective_user.id, update.effective_chat.id)
    _reset_search(row)
    await update.message.reply_text(
        "سلام.\n"
        "بازه متراژ را انتخاب کنید.\n"
        "هر زمان با «شروع دوباره» از نو شروع کنید، یا با «ادامه» به همان مرحله برگردید.\n"
        "اگر کد ۸ رقمی یک آگهی را دارید، همان را ارسال کنید.",
        reply_markup=AREA_KEYBOARD,
    )


async def continue_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_user is None or update.message is None:
        return
    if update.effective_chat.type != "private":
        return
    row = _session(update.effective_user.id, update.effective_chat.id)
    await _resume(update.message, row)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_chat is None:
        return
    await query.answer()
    if not query.data.startswith("more:"):
        return
    code = query.data.split(":", 1)[1]
    await _send_details(update.effective_chat.id, code, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_user is None or update.message is None:
        return
    if update.effective_chat.type != "private":
        return
    text = (update.message.text or "").strip()
    normalized = to_english_digits(text)
    if normalized.isdigit() and len(normalized) == 8:
        await _send_details(update.effective_chat.id, normalized, context)
        return

    row = _session(update.effective_user.id, update.effective_chat.id)
    if text in {BUY, RESTART}:
        _reset_search(row)
        await update.message.reply_text(AREA_PROMPT, reply_markup=AREA_KEYBOARD)
        return
    if text == CONTINUE:
        await _resume(update.message, row)
        return

    if row.step == "area":
        if text not in AREA_CHOICES:
            await update.message.reply_text("یکی از بازه‌های متراژ را انتخاب کنید.", reply_markup=AREA_KEYBOARD)
            return
        _store_range(row, "area", AREA_CHOICES[text])
        row.step = "price"
        _save(row)
        await update.message.reply_text(PRICE_PROMPT, reply_markup=PRICE_KEYBOARD)
        return

    if row.step == "price":
        if text not in PRICE_CHOICES:
            await update.message.reply_text("یکی از بازه‌های قیمت را انتخاب کنید.", reply_markup=PRICE_KEYBOARD)
            return
        _store_range(row, "price", PRICE_CHOICES[text])
        row.step = "age"
        _save(row)
        await update.message.reply_text(AGE_PROMPT, reply_markup=AGE_KEYBOARD)
        return

    if row.step == "age":
        if text not in AGE_CHOICES:
            await update.message.reply_text("یکی از گزینه‌های سن بنا را انتخاب کنید.", reply_markup=AGE_KEYBOARD)
            return
        _store_range(row, "age", AGE_CHOICES[text])
        row.step = "bedrooms"
        row.bedrooms = None
        row.bedrooms_or_more = False
        row.bedrooms_skipped = False
        _save(row)
        await update.message.reply_text(BEDROOM_PROMPT, reply_markup=BEDROOM_KEYBOARD)
        return

    if row.step == "bedrooms":
        if text not in BEDROOM_CHOICES:
            await update.message.reply_text("یکی از دکمه‌های تعداد خواب را بزنید.", reply_markup=BEDROOM_KEYBOARD)
            return
        choice = BEDROOM_CHOICES[text]
        if choice is None:
            row.bedrooms = None
            row.bedrooms_or_more = False
            row.bedrooms_skipped = True
        else:
            bedrooms, or_more = choice
            row.bedrooms = bedrooms
            row.bedrooms_or_more = or_more
            row.bedrooms_skipped = False
        row.step = "idle"
        _save(row)
        await _show_matches(update.effective_chat.id, row, context)
        return

    await update.message.reply_text(
        "«خرید خانه» یا «شروع دوباره» را بزنید، یا کد ۸ رقمی آگهی را ارسال کنید.",
        reply_markup=MENU,
    )


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("continue", continue_search))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
