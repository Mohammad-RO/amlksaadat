import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Agent, Listing
from app.bot.handlers import _caption, _preview_listing
from app.services.divar import parse_divar_post
from app.services.llm import compose_listing_text, listing_details
from app.services.matching import match_listings
from app.utils import (
    build_year_from_text,
    duplicate_message,
    extract_divar_token,
    normalize_phone,
    parse_build_year,
    parse_report_bound,
)


SAMPLE = {
    "seo": {"title": "فروش آپارتمان سعادت‌آباد"},
    "sections": [
        {
            "widgets": [
                {
                    "widget_type": "LEGEND_TITLE_ROW",
                    "data": {"title": "۱۲۰ متر، دو خواب"},
                },
                {
                    "widget_type": "IMAGE_CAROUSEL",
                    "data": {
                        "items": [
                            {"image": {"url": "https://s100.divarcdn.com/static/photo/a.jpg?x=1"}},
                            {"image": {"url": "https://cdn.example.com/logo.png"}},
                        ]
                    },
                },
                {
                    "widget_type": "GROUP_INFO_ROW",
                    "data": {
                        "items": [
                            {"title": "متراژ", "value": "۱۲۰"},
                            {"title": "اتاق", "value": "۲"},
                        ]
                    },
                },
                {
                    "widget_type": "UNEXPANDABLE_ROW",
                    "data": {"title": "قیمت کل", "value": "۱۲٬۰۰۰٬۰۰۰٬۰۰۰ تومان"},
                },
                {
                    "widget_type": "UNEXPANDABLE_ROW",
                    "data": {"title": "قیمت هر متر", "value": "۱۰۰٬۰۰۰٬۰۰۰ تومان"},
                },
                {
                    "widget_type": "UNEXPANDABLE_ROW",
                    "data": {"title": "سال ساخت", "value": "۱۴۰۱"},
                },
                {
                    "widget_type": "DESCRIPTION_ROW",
                    "data": {"text": "آپارتمان نورگیر با بالکن، مناسب خانواده، طبقه سوم."},
                },
            ]
        }
    ],
}


