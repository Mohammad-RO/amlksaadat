import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.errors import AppError
from app.models import DivarColleague
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
        added, removed, updated = apply_colleague_snapshot(
            self.db,
            business,
            [
                ColleagueSnapshot("a", "ماهان حسن نژاد", "09122167922", "همکار"),
                ColleagueSnapshot("c", "فرهاد", "09122361418", "مدیر"),
            ],
        )
        self.db.commit()
        self.assertEqual((added, removed, updated), (1, 1, 1))
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
