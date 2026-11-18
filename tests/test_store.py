"""The store: items survive scans with their ticks, the student's own placement, and old databases still open."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import timedelta
from pathlib import Path

from helpers import NOW, at, item, store

from store import Store


class Items(unittest.TestCase):
    def test_new_then_refreshed(self):
        s = store()
        self.assertTrue(s.upsert(item(title="Lab report 4")))
        self.assertFalse(s.upsert(item(title="Lab report 4 (revised)")))
        self.assertEqual(s.get("moodle:cm:1").title, "Lab report 4 (revised)")

    def test_a_tick_survives_the_next_scan(self):
        s = store()
        s.upsert(item())
        self.assertTrue(s.set_done("moodle:cm:1", True))
        s.upsert(item(title="Lab report 4, due date moved", due=at(3)))
        got = s.get("moodle:cm:1")
        self.assertIsNotNone(got.done_at)
        self.assertEqual(got.due, at(3))
        s.set_done("moodle:cm:1", False)
        self.assertIsNone(s.get("moodle:cm:1").done_at)

    def test_ticking_something_that_is_not_there(self):
        self.assertFalse(store().set_done("moodle:cm:404", True))

    def test_between_is_in_due_order_and_skips_undated(self):
        s = store()
        s.upsert(item("moodle:cm:2", "Second", at(2)))
        s.upsert(item("moodle:cm:1", "First", at(1)))
        s.upsert(item("moodle:cm:3", "No date", None))
        s.upsert(item("moodle:cm:4", "Too far", at(40)))
        got = s.items_between(NOW - timedelta(days=1), NOW + timedelta(days=30))
        self.assertEqual([i.title for i in got], ["First", "Second"])

    def test_every_change_bumps_the_version_the_page_polls(self):
        s = store()
        before = s.version
        s.upsert(item())
        s.set_done("moodle:cm:1", True)
        s.set_placement("moodle:cm:1", "archived")
        self.assertGreaterEqual(s.version, before + 3)


class Missing(unittest.TestCase):
    def test_work_moodle_no_longer_lists_goes(self):
        s = store()
        s.upsert(item("moodle:cm:1"))
        s.upsert(item("moodle:cm:2"))
        s.upsert(item("gradescope:9", source="gradescope"))
        self.assertEqual(s.remove_missing("moodle:cm:", {"moodle:cm:2"}), 1)
        self.assertFalse(s.exists("moodle:cm:1"))
        self.assertTrue(s.exists("moodle:cm:2"))
        self.assertTrue(s.exists("gradescope:9"))

    def test_one_scan_that_missed_it_does_not_delete_it(self):
        s = store()
        s.upsert(item("moodle:cm:1"))
        self.assertEqual(s.remove_missing("moodle:cm:", set(), grace=timedelta(hours=6)), 0)
        self.assertTrue(s.exists("moodle:cm:1"))


class Placement(unittest.TestCase):
    def test_archive_show_and_back_to_the_rules(self):
        s = store()
        s.upsert(item())
        self.assertIsNone(s.set_placement("moodle:cm:1", "archived"))
        self.assertEqual(s.placements(), {"moodle:cm:1": "archived"})
        self.assertEqual(s.set_placement("moodle:cm:1", "shown"), "archived")
        self.assertEqual(s.set_placement("moodle:cm:1", None), "shown")
        self.assertEqual(s.placements(), {})

    def test_an_unknown_place_is_refused(self):
        with self.assertRaises(ValueError):
            store().set_placement("moodle:cm:1", "somewhere")

    def test_deleting_an_item_forgets_its_placement(self):
        s = store()
        s.upsert(item())
        s.set_placement("moodle:cm:1", "archived")
        s.delete("moodle:cm:1")
        self.assertEqual(s.placements(), {})


class OlderDatabases(unittest.TestCase):
    def test_a_database_from_before_ticks_and_levels_still_opens(self):
        path = Path(store()._db.execute("PRAGMA database_list").fetchone()[2]).with_name("old.db")
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT, kind TEXT, title TEXT, due TEXT, course TEXT,
                                url TEXT, detail TEXT, confidence REAL, needs_review INTEGER,
                                first_seen TEXT, last_seen TEXT);
            INSERT INTO items VALUES ('moodle:cm:7', 'moodle', 'assignment', 'Essay 2', '2026-11-20T23:59',
                                      'ENGL 2000', '', '', NULL, 0, '2026-11-01T09:00:00', '2026-11-01T09:00:00');
        """)
        db.commit()
        db.close()
        s = Store(path)
        got = s.get("moodle:cm:7")
        self.assertEqual((got.title, got.level, got.done_at), ("Essay 2", "", None))
        s.set_done("moodle:cm:7", True)
        self.assertIsNotNone(s.get("moodle:cm:7").done_at)

    def test_meta_round_trip(self):
        s = store()
        self.assertEqual(s.get_meta("nothing", "fallback"), "fallback")
        s.set_meta("last_scan", "2026-11-18T10:00")
        self.assertEqual(s.get_meta("last_scan"), "2026-11-18T10:00")


if __name__ == "__main__":
    unittest.main()
