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
    apply_colleague_snapshot,
    parse_agent_management_url,
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
