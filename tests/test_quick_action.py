"""Quick write, as the page asks for it: read as you type, save on Enter. And the label tag on a card."""
from __future__ import annotations

import unittest
from datetime import datetime

from helpers import NOW, at, item, store

import prefs
import report
from config import Settings
from server import ListServer


def server(s):
    return ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                      request_mail_scan=lambda d: None, on_change=lambda: None)


class Quick(unittest.TestCase):
    def setUp(self):
        self.store = store()
        self.store.upsert(item("moodle:cm:1", course="2026 Fall CHEM 1202 for A. Teacher"))
        self.store.upsert(item("moodle:cm:2", course="2026 Fall MATH 1550 for B. Teacher"))
        self.srv = server(self.store)

    def test_reading_says_how_the_line_was_understood_and_saves_nothing(self):
        got = self.srv.quick({"text": "chem lab report fri 5pm #life"}, NOW)
        self.assertEqual((got["title"], got["date"], got["time"], got["label"], got["day"]),
                         ("Chem lab report", "2026-11-20", "17:00", "life", "Friday, Nov 20"))
        self.assertEqual([(c["what"], c["says"]) for c in got["chips"]],
                         [("day", "Friday, Nov 20"), ("time", "5:00 PM"), ("label", "Life")])
        self.assertNotIn("id", got)
        self.assertEqual(len(self.store.items_between(datetime(2026, 1, 1), datetime(2028, 1, 1))), 2)

    def test_the_students_own_courses_are_known(self):
        self.assertEqual(self.srv.courses(), ["CHEM 1202", "MATH 1550"])
        self.assertEqual(self.srv.quick({"text": "problem set @math"}, NOW)["course"], "MATH 1550")

    def test_saving_adds_an_item_of_yours_with_everything_read(self):
        got = self.srv.quick({"text": "dentist tue 3pm #appointment", "save": True}, NOW)
        saved = self.store.get(got["id"])
        self.assertEqual((saved.source, saved.title, saved.kind, saved.due, saved.label, saved.timed),
                         ("manual", "Dentist", "event", datetime(2026, 11, 24, 15, 0), "appointment", True))

    def test_no_day_is_today_and_no_time_is_no_time(self):
        got = self.srv.quick({"text": "buy milk", "save": True}, NOW)
        saved = self.store.get(got["id"])
        self.assertEqual((saved.due, saved.timed), (datetime(2026, 11, 18, 23, 59), False))
        self.assertFalse(report.has_time(saved))

    def test_1159_pm_typed_on_purpose_is_a_real_time(self):
        saved = self.store.get(self.srv.quick({"text": "essay 11:59pm", "save": True}, NOW)["id"])
        self.assertTrue(report.has_time(saved))

    def test_a_word_handed_back_stays_in_the_title(self):
        got = self.srv.quick({"text": "friday night lights", "skip": ["friday"]}, NOW)
        self.assertEqual((got["title"], got["date"]), ("Friday night lights", "2026-11-18"))

    def test_nothing_typed_cannot_be_saved(self):
        for text in ("", "   ", "fri 5pm"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Type what it is"):
                self.srv.quick({"text": text, "save": True}, NOW)

    def test_a_renamed_label_is_still_found_by_its_new_name(self):
        p = prefs.load(self.store)
        p["labels"][0]["name"] = "Home"
        self.store.set_meta(prefs.KEY, __import__("json").dumps(p))
        self.assertEqual(self.srv.quick({"text": "groceries #home"}, NOW)["label"], "life")


class LabelTag(unittest.TestCase):
    def page(self, p=None):
        s = store()
        s.upsert(item("manual:1", "Groceries", at(1), kind="assignment", course="", label="life", timed=False))
        s.upsert(item("manual:2", "Gone label", at(1), kind="assignment", course="", label="deleted", timed=False))
        return report.render_board(report.build(s, Settings(), NOW), Settings(), "", NOW, prefs=p or prefs.DEFAULTS)

    def test_a_card_carries_its_labels_name_and_colour(self):
        page = self.page()
        self.assertIn('<span class="lab" data-label="life" style="--lab:#3fa7a0">Life</span>', page)
        self.assertEqual(page.count('class="lab"'), 1)   # a label that no longer exists shows nothing

    def test_the_four_labels_to_begin_with(self):
        self.assertEqual([x["name"] for x in prefs.load(store())["labels"]],
                         ["Life", "Extracurricular", "Appointment", "Work"])

    def test_labels_that_are_not_labels_are_dropped_on_load(self):
        s = store()
        s.set_meta(prefs.KEY, '{"labels": [{"id": "ok", "name": "Fine", "color": "#112233"}, {"id": "BAD ID", "name": "x"}, '
                              '{"id": "ok", "name": "twice"}, "junk", {"id": "nameless", "name": "  "}]}')
        self.assertEqual(prefs.load(s)["labels"], [{"id": "ok", "name": "Fine", "color": "#112233"}])


if __name__ == "__main__":
    unittest.main()
