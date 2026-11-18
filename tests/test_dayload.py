"""A day's load in a few words, and one early word about a heavy day."""
from __future__ import annotations

import unittest
from datetime import timedelta

from helpers import NOW, item, store

import dayload
import notices
import report
from config import Settings

CHEM = "2026 Fall CHEM 1212 for A. Teacher"


def due(n, hour=23, minute=59):
    return (NOW + timedelta(days=n)).replace(hour=hour, minute=minute)


def page(s, now=NOW):
    return report.render_board(report.build(s, Settings(), now), Settings(), "", now, s.version, {})


class Words(unittest.TestCase):
    def test_a_few_words(self):
        day = [item("a", "Lab report", due(2)), item("b", "Problem set", due(2)), item("c", "Reading", due(2)),
               item("d", "Exam 2", due(2, 9, 30), kind="test")]
        self.assertEqual(dayload.words(day, report.test_level), "3 due · 1 exam")
        self.assertTrue(dayload.heavy(day, report.test_level))
        two = [item("a", "Quiz 4", due(2), kind="test", level="quiz"), item("b", "Quiz 5", due(2), kind="test", level="quiz")]
        self.assertEqual(dayload.words(two, report.test_level), "2 quizzes")
        self.assertFalse(dayload.heavy(two, report.test_level))
        self.assertEqual(dayload.words(day[:1], report.test_level), "")        # one card says it all itself
        mixed = [item("a", "Essay", due(2)), item("e", "Career fair", due(2, 14, 0), kind="event")]
        self.assertEqual(dayload.words(mixed, report.test_level), "1 due · 1 event")

    def test_two_exams_make_a_heavy_day_and_events_dont(self):
        exams = [item("a", "Exam 1", due(2), kind="test"), item("b", "Final", due(2), kind="test")]
        self.assertTrue(dayload.heavy(exams, report.test_level))
        events = [item(str(n), f"Meeting {n}", due(2), kind="event") for n in range(6)]
        self.assertFalse(dayload.heavy(events, report.test_level))


class OnThePage(unittest.TestCase):
    def test_each_day_says_its_load_beside_its_name(self):
        s = store()
        for n, title in enumerate(("Lab report", "Problem set", "Reading", "Worksheet")):
            s.upsert(item(f"moodle:cm:{n}", title, due(2), course=CHEM))
        s.upsert(item("moodle:cm:9", "Essay", due(4), course=CHEM))
        html = page(s)
        friday = html[html.index(">Friday, Nov 20</h3>") - 200:html.index(">Friday, Nov 20</h3>")]
        self.assertIn('data-load="4 due"', friday)
        self.assertIn("heavy", friday)
        self.assertIn(">Friday, Nov 20</h3>", html)                             # the name itself is untouched
        sunday = html[html.index(">Sunday, Nov 22</h3>") - 200:html.index(">Sunday, Nov 22</h3>")]
        self.assertNotIn("data-load", sunday)                                   # one card: nothing to add

    def test_today_is_never_called_heavy_it_is_just_today(self):
        s = store()
        for n in range(5):
            s.upsert(item(f"moodle:cm:{n}", f"Homework {n}", due(0), course=CHEM))
        html = page(s)
        today = html[html.index(">Today</h3>") - 200:html.index(">Today</h3>")]
        self.assertIn('data-load="5 due"', today)
        self.assertNotIn("heavy", today)


class CalledOutOnceEarly(unittest.TestCase):
    def setUp(self):
        self.s, self.settings = store(), Settings(evening_list="", test_reminders=False)
        self.n = notices.Notices(self.s, self.settings)
        for k, title in enumerate(("Lab report", "Problem set", "Reading")):
            self.s.upsert(item(f"moodle:cm:{k}", title, due(3), course=CHEM))
        self.s.upsert(item("moodle:cal:4", "Exam 2", due(3, 9, 30), course=CHEM, kind="test"))

    def heavy(self, now):
        return [x.line for x in self.n.due(now) if x.key.startswith("heavy")]

    def test_three_days_ahead_with_the_morning_list_and_only_once(self):
        self.assertEqual(self.heavy(NOW.replace(hour=7, minute=0)), [])         # before the morning list's time
        self.assertEqual(self.heavy(NOW.replace(hour=7, minute=30)), ["Saturday is heavy: 3 due · 1 exam"])
        self.assertEqual(self.heavy(NOW.replace(hour=9)), [])
        self.assertEqual(self.heavy(NOW.replace(hour=8) + timedelta(days=1)), [])   # two days ahead now: already said

    def test_a_day_that_turns_heavy_two_days_out_is_still_said(self):
        s = store()
        n = notices.Notices(s, self.settings)
        for k in range(4):
            s.upsert(item(f"moodle:cm:{k}", f"Homework {k}", due(2), course=CHEM))
        self.assertEqual([x.title for x in n.due(NOW.replace(hour=8))], ["Friday is heavy"])

    def test_tomorrow_is_too_late_to_be_early_and_light_days_say_nothing(self):
        s = store()
        n = notices.Notices(s, self.settings)
        for k in range(5):
            s.upsert(item(f"moodle:cm:{k}", f"Homework {k}", due(1), course=CHEM))
        s.upsert(item("moodle:cm:9", "Essay", due(3), course=CHEM))
        self.assertEqual([x for x in n.due(NOW.replace(hour=8)) if x.key.startswith("heavy")], [])

    def test_no_morning_list_no_call(self):
        self.settings.morning_list = ""
        self.assertEqual(self.heavy(NOW.replace(hour=12)), [])


if __name__ == "__main__":
    unittest.main()
