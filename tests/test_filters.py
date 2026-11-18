"""What the list shows and what it archives: keywords, copies of Moodle work, and the student's own say."""
from __future__ import annotations

import unittest

from helpers import at, item

import filters


def moodle(title="Experiment 15 Pre-lab", due=None, n=1):
    return item(f"moodle:cm:{n}", title, due or at(2), course="2026 Fall CHEM 1212 for A. Teacher")


def mail(title, due=None, n=1, **more):
    return item(f"outlook-mail:{n}", title, due or at(2), course="", source="outlook-mail", **more)


class Keywords(unittest.TestCase):
    def test_a_keyword_in_the_title_or_course_archives_it(self):
        shown, hidden = filters.split([moodle("Absence Documentation"), moodle("Lab report", n=2)], ["absence doc"])
        self.assertEqual([i.title for i in shown], ["Lab report"])
        self.assertIn("absence doc", hidden[0].reason)

    def test_blank_keywords_match_nothing(self):
        shown, hidden = filters.split([moodle()], ["", "   "])
        self.assertEqual((len(shown), len(hidden)), (1, 0))


class Copies(unittest.TestCase):
    def test_moodles_reminder_email_is_a_copy_of_the_moodle_item(self):
        m = moodle("Experiment 15 Pre-lab")
        e = mail("Moodle4 - [2026 Fall CHEM 1212] Due on Friday: Experiment 15 Pre-lab")
        shown, hidden = filters.split([m, e], [])
        self.assertEqual([i.id for i in shown], ["moodle:cm:1"])
        self.assertIn("duplicate of", hidden[0].reason)

    def test_the_same_title_in_another_course_is_not_a_copy(self):
        m = moodle("Exam 1")
        e = mail("BE 2352 Exam 1 is this Friday")
        self.assertIsNone(filters.duplicate_of(e, [m]))

    def test_an_email_weeks_away_from_the_moodle_date_is_not_a_copy(self):
        m = moodle("Experiment 15 Pre-lab", due=at(2))
        e = mail("CHEM 1212 Experiment 15 Pre-lab", due=at(40))
        self.assertIsNone(filters.duplicate_of(e, [m]))

    def test_what_the_student_added_is_never_a_copy(self):
        m = moodle("Experiment 15 Pre-lab")
        mine = item("manual:1", "Experiment 15 Pre-lab", at(2), course="CHEM 1212")
        self.assertIsNone(filters.duplicate_of(mine, [m]))

    def test_gradescope_copy_needs_the_same_course_title_and_about_the_same_day(self):
        m = moodle("HW 3", due=at(2))
        same = item("gradescope:1", "HW3", at(2), course="CHEM 1212")
        other_course = item("gradescope:2", "HW3", at(2), course="MATH 1550")
        other_week = item("gradescope:3", "HW3", at(9), course="CHEM 1212")
        self.assertTrue(filters.same_assignment(same, m))
        self.assertFalse(filters.same_assignment(other_course, m))
        self.assertFalse(filters.same_assignment(other_week, m))
        self.assertIs(filters.duplicate_of(same, [m]), m)

    def test_copies_are_judged_against_everything_stored_not_just_what_is_listed(self):
        m = moodle("Experiment 15 Pre-lab")
        e = mail("Due on Friday: CHEM 1212 Experiment 15 Pre-lab")
        shown, hidden = filters.split([e], [], pool=[m, e])
        self.assertEqual((len(shown), len(hidden)), (0, 1))


class TheStudentsSay(unittest.TestCase):
    def test_their_own_archive_and_show_beat_both_rules(self):
        m, quiet = moodle("Experiment 15 Pre-lab"), moodle("Absence Documentation", n=2)
        shown, hidden = filters.split([m, quiet], ["absence"], placement={m.id: "archived", quiet.id: "shown"})
        self.assertEqual([i.id for i in shown], [quiet.id])
        self.assertEqual(hidden[0].reason, "you archived it")


if __name__ == "__main__":
    unittest.main()
