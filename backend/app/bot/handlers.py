import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.database import SessionLocal
from app.models import BuyerSession, Listing
from app.services.matching import match_listings
from app.utils import parse_number, to_english_digits

logger = logging.getLogger(__name__)

BUY = "خرید خانه"
RESTART = "شروع دوباره"
CONTINUE = "ادامه"
BEDROOM_CHOICES = {
    "تک خواب": (1, False),
    "دو خواب": (2, False),
    "سه خواب": (3, False),
    "چهار خواب و بیشتر": (4, True),
}
MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BUY)],
        [KeyboardButton(RESTART), KeyboardButton(CONTINUE)],
    ],
    resize_keyboard=True,
)
BEDROOM_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("تک خواب"), KeyboardButton("دو خواب")],
        [KeyboardButton("سه خواب"), KeyboardButton("چهار خواب و بیشتر")],
        [KeyboardButton(RESTART), KeyboardButton(CONTINUE)],
    ],
    resize_keyboard=True,
)
AREA_PROMPT = "متراژ خانه را به متر وارد کنید.\nمثال: 90"
PRICE_PROMPT = "قیمت را فقط با یک عدد وارد کنید.\nمثال: 65، یعنی 65 میلیارد تومان."


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
        current.chat_id = row.chat_id
        db.commit()
    finally:
        db.close()


def _parse_price(text: str) -> int | None:
    number = parse_number(text)
    if number is None or number <= 0:
        return None
    return int(round(number * 1_000_000_000))


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
            row.area,
            int(row.price),
            int(row.bedrooms),
            bedrooms_or_more=bool(row.bedrooms_or_more),
        )
        payload = [(item.unique_code, item.structured_text) for item in found]
    finally:
        db.close()

    if not payload:
        await context.bot.send_message(
            chat_id,
            "خانه‌ای در بازه ۱۵ درصد متراژ و قیمت، با این تعداد خواب، پیدا نشد.\n"
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
    _save(row)


async def _resume(message, row: BuyerSession) -> None:
    if row.step == "price" and row.area is not None:
        await message.reply_text(PRICE_PROMPT, reply_markup=MENU)
        return
    if row.step == "bedrooms" and row.price is not None:
        await message.reply_text("تعداد خواب را انتخاب کنید.", reply_markup=BEDROOM_KEYBOARD)
        return
    if row.step == "area":
        await message.reply_text(AREA_PROMPT, reply_markup=MENU)
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
        "متراژ خانه را به متر وارد کنید.\nمثال: 90\n"
        "هر زمان با «شروع دوباره» از نو شروع کنید، یا با «ادامه» به همان مرحله برگردید.\n"
        "اگر کد ۸ رقمی یک آگهی را دارید، همان را ارسال کنید.",
        reply_markup=MENU,
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
        await update.message.reply_text(AREA_PROMPT, reply_markup=MENU)
        return
    if text == CONTINUE:
        await _resume(update.message, row)
        return

    if row.step == "area":
        area = parse_number(text)
        if area is None or area < 10 or area > 5000:
            await update.message.reply_text("یک متراژ معتبر به متر بفرستید. مثال: 90", reply_markup=MENU)
            return
        row.area = area
        row.step = "price"
        _save(row)
        await update.message.reply_text(PRICE_PROMPT, reply_markup=MENU)
        return

    if row.step == "price":
        price = _parse_price(text)
        if price is None:
            await update.message.reply_text("یک عدد وارد کنید. مثال: 65، یعنی 65 میلیارد تومان.", reply_markup=MENU)
            return
        row.price = price
        row.step = "bedrooms"
        row.bedrooms = None
        row.bedrooms_or_more = False
        _save(row)
        await update.message.reply_text("تعداد خواب را انتخاب کنید.", reply_markup=BEDROOM_KEYBOARD)
        return

    if row.step == "bedrooms":
        choice = BEDROOM_CHOICES.get(text)
        if choice is None:
            await update.message.reply_text("یکی از دکمه‌های تعداد خواب را بزنید.", reply_markup=BEDROOM_KEYBOARD)
            return
        bedrooms, or_more = choice
        row.bedrooms = bedrooms
        row.bedrooms_or_more = or_more
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
