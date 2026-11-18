"""Your own items: everything about them is kept, and a database made by 1.1.2 opens with nothing lost."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from helpers import at, item, store

from server import ListServer
from store import Store

# The tables exactly as Birdbrain 1.1.2 made them.
V112 = """
CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT, kind TEXT, title TEXT, due TEXT, course TEXT, url TEXT,
                    detail TEXT, confidence REAL, needs_review INTEGER, first_seen TEXT, last_seen TEXT,
                    level TEXT DEFAULT '', done_at TEXT);
CREATE TABLE judged (hash TEXT PRIMARY KEY, item_id TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE placement (id TEXT PRIMARY KEY, how TEXT);
INSERT INTO items VALUES ('moodle:cm:7', 'moodle', 'assignment', 'Essay 2', '2026-11-20T23:59', 'ENGL 2000',
                          'https://example.edu/7', '', NULL, 0, '2026-11-01T09:00:00', '2026-11-17T09:00:00', '', NULL);
INSERT INTO items VALUES ('moodle:cal:8', 'moodle', 'test', 'Exam 2', '2026-11-21T09:30', 'MATH 1550', '', '', NULL, 0,
                          '2026-11-01T09:00:00', '2026-11-17T09:00:00', 'exam', '2026-11-16T20:15:00');
INSERT INTO items VALUES ('manual:0123456789ab', 'manual', 'event', 'Dentist', '2026-11-19T15:00', '', '', 'bring the form',
                          NULL, 0, '2026-11-10T09:00:00', '2026-11-10T09:00:00', '', NULL);
INSERT INTO items VALUES ('manual:ba9876543210', 'manual', 'test', 'Practice quiz', '2026-11-22T23:59', 'CHEM 1202', '', '',
                          NULL, 0, '2026-11-10T09:00:00', '2026-11-10T09:00:00', 'quiz', NULL);
INSERT INTO judged VALUES ('abc123', 'outlook:mail:1');
INSERT INTO meta VALUES ('prefs', '{"layout": "focus", "focus_theme": "paper"}');
INSERT INTO meta VALUES ('login_done', '1');
INSERT INTO placement VALUES ('moodle:cm:7', 'archived');
"""


def server(s):
    return ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                      request_mail_scan=lambda d: None, on_change=lambda: None)


class From112(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "birdbrain.db"
        db = sqlite3.connect(self.path)
        db.executescript(V112)
        db.commit()
        db.close()

    def test_everything_in_a_112_database_is_still_there(self):
        s = Store(self.path)
        essay, exam = s.get("moodle:cm:7"), s.get("moodle:cal:8")
        dentist, quiz = s.get("manual:0123456789ab"), s.get("manual:ba9876543210")
        self.assertEqual((essay.title, essay.due, essay.url), ("Essay 2", datetime(2026, 11, 20, 23, 59), "https://example.edu/7"))
        self.assertEqual((exam.level, exam.done_at), ("exam", datetime(2026, 11, 16, 20, 15)))
        self.assertEqual((dentist.title, dentist.kind, dentist.due, dentist.detail),
                         ("Dentist", "event", datetime(2026, 11, 19, 15, 0), "bring the form"))
        self.assertEqual((quiz.kind, quiz.level, quiz.course), ("test", "quiz", "CHEM 1202"))
        self.assertEqual([i.label for i in (essay, exam, dentist, quiz)], [""] * 4)   # labels are new: none yet
        self.assertEqual(s.placements(), {"moodle:cm:7": "archived"})
        self.assertEqual(s.get_meta("login_done"), "1")
        self.assertIn("paper", s.get_meta("prefs"))
        self.assertTrue(s.already_judged("abc123"))

    def test_it_can_be_opened_again_and_again(self):
        Store(self.path)._db.close()
        s = Store(self.path)
        self.assertEqual(len(s.items_between(datetime(2026, 11, 1), datetime(2026, 12, 1))), 4)

    def test_an_old_item_can_take_a_label_and_keeps_the_rest(self):
        s = Store(self.path)
        srv = server(s)
        srv.update_item({"id": "manual:0123456789ab", "title": "Dentist", "kind": "event", "date": "2026-11-19",
                         "time": "15:00", "notes": "bring the form", "label": "appointment"})
        got = s.get("manual:0123456789ab")
        self.assertEqual((got.label, got.detail, got.due), ("appointment", "bring the form", datetime(2026, 11, 19, 15, 0)))


class EveryField(unittest.TestCase):
    def test_a_personal_item_keeps_all_of_itself(self):
        s = store()
        srv = server(s)
        new = srv.add_item({"title": "  Lab   report ", "kind": "assignment", "date": "2026-11-20", "time": "17:00",
                            "course": "CHEM 1202", "notes": "sections 3 and 4", "label": "work"})
        got = s.get(new["id"])
        self.assertEqual((got.title, got.kind, got.due, got.course, got.detail, got.label, got.source),
                         ("Lab report", "assignment", datetime(2026, 11, 20, 17, 0), "CHEM 1202", "sections 3 and 4",
                          "work", "manual"))
        s.set_done(got.id, True)                       # done
        s.set_placement(got.id, "archived")            # archived
        srv.update_item({"id": got.id, "title": "Lab report", "kind": "assignment", "date": "2026-11-21", "label": ""})
        after = s.get(got.id)
        self.assertIsNotNone(after.done_at)
        self.assertEqual(s.placements(), {got.id: "archived"})
        self.assertEqual((after.label, after.due), ("", datetime(2026, 11, 21, 23, 59)))   # no time given

    def test_delete_and_undo_bring_the_label_back(self):
        s = store()
        srv = server(s)
        new = srv.add_item({"title": "Club meeting", "kind": "event", "date": "2026-11-20", "label": "extracurricular"})
        gone = srv.delete_item({"id": new["id"]})["item"]
        self.assertEqual(gone["label"], "extracurricular")
        srv.restore_item(gone)
        self.assertEqual(s.get(new["id"]).label, "extracurricular")

    def test_a_label_must_look_like_one(self):
        with self.assertRaisesRegex(ValueError, "Unknown label"):
            server(store()).add_item({"title": "x", "kind": "event", "date": "2026-11-20", "label": "<b>nope</b>"})

    def test_a_scan_does_not_touch_your_own_items(self):
        s = store()
        s.upsert(item("manual:1", "Gym", at(1, 18, 0), kind="event", course="", label="life"))
        s.remove_missing("moodle:", set())
        self.assertEqual(s.get("manual:1").label, "life")


if __name__ == "__main__":
    unittest.main()
