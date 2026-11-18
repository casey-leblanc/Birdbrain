"""What Birdbrain says without being asked: one short line, at the right moment, once."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from helpers import NOW, at, item, store

import notices
import prefs
from config import Settings

CHEM = "2026 Fall CHEM 1212 for A. Teacher"
MATH = "2026 Fall MATH 1550 for B. Teacher"


def clock(hour: int, minute: int = 0, day: int = 0) -> datetime:
    return (NOW + timedelta(days=day)).replace(hour=hour, minute=minute, second=0, microsecond=0)


class Names(unittest.TestCase):
    def test_a_short_name_leads_with_the_class(self):
        self.assertEqual(notices.short(item("a", "Exp 15 Quiz (closes Friday)", at(0), course=CHEM)), "Chem Exp 15 Quiz")
        self.assertEqual(notices.short(item("a", "CHEM 1212 - Pre-lab 8", at(0), course=CHEM)), "Chem Pre-lab 8")
        self.assertEqual(notices.short(item("a", "Chem Lab 8 report", at(0), course=CHEM)), "Chem Lab 8 report")
        self.assertEqual(notices.short(item("a", "Dentist", at(0), course="")), "Dentist")

    def test_a_nickname_is_used_when_the_class_has_one(self):
        nick = {"CHEM 1212": {"nick": "Orgo"}}
        self.assertEqual(notices.short(item("a", "Exp 15 Quiz", at(0), course=CHEM), nick), "Orgo Exp 15 Quiz")

    def test_a_long_title_is_cut_at_a_word(self):
        name = notices.short(item("a", "Reading response on the causes of the French Revolution", at(0)))
        self.assertLessEqual(len(name), notices.NAME + 1)
        self.assertTrue(name.endswith("…"))
        self.assertNotIn("  ", name)

    def test_the_line_takes_what_fits_and_counts_the_rest(self):
        items = [item(str(n), f"Problem set number {n}", at(0), course=CHEM) for n in range(1, 9)]
        line = notices.names(items)
        self.assertLessEqual(len(line), notices.LINE)
        self.assertTrue(line.startswith("Chem Problem set number 1, Chem Problem set number 2"))
        self.assertRegex(line, r" and \d more$")
        said = line.count("Chem Problem set")
        self.assertEqual(int(line.rsplit(" ", 2)[1]), 8 - said)
        self.assertEqual(notices.names(items[:2]), "Chem Problem set number 1, Chem Problem set number 2")


class Lists(unittest.TestCase):
    def setUp(self):
        self.s, self.settings = store(), Settings()
        self.n = notices.Notices(self.s, self.settings)

    def add(self, *items):
        for i in items:
            self.s.upsert(i)

    def test_the_morning_list_is_one_line_and_said_once(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"),
                 item("moodle:cm:2", "Pre-lab", clock(23, 59), course=CHEM, kind="assignment"),
                 item("moodle:cm:3", "Essay", clock(23, 59, day=2), kind="assignment"))
        self.assertEqual(self.n.due(clock(7, 29)), [])                          # not yet
        got = self.n.due(clock(7, 30))
        self.assertEqual([g.line for g in got], ["Today: Chem Exp 15 Quiz, Chem Pre-lab"])
        self.assertEqual(got[0].ids, ["moodle:cm:1", "moodle:cm:2"])
        self.assertEqual(self.n.due(clock(7, 31)), [])                          # once
        self.assertEqual(self.n.due(clock(12)), [])

    def test_overdue_work_is_counted_not_listed_when_there_is_work_today(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"),
                 item("moodle:cm:9", "Essay 2 draft", clock(23, 59, day=-1), kind="assignment"))
        self.assertEqual(self.n.due(clock(7, 30))[0].line, "Today: Chem Exp 15 Quiz. 1 overdue")

    def test_nothing_due_nothing_said(self):
        self.add(item("moodle:cm:3", "Essay", clock(23, 59, day=4), kind="assignment"))
        self.assertEqual(self.n.due(clock(7, 30)), [])
        self.assertEqual(self.n.due(clock(19, 0)), [])

    def test_ticked_and_archived_cards_are_left_out(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"),
                 item("moodle:cm:2", "Pre-lab", clock(23, 59), course=CHEM, kind="assignment"),
                 item("moodle:cm:4", "Worksheet", clock(23, 59), course=CHEM, kind="assignment"))
        self.s.set_done("moodle:cm:1", True)
        self.s.set_placement("moodle:cm:4", "archived")
        self.assertEqual(self.n.due(clock(7, 30))[0].line, "Today: Chem Pre-lab")

    def test_the_evening_check_reaches_into_tomorrow_morning(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(23, 59), course=CHEM, kind="assignment"),
                 item("moodle:cm:2", "Pre-lab", clock(7, 0, day=1), course=CHEM, kind="assignment"),
                 item("moodle:cm:3", "Essay", clock(17, 0, day=1), kind="assignment"),
                 item("moodle:cm:5", "Done already", clock(15, 0), kind="assignment"))   # past by the evening
        self.n.due(clock(7, 30))
        got = self.n.due(clock(19, 0))
        self.assertEqual([g.line for g in got], ["Due tonight: Chem Exp 15 Quiz, Chem Pre-lab"])

    def test_a_list_missed_while_the_pc_was_off_still_comes_but_not_hours_late(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"))
        self.assertEqual(len(self.n.due(clock(9, 15))), 1)                      # woke at 9:15: still this morning
        other = notices.Notices(store(), self.settings)
        other.store.upsert(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"))
        self.assertEqual(other.due(clock(14, 0)), [])                           # 2 PM is no time for a morning list
        self.assertEqual(other.due(clock(14, 1)), [])

    def test_the_times_can_be_changed_or_turned_off(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(23, 59), course=CHEM, kind="assignment"))
        self.settings.morning_list, self.settings.evening_list = "", "21:15"
        self.assertEqual(self.n.due(clock(8, 0)), [])
        self.assertEqual(self.n.due(clock(19, 0)), [])
        self.assertEqual(len(self.n.due(clock(21, 15))), 1)

    def test_notifications_off_says_nothing(self):
        self.add(item("moodle:cm:1", "Exp 15 Quiz", clock(17), course=CHEM, kind="assignment"))
        self.settings.notify = False
        self.assertEqual(self.n.due(clock(7, 30)), [])
        self.assertIsNone(self.n.new_work([item("x", "New thing", clock(17))], clock(8)))


class BeforeATest(unittest.TestCase):
    def setUp(self):
        self.s, self.settings = store(), Settings(morning_list="", evening_list="")
        self.n = notices.Notices(self.s, self.settings)

    def test_an_exam_is_said_the_day_before_once(self):
        self.s.upsert(item("moodle:cal:4", "Exam 2", clock(9, 30, day=2), course=MATH, kind="test"))
        self.assertEqual(self.n.due(clock(9, 0, day=1)), [])                    # more than a day off
        got = self.n.due(clock(9, 30, day=1))
        self.assertEqual([g.line for g in got], ["Exam tomorrow at 9:30 AM: Math Exam 2"])
        self.assertEqual(got[0].ids, ["moodle:cal:4"])
        self.assertEqual(self.n.due(clock(9, 31, day=1)), [])
        self.assertEqual(self.n.due(clock(8, 0, day=2)), [])

    def test_an_exam_first_seen_on_the_day_says_today(self):
        self.s.upsert(item("moodle:cal:4", "Exam 2", clock(15, 0), course=MATH, kind="test"))
        self.assertEqual(self.n.due(clock(10, 0))[0].line, "Exam today at 3 PM: Math Exam 2")

    def test_a_quiz_is_said_three_hours_before_it_closes(self):
        self.s.upsert(item("moodle:cm:5", "Chapter 7 Quiz", clock(17, 0), course=MATH, kind="test", level="quiz"))
        self.assertEqual(self.n.due(clock(13, 59)), [])
        self.assertEqual(self.n.due(clock(14, 0))[0].line, "Quiz closes in 3 hours (5 PM): Math Chapter 7 Quiz")
        self.assertEqual(self.n.due(clock(15, 0)), [])

    def test_a_test_that_moves_is_said_again(self):
        self.s.upsert(item("moodle:cal:4", "Exam 2", clock(9, 30, day=1), course=MATH, kind="test"))
        self.assertEqual(len(self.n.due(clock(10, 0))), 1)
        self.s.upsert(item("moodle:cal:4", "Exam 2", clock(14, 0, day=1), course=MATH, kind="test"))
        self.assertEqual(self.n.due(clock(14, 30))[0].line, "Exam tomorrow at 2 PM: Math Exam 2")

    def test_a_ticked_test_and_the_switch_being_off_say_nothing(self):
        self.s.upsert(item("moodle:cal:4", "Exam 2", clock(9, 30, day=1), course=MATH, kind="test"))
        self.settings.test_reminders = False
        self.assertEqual(self.n.due(clock(10, 0)), [])
        self.settings.test_reminders = True
        self.s.set_done("moodle:cal:4", True)
        self.assertEqual(self.n.due(clock(10, 0)), [])


class NewWork(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.n = notices.Notices(self.s, Settings())

    def test_one_new_thing_says_when(self):
        got = self.n.new_work([item("a", "Lab 8 report", clock(23, 59, day=1), course=CHEM)], NOW)
        self.assertEqual(got.line, f"New: Chem Lab 8 report ({clock(0, 0, day=1):%b} {clock(0, 0, day=1).day}, 11:59 PM)")

    def test_several_come_as_one_line(self):
        new = [item(str(n), f"Homework {n}", clock(23, 59, day=n), course=CHEM) for n in range(1, 6)]
        got = self.n.new_work(new, NOW)
        self.assertEqual(got.title, "5 new")
        self.assertLessEqual(len(got.line), notices.LINE + 8)
        self.assertEqual(got.ids[0], "1")

    def test_a_sample_is_always_something(self):
        self.assertIn("what a notification looks like", self.n.sample(NOW).text)
        self.s.upsert(item("moodle:cm:1", "Exp 15 Quiz", clock(23, 59), course=CHEM, kind="assignment"))
        self.assertEqual(self.n.sample(clock(12)).line, "Due tonight: Chem Exp 15 Quiz")

    def test_nicknames_come_from_the_students_own(self):
        prefs.update(self.s, {"courses": {"CHEM 1212": {"nick": "Orgo"}}})
        got = self.n.new_work([item("a", "Lab 8 report", clock(23, 59, day=1), course=CHEM)], NOW)
        self.assertTrue(got.text.startswith("Orgo Lab 8 report"))


if __name__ == "__main__":
    unittest.main()
