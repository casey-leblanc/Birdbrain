"""What is this? The student's own answer beats the rules, sticks across scans, and goes for the whole series."""
from __future__ import annotations

import unittest

from helpers import NOW, at, item, store

import report
from config import Settings
from server import ListServer
from store import series_of

CHEM = "2026 Fall CHEM 1212 for A. Teacher"


def lab(n, name, kind="test", **more):
    return item(f"moodle:cm:{n}", f"Biochemical Testing - {name} Test", at(n), kind=kind, course=CHEM, **more)


class Series(unittest.TestCase):
    def test_what_a_run_of_items_has_in_common(self):
        self.assertEqual(series_of("Biochemical Testing - Indole Test"), "biochemical testing")
        self.assertEqual(series_of("Biochemical Testing – Urease Test"), "biochemical testing")
        self.assertEqual(series_of("Exp #19 Quiz: Titration"), "exp # quiz")
        self.assertEqual(series_of("Quiz 4"), "quiz")


class Saying(unittest.TestCase):
    def test_one_answer_fixes_the_whole_series_in_that_course(self):
        s = store()
        for n, name in enumerate(("Oxidase", "Catalase", "Urease"), 1):
            s.upsert(lab(n, name))
        s.upsert(item("moodle:cm:9", "Biochemical Testing - Final", at(5), kind="test", course="BIOL 2051"))
        changed = s.say_kind(s.get("moodle:cm:1"), "assignment")
        self.assertEqual(sorted(i.id for i in changed), ["moodle:cm:2", "moodle:cm:3"])
        self.assertEqual({s.get(f"moodle:cm:{n}").kind for n in (1, 2, 3)}, {"assignment"})
        self.assertEqual(s.get("moodle:cm:9").kind, "test")   # another course's series is its own

    def test_it_sticks_when_the_next_scan_says_otherwise(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.say_kind(s.get("moodle:cm:1"), "assignment")
        s.upsert(lab(1, "Oxidase", kind="test", level="exam"))
        got = s.get("moodle:cm:1")
        self.assertEqual((got.kind, got.level), ("assignment", ""))

    def test_new_ones_in_the_series_arrive_already_right(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.say_kind(s.get("moodle:cm:1"), "assignment")
        s.upsert(lab(4, "Indole"))
        self.assertEqual(s.get("moodle:cm:4").kind, "assignment")

    def test_an_answer_about_one_item_in_particular_stands(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.upsert(item("moodle:cm:2", "Biochemical Testing - Practical Exam", at(2), kind="test", course=CHEM))
        s.say_kind(s.get("moodle:cm:2"), "exam")
        changed = s.say_kind(s.get("moodle:cm:1"), "assignment")
        self.assertEqual(changed, [])
        got = s.get("moodle:cm:2")
        self.assertEqual((got.kind, got.level), ("test", "exam"))

    def test_quiz_exam_and_event(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Chapter 3", kind="assignment", course=CHEM))
        for what, want in (("quiz", ("test", "quiz")), ("exam", ("test", "exam")), ("event", ("event", ""))):
            s.say_kind(s.get("moodle:cm:1"), what)
            got = s.get("moodle:cm:1")
            self.assertEqual((got.kind, got.level), want)
        self.assertEqual(report.test_level(s.get("moodle:cm:1")), None)

    def test_an_email_that_names_no_course_changes_only_itself(self):
        s = store()
        s.upsert(item("outlook-mail:1", "Reminder: bring a calculator", kind="test", course=""))
        s.upsert(item("outlook-mail:2", "Reminder: parking", kind="event", course=""))
        self.assertEqual(s.say_kind(s.get("outlook-mail:1"), "event"), [])
        s.upsert(item("outlook-mail:3", "Reminder: Exam 2 Friday", kind="test", course=""))
        self.assertEqual(s.get("outlook-mail:3").kind, "test")

    def test_the_students_own_items_are_left_alone(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.upsert(item("manual:1", "Biochemical Testing - my notes", kind="event", course="CHEM 1212"))
        s.say_kind(s.get("moodle:cm:1"), "assignment")
        self.assertEqual(s.get("manual:1").kind, "event")


class FromThePage(unittest.TestCase):
    def server(self, s):
        return ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                          request_mail_scan=lambda d: None, on_change=lambda: None)

    def test_the_page_asks_and_hears_how_many_followed(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.upsert(lab(2, "Catalase"))
        got = self.server(s).kind({"id": "moodle:cm:1", "what": "assignment"})
        self.assertEqual(got, {"ok": True, "what": "assignment", "also": 1})

    def test_nonsense_and_own_items_are_refused(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.upsert(item("manual:1", "Dentist", kind="event", course=""))
        srv = self.server(s)
        for body in ({"id": "moodle:cm:1", "what": "holiday"}, {"id": "nope", "what": "exam"},
                     {"id": "manual:1", "what": "exam"}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                srv.kind(body)

    def test_every_scraped_card_offers_it_and_says_what_it_is_now(self):
        s = store()
        s.upsert(lab(1, "Oxidase"))
        s.upsert(item("manual:1", "Dentist", at(1), kind="event", course=""))
        page = report.render_board(report.build(s, Settings(), NOW), Settings(), "", NOW)
        self.assertEqual(page.count('class="act whatis needs-app"'), 1)
        self.assertIn('data-what="exam"', page)
        s.say_kind(s.get("moodle:cm:1"), "assignment")
        page = report.render_board(report.build(s, Settings(), NOW), Settings(), "", NOW)
        self.assertIn('data-what="assignment"', page)
        self.assertNotIn('<span class="kind">exam</span>', page)


if __name__ == "__main__":
    unittest.main()
