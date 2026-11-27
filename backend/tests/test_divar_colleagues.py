import asyncio
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.errors import AppError
from app.models import Agent, DivarColleague, Listing
from app.services.divar import DivarPost
from app.services.divar_import import apply_consultant_change, drop_listings_outside, sync_result_note
from app.services.listings import describe_listing_changes, listing_content_changed
from app.services.llm import compose_listing_text
from app.services.divar_panel import (
    ColleagueSnapshot,
    _agent_refs,
    _person_from_details,
    active_posts_from_page,
    apply_colleague_snapshot,
    author_from_label,
    match_colleague,
    parse_agent_management_url,
    parse_posts_url,
    public_post_url,
)


class DivarColleagueSyncTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_agent_link(self):
        url, token = parse_agent_management_url(
            "https://divar.ir/my-divar/my-business/wgiqQiGe/agent-management"
        )
        self.assertEqual(token, "wgiqQiGe")
        self.assertEqual(url, "https://divar.ir/my-divar/my-business/wgiqQiGe/agent-management")

    def test_posts_link_is_rejected(self):
        with self.assertRaises(AppError):
            parse_agent_management_url("https://divar.ir/my-divar/my-posts")

    def test_snapshot_applies_add_update_and_remove(self):
        business = "wgiqQiGe"
        apply_colleague_snapshot(
            self.db,
            business,
            [
                ColleagueSnapshot("a", "ماهان", "09122167922", "همکار"),
                ColleagueSnapshot("b", "رضا", "09121097021", "همکار"),
            ],
        )
        self.db.commit()
        added, removed, updated, diff = apply_colleague_snapshot(
            self.db,
            business,
            [
                ColleagueSnapshot("a", "ماهان حسن نژاد", "09122167922", "همکار"),
                ColleagueSnapshot("c", "فرهاد", "09122361418", "مدیر"),
            ],
        )
        self.db.commit()
        self.assertEqual((added, removed, updated), (1, 1, 1))
        self.assertEqual(diff.added, ["فرهاد"])
        self.assertEqual(diff.removed, ["رضا"])
        self.assertEqual(diff.renames, [{"old_name": "ماهان", "new_name": "ماهان حسن نژاد"}])
        self.assertEqual(diff.phones, [])
        rows = {row.relation_token: row for row in self.db.query(DivarColleague).all()}
        self.assertEqual(set(rows), {"a", "c"})
        self.assertEqual(rows["a"].name, "ماهان حسن نژاد")
        self.assertEqual(rows["c"].phone, "09122361418")

    def test_empty_snapshot_does_not_wipe(self):
        apply_colleague_snapshot(
            self.db,
            "wgiqQiGe",
            [ColleagueSnapshot("a", "ماهان", "09122167922", "همکار")],
        )
        self.db.commit()
        with self.assertRaises(AppError):
            apply_colleague_snapshot(self.db, "wgiqQiGe", [])
        self.db.rollback()
        self.assertEqual(self.db.query(DivarColleague).count(), 1)

    def test_details_phone(self):
        refs = _agent_refs(
            {
                "page": {
                    "widget_list": [
                        {
                            "widget_type": "SELECTOR_ROW",
                            "data": {
                                "title": "ماهان",
                                "action": {
                                    "type": "PREMIUM_PANEL_AGENT_DETAILS",
                                    "payload": {"relation_token": "abc"},
                                },
                            },
                        }
                    ]
                }
            }
        )
        self.assertEqual(refs, [("ماهان", "abc")])
        name, phone, role = _person_from_details(
            {
                "page": {
                    "widget_list": [
                        {"widget_type": "TITLE_ROW", "data": {"text": "ماهان حسن نژاد"}},
                        {"widget_type": "UNEXPANDABLE_ROW", "data": {"title": "شمارهٔ موبایل", "value": "۰۹۱۲۲۱۶۷۹۲۲"}},
                        {"widget_type": "UNEXPANDABLE_ROW", "data": {"title": "نوع دسترسی", "value": "همکار"}},
                    ]
                }
            },
            "ماهان",
        )
        self.assertEqual(name, "ماهان حسن نژاد")
        self.assertEqual(phone, "۰۹۱۲۲۱۶۷۹۲۲")
        self.assertEqual(role, "همکار")

    def test_posts_link_and_active_page(self):
        self.assertEqual(parse_posts_url("https://divar.ir/my-divar/my-posts"), "https://divar.ir/my-divar/my-posts")
        with self.assertRaises(AppError):
            parse_posts_url("https://divar.ir/my-divar/my-posts/waEMTo_j-Sxikn")
        posts, cursor, has_next = active_posts_from_page(
            {
                "tab_bar": {"current_tab_identifier": "ongoing"},
                "page": {
                    "widget_list": [
                        {
                            "widget_type": "CONTENT_CONTAINER",
                            "data": {
                                "widgets": [
                                    {
                                        "widget_type": "POST_ROW",
                                        "data": {
                                            "title": "آپارتمان",
                                            "top_description_text": "توسط: شهاب اكبرى",
                                            "action": {"payload": {"manage_token": "waEMTo_j-Sxikn"}},
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                    "infinite_scroll_response": {"has_next": False, "last_item_identifier": "end"},
                },
            }
        )
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].author, "شهاب اكبرى")
        self.assertEqual(author_from_label("توسط: شهاب اکبری"), "شهاب اکبری")
        self.assertFalse(has_next)
        self.assertEqual(cursor, "end")
        self.assertEqual(
            public_post_url({"widgets": [{"text": "مشاهده در https://divar.ir/v/waEMTo_j"}]}),
            "https://divar.ir/v/waEMTo_j",
        )

    def test_colleague_name_match(self):
        people = [("شهاب اكبرى", "09121276459"), ("ماهان", "09024313120"), ("ماهان حسن نژاد", "09122167922")]
        self.assertEqual(match_colleague("شهاب اکبری", people), ("شهاب اكبرى", "09121276459"))
        self.assertEqual(match_colleague("ماهان", people)[0], "ماهان")
        with self.assertRaises(AppError):
            match_colleague("فرهاد", people)
        with self.assertRaises(AppError):
            match_colleague("ماهان", [("ماهان", "09024313120"), ("ماهان", "09120000000")])

    def test_drop_listings_outside_active_set(self):
        agent = Agent(name="ورود دیوار", phone="09000000000", is_active=False)
        self.db.add(agent)
        self.db.flush()
        for token, code in (("keep", "11111111"), ("gone", "22222222")):
            self.db.add(
                Listing(
                    agent_id=agent.id,
                    divar_url=f"https://divar.ir/v/{token}",
                    divar_token=token,
                    title="خانه",
                    unique_code=code,
                )
            )
        self.db.commit()
        removed = drop_listings_outside(self.db, {"keep"})
        self.db.commit()
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["title"], "خانه")
        left = {row.divar_token for row in self.db.query(Listing).all()}
        self.assertEqual(left, {"keep"})
        removed_all = drop_listings_outside(self.db, set())
        self.db.commit()
        self.assertEqual(len(removed_all), 1)
        self.assertEqual(self.db.query(Listing).count(), 0)

    def test_consultant_change_updates_name_and_phone(self):
        agent = Agent(name="ورود دیوار", phone="09000000000", is_active=False)
        self.db.add(agent)
        self.db.flush()
        listing = Listing(
            agent_id=agent.id,
            divar_url="https://divar.ir/v/keep",
            divar_token="keep",
            title="خانه",
            unique_code="33333333",
            consultant_name="شهاب اكبرى",
            consultant_phone="09121276459",
        )
        people = [("شهاب اکبری", "09121276459"), ("فرهاد", "09122361418")]
        self.assertFalse(apply_consultant_change(listing, "شهاب اکبری", people))
        self.assertEqual(listing.consultant_phone, "09121276459")
        self.assertTrue(apply_consultant_change(listing, "فرهاد", people))
        self.assertEqual(listing.consultant_name, "فرهاد")
        self.assertEqual(listing.consultant_phone, "09122361418")
        with self.assertRaises(AppError):
            apply_consultant_change(listing, "رضا", people)
        self.assertEqual(listing.consultant_name, "فرهاد")
        self.assertEqual(listing.consultant_phone, "09122361418")

    def test_description_alone_does_not_count_as_change(self):
        post = DivarPost(
            title="خانه",
            description="توضیح تازه",
            area=80,
            price=1_000,
            bedrooms=2,
            building_year=1400,
            image_urls=["https://img/a.jpg"],
            specs=[("متراژ", "۸۰"), ("تعداد اتاق", "۲")],
            category="residential",
            deal_type="sell",
        )
        listing = Listing(
            agent_id=1,
            divar_url="https://divar.ir/v/abcde",
            divar_token="abcde",
            title="خانه",
            area=80,
            price=1_000,
            bedrooms=2,
            building_year=1400,
            category="residential",
            deal_type="sell",
            unique_code="33333333",
            image_urls=["https://img/a.jpg"],
            structured_text=compose_listing_text(post, "توضیح قدیمی") + "\n\nکد: 33333333",
        )
        self.assertFalse(listing_content_changed(listing, post))
        post.price = 2_000
        self.assertTrue(listing_content_changed(listing, post))
        post.price = 1_000
        post.image_urls = ["https://img/b.jpg"]
        self.assertTrue(listing_content_changed(listing, post))

    def test_phone_change_is_separate_from_rename(self):
        business = "wgiqQiGe"
        apply_colleague_snapshot(
            self.db,
            business,
            [ColleagueSnapshot("a", "ماهان", "09122167922", "همکار")],
        )
        self.db.commit()
        _added, _removed, _updated, diff = apply_colleague_snapshot(
            self.db,
            business,
            [ColleagueSnapshot("a", "ماهان", "09120000000", "همکار")],
        )
        self.assertEqual(diff.phones, [{"name": "ماهان", "old_phone": "09122167922", "new_phone": "09120000000"}])
        self.assertEqual(diff.renames, [])
        self.assertEqual(diff.added, [])
        self.assertEqual(diff.removed, [])

    def test_report_describes_price_specs_and_photos(self):
        post = DivarPost(
            title="خانه",
            description="توضیح تازه",
            area=80,
            price=1_000,
            bedrooms=2,
            building_year=1400,
            image_urls=["https://img/a.jpg"],
            specs=[("متراژ", "۸۰"), ("تعداد اتاق", "۲"), ("پارکینگ", "دارد")],
            category="residential",
            deal_type="sell",
        )
        listing = Listing(
            agent_id=1,
            divar_url="https://divar.ir/v/abcde",
            divar_token="abcde",
            title="خانه",
            area=80,
            price=1_000,
            bedrooms=2,
            building_year=1400,
            category="residential",
            deal_type="sell",
            unique_code="33333333",
            image_urls=["https://img/a.jpg"],
            structured_text=compose_listing_text(post, "توضیح قدیمی") + "\n\nکد: 33333333",
        )
        self.assertEqual(describe_listing_changes(listing, post), [])
        post.price = 2_000
        price_changes = describe_listing_changes(listing, post)
        self.assertEqual([item["label"] for item in price_changes], ["قیمت"])
        post.price = 1_000
        post.specs = [("متراژ", "۸۰"), ("تعداد اتاق", "۲"), ("پارکینگ", "ندارد")]
        spec_changes = describe_listing_changes(listing, post)
        parking = next(item for item in spec_changes if item["label"] == "پارکینگ")
        self.assertEqual(parking["old"], "دارد")
        self.assertEqual(parking["new"], "ندارد")
        self.assertFalse(any(item["label"] == "متراژ" for item in spec_changes))
        post.specs = [("متراژ", "۸۰"), ("تعداد اتاق", "۲"), ("پارکینگ", "دارد")]
        post.image_urls = ["https://img/b.jpg"]
        photo_changes = describe_listing_changes(listing, post)
        self.assertEqual(photo_changes, [{"label": "عکس‌ها", "old": "", "new": "عوض شد"}])


class DivarSyncPauseTest(unittest.TestCase):
    def tearDown(self):
        from app.services import divar_import

        divar_import._gate.set()
        divar_import._status = divar_import.SyncStatus()
        divar_import.save_sync_mark = self._saved_mark

    def setUp(self):
        from app.services import divar_import

        self._saved_mark = divar_import.save_sync_mark
        divar_import.save_sync_mark = lambda *args, **kwargs: None

    def test_pause_holds_until_resume(self):
        from app.services import divar_import

        async def main():
            divar_import._gate = asyncio.Event()
            divar_import._gate.set()
            divar_import._status.running = True
            divar_import.pause_sync()
            self.assertTrue(divar_import.sync_status().paused)
            task = asyncio.create_task(divar_import._wait_if_paused())
            await asyncio.sleep(0.05)
            self.assertFalse(task.done())
            divar_import.resume_sync()
            await task
            self.assertFalse(divar_import.sync_status().paused)

        asyncio.run(main())

    def test_cancel_stops_instead_of_resuming(self):
        from app.services import divar_import

        async def main():
            divar_import._gate = asyncio.Event()
            divar_import._gate.set()
            divar_import._status.running = True
            divar_import._status.phase = "sending"
            divar_import.pause_sync()
            task = asyncio.create_task(divar_import._wait_if_paused())
            await asyncio.sleep(0.05)
            divar_import.cancel_sync()
            with self.assertRaises(asyncio.CancelledError):
                await task
            resumed = divar_import.resume_sync()
            self.assertFalse(resumed.running)
            self.assertFalse(resumed.paused)
            self.assertEqual(resumed.phase, "idle")

        asyncio.run(main())


class SyncResultNoteTest(unittest.TestCase):
    def test_complete_and_partial_notes(self):
        self.assertEqual(sync_result_note(True, 190, 190, True), "کامل")
        self.assertEqual(
            sync_result_note(False, 25, 190, True),
            "ناقص: بررسی لیست مشاوران و 25 آگهی از 190",
        )
        self.assertEqual(sync_result_note(False, 0, 0, False), "ناقص: بررسی لیست مشاوران")