class LogicTests(unittest.TestCase):
    def test_phone_and_token(self):
        self.assertEqual(normalize_phone("+98 912 123 4567"), "09121234567")
        self.assertEqual(normalize_phone("۰۹۱۲۱۲۳۴۵۶۷"), "09121234567")
        self.assertEqual(
            extract_divar_token("https://divar.ir/v/apartment/AbCdE1234?utm=1"),
            "AbCdE1234",
        )
        with self.assertRaises(ValueError):
            normalize_phone("12345")

    def test_duplicate_photo_sizes_collapse(self):
        payload = {
            "seo": {"title": "خانه"},
            "gallery": [
                "https://s100.divarcdn.com/static/photo/neda/webp_post/a/6639fed6-26d5-4d38-b198-83325805a1bc.webp",
                "https://s100.divarcdn.com/static/photo/neda/webp_thumbnail/b/6639fed6-26d5-4d38-b198-83325805a1bc.webp",
                "https://s100.divarcdn.com/static/photo/neda/webp_post/c/5e504121-6f1e-43d7-8ef5-0d46b0f635a0.webp",
                "https://s100.divarcdn.com/static/photo/neda/webp_thumbnail/d/5e504121-6f1e-43d7-8ef5-0d46b0f635a0.webp",
                "https://s100.divarcdn.com/static/photo/neda/post/e/6639fed6-26d5-4d38-b198-83325805a1bc.jpg",
                "https://mapimage.divarcdn.com/v8/mapimage?encrypted_data=abc",
                "https://s100.divarcdn.com/static/imgs/widget-icons/dark/icon_secondary/v1/parking.png",
            ],
        }
        post = parse_divar_post(payload)
        self.assertEqual(
            post.image_urls,
            [
                "https://s100.divarcdn.com/static/photo/neda/webp_post/a/6639fed6-26d5-4d38-b198-83325805a1bc.webp",
                "https://s100.divarcdn.com/static/photo/neda/webp_post/c/5e504121-6f1e-43d7-8ef5-0d46b0f635a0.webp",
            ],
        )

    def test_divar_parser(self):
        post = parse_divar_post(SAMPLE)
        self.assertEqual(post.area, 120)
        self.assertEqual(post.bedrooms, 2)
        self.assertEqual(post.price, 12_000_000_000)
        self.assertEqual(post.building_year, 1401)
        self.assertIn("نورگیر", post.description)
        self.assertEqual(post.image_urls, ["https://s100.divarcdn.com/static/photo/a.jpg"])
        self.assertEqual(
            post.specs,
            [
                ("متراژ", "۱۲۰"),
                ("اتاق", "۲"),
                ("قیمت کل", "۱۲٬۰۰۰٬۰۰۰٬۰۰۰ تومان"),
                ("قیمت هر متر", "۱۰۰٬۰۰۰٬۰۰۰ تومان"),
                ("سال ساخت", "۱۴۰۱"),
            ],
        )
        rendered = compose_listing_text(post, "متن تمیز توضیحات")
        self.assertIn("📐 متراژ: ۱۲۰", rendered)
        self.assertIn("📏 قیمت هر متر: ۱۰۰٬۰۰۰٬۰۰۰ تومان", rendered)
        self.assertIn("📝 توضیحات\nمتن تمیز توضیحات", rendered)
        self.assertNotIn("نورگیر", rendered)

    def test_duplicate_stamp(self):
        moment = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)
        text = duplicate_message("علی راد", moment)
        self.assertIn("علی راد", text)
        self.assertIn("این لینک را قبلاً وارد کرده است. تکراری است.", text)
        self.assertTrue(text.startswith("«"))
        self.assertTrue(text.endswith("»"))

    def test_listing_preview_stops_at_storage(self):
        full = "\n".join(
            [
                "فروش آپارتمان",
                "",
                "📐 متراژ: ۱۲۰",
                "🅿️ پارکینگ: دارد",
                "📦 انباری: دارد",
                "📄 سند: تک‌برگ",
                "",
                "📝 توضیحات",
                "متن کامل توضیحات",
                "",
                "کد: 12345678",
            ]
        )
        preview = _preview_listing(full)
        self.assertEqual(
            preview.splitlines(),
            [
                "فروش آپارتمان",
                "",
                "📐 متراژ: ۱۲۰",
                "🛏 اتاق: نامشخص",
                "🏢 طبقه: نامشخص",
                "🚪 تعداد واحد: نامشخص",
                "🏗️ ساخت: نامشخص",
                "💰 قیمت کل: نامشخص",
                "📏 قیمت هر متر: نامشخص",
            ],
        )
        details = listing_details(full)
        self.assertTrue(details.startswith(preview))
        self.assertEqual(details.count("فروش آپارتمان"), 1)
        self.assertIn("پارکینگ: دارد", details)
        self.assertIn("انباری: دارد", details)
        self.assertIn("سند: تک‌برگ", details)
        self.assertIn("📝 توضیحات\nمتن کامل توضیحات", details)
        self.assertIn("کد: 12345678", details)
        self.assertEqual(details.count("متراژ:"), 1)
        self.assertLessEqual(len(_caption("📐 متراژ: " + ("۱" * 2000))), 1024)

    def test_build_year_text(self):
        self.assertEqual(parse_build_year("نوساز", now_year=1405), 1405)
        self.assertEqual(parse_build_year("۵ سال", now_year=1405), 1400)
        self.assertEqual(
            build_year_from_text("🏗️ سال ساخت: ۱۴۰۰\nکد: 11111111", now_year=1405),
            1400,
        )

    def test_match_band(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        agent = Agent(name="علی راد", phone="09120000000", is_active=True)
        db.add(agent)
        db.flush()

        def add(area, price, bedrooms, code, token, year=1402):
            db.add(
                Listing(
                    agent_id=agent.id,
                    divar_url=f"https://divar.ir/v/{token}",
                    divar_token=token,
                    title="خانه",
                    area=area,
                    price=price,
                    bedrooms=bedrooms,
                    building_year=year,
                    raw_description="",
                    structured_text=f"کد: {code}",
                    unique_code=code,
                    image_file_ids=[],
                    image_urls=[],
                    llm_used=False,
                )
            )

        add(120, 40_000_000_000, 2, "11111111", "token-hit", 1402)
        add(80, 40_000_000_000, 2, "22222222", "token-small", 1402)
        add(120, 40_000_000_000, 3, "33333333", "token-rooms", 1402)
        add(None, 40_000_000_000, 2, "44444444", "token-empty", 1402)
        add(120, 40_000_000_000, 4, "55555555", "token-four", 1402)
        add(120, 40_000_000_000, 5, "66666666", "token-five", 1370)
        add(300, 350_000_000_000, 2, "77777777", "token-large", 1405)
        db.commit()

        inside = match_listings(
            db,
            area=(110, 130),
            price=(30_000_000_000, 50_000_000_000),
            bedrooms=2,
            age=(0, 4),
            now_year=1405,
        )
        self.assertEqual([item.unique_code for item in inside], ["11111111"])
        more = match_listings(
            db,
            area=(110, 130),
            price=(30_000_000_000, 50_000_000_000),
            bedrooms=4,
            bedrooms_or_more=True,
            now_year=1405,
        )
        self.assertCountEqual([item.unique_code for item in more], ["55555555", "66666666"])
        skipped_area = match_listings(
            db,
            price=(30_000_000_000, 50_000_000_000),
            bedrooms=2,
            now_year=1405,
        )
        self.assertIn("44444444", [item.unique_code for item in skipped_area])
        old = match_listings(db, age=(30, None), now_year=1405)
        self.assertEqual([item.unique_code for item in old], ["66666666"])
        brand_new = match_listings(db, age=(0, 1), now_year=1405)
        self.assertEqual([item.unique_code for item in brand_new], ["77777777"])
        capped = [item.unique_code for item in match_listings(db, price=(None, 140_000_000_000), now_year=1405)]
        self.assertIn("11111111", capped)
        self.assertNotIn("77777777", capped)
        db.close()

    def test_jalali_report_bound(self):
        start = parse_report_bound("1404/01/01", end_of_day=False)
        end = parse_report_bound("1404/01/01", end_of_day=True)
        self.assertLess(start, end)
        self.assertEqual((end - start).total_seconds(), 24 * 60 * 60)


if __name__ == "__main__":
    unittest.main()
