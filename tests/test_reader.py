"""The plain rules that read titles and text: what kind of thing it is, and when. No AI anywhere."""
from __future__ import annotations

import re
import unittest
from datetime import date
from pathlib import Path

import helpers  # noqa: F401  (sets the data folder and the import path)

import reader

WED = date(2026, 11, 18)   # a Wednesday


class Kinds(unittest.TestCase):
    def test_a_lab_with_test_in_its_name_is_an_assignment_not_an_exam(self):
        labs = ["Biochemical Testing - Oxidase Test", "Biochemical Testing - Catalase Test",
                "Biochemical Testing – Urease Test", "Lab 7: Flame Test", "Experiment 12 Benedict's Test Pre-lab",
                "Virtual Lab: Starch Hydrolysis Test", "Homework 4 - Hypothesis Test"]
        for title in labs:
            for module in ("quiz", "assign", "lti", ""):
                with self.subTest(title=title, module=module):
                    self.assertIsNone(reader.level(title))
                    self.assertEqual(reader.kind_of(title, module), "assignment")

    def test_exams_named_plainly_are_exams(self):
        for title in ["Exam 2", "Midterm", "Mid-term Exam", "Final", "Final Exam", "Finals", "Unit 3 Test", "Test 1",
                      "Chapter 5 Test", "Lab Exam 2", "CHEM 1202 Examination"]:
            with self.subTest(title=title):
                self.assertEqual(reader.level(title), "exam")
                self.assertEqual(reader.kind_of(title, "quiz"), "test")
                self.assertEqual(reader.moodle_level(title, "quiz", "test"), "exam")

    def test_quizzes(self):
        for title in ["Quiz 4", "Chapter 7 Quiz", "Reading quizzes", "Exp 15 Quiz"]:
            with self.subTest(title=title):
                self.assertEqual(reader.level(title), "quiz")
                self.assertEqual(reader.kind_of(title), "test")

    def test_work_about_a_test_is_not_the_test(self):
        for title in ["Exam 2 Review", "Practice Exam", "Quiz corrections", "Exam 1 Study Guide", "Final Project",
                      "Final draft of essay 3", "Final Paper", "Midterm reflection", "Test corrections"]:
            with self.subTest(title=title):
                self.assertIsNone(reader.level(title))
                self.assertEqual(reader.kind_of(title, "assign"), "assignment")

    def test_moodles_quiz_activity_is_a_quiz_unless_the_title_says_otherwise(self):
        self.assertEqual(reader.kind_of("Chapter 3", "quiz"), "test")
        self.assertEqual(reader.moodle_level("Chapter 3", "quiz", "test"), "quiz")
        self.assertEqual(reader.kind_of("Chapter 3 Homework", "quiz"), "assignment")
        self.assertEqual(reader.kind_of("Syllabus check-in assignment", "quiz"), "assignment")
        self.assertEqual(reader.moodle_level("Essay", "assign", "assignment"), "")

    def test_calendar_entries_are_events_unless_they_name_an_assessment(self):
        self.assertEqual(reader.kind_of("Study group", "calendar"), "event")
        self.assertEqual(reader.kind_of("BIOL 1201 Exam 3", "calendar"), "test")
        self.assertEqual(reader.kind_of("Exam 3 review session", "calendar"), "event")

    def test_a_hand_in_activity_is_homework_even_when_named_after_a_quiz(self):
        self.assertEqual(reader.kind_of("Quiz 2 upload", "assign"), "assignment")
        self.assertEqual(reader.kind_of("Take-home Exam", "assign"), "test")


class Dates(unittest.TestCase):
    def day(self, text, today=WED):
        return reader.find_date(text, today)

    def test_a_month_and_a_day_is_stated_outright(self):
        self.assertEqual(self.day("Homework 6 is due November 20 at 11:59 PM"), (date(2026, 11, 20), True))
        self.assertEqual(self.day("due Nov. 20th, 2026"), (date(2026, 11, 20), True))
        self.assertEqual(self.day("on the 3rd of December"), (date(2026, 12, 3), True))
        self.assertEqual(self.day("Exam: Dec 9"), (date(2026, 12, 9), True))

    def test_january_read_in_november_is_next_year(self):
        self.assertEqual(self.day("Project due January 12"), (date(2027, 1, 12), True))
        self.assertEqual(self.day("was due November 2"), (date(2026, 11, 2), True))   # recent past stays

    def test_numbers_and_weekdays_need_a_word_that_says_a_date_is_coming(self):
        self.assertEqual(self.day("Lab report due 11/24"), (date(2026, 11, 24), True))
        self.assertEqual(self.day("closes on 12/1/26"), (date(2026, 12, 1), True))
        self.assertEqual(self.day("A. Teacher Wed 11/18 Homework posted"), (None, False))   # the day it arrived
        self.assertEqual(self.day("due Friday"), (date(2026, 11, 20), False))
        self.assertEqual(self.day("Quiz next Tuesday"), (date(2026, 11, 24), False))
        self.assertEqual(self.day("by Wednesday"), (date(2026, 11, 18), False))
        self.assertEqual(self.day("Friday office hours as usual"), (None, False))

    def test_relative_days(self):
        self.assertEqual(self.day("due tomorrow"), (date(2026, 11, 19), False))
        self.assertEqual(self.day("due tonight at midnight"), (date(2026, 11, 18), False))
        self.assertEqual(self.day("the day after tomorrow"), (date(2026, 11, 20), False))

    def test_impossible_dates_are_not_dates(self):
        self.assertEqual(self.day("due February 30"), (None, False))
        self.assertEqual(self.day("nothing here"), (None, False))


class Text(unittest.TestCase):
    def test_an_email_about_homework(self):
        j = reader.judge("A. Teacher\nHomework 6 posted\nHomework 6 is due November 20 at 11:59 PM.", today=WED)
        self.assertEqual((j.kind, j.due, j.needs_review), ("assignment", date(2026, 11, 20), False))
        self.assertTrue(reader.is_actionable(j))

    def test_relative_days_count_from_when_the_email_was_sent_and_ask_to_be_checked(self):
        j = reader.judge("Reminder: Exam 2 is tomorrow in Williams 103", today=WED, sent=date(2026, 11, 16))
        self.assertEqual((j.kind, j.due, j.needs_review), ("test", date(2026, 11, 17), True))

    def test_receipts_and_news_are_not_things_to_do(self):
        for text in ["Successfully submitted to HW3 on November 20", "Your submission has been graded",
                     "Grades for Exam 2 have been released", "Campus dining hours for November 26"]:
            with self.subTest(text=text):
                self.assertFalse(reader.is_actionable(reader.judge(text, today=WED)))

    def test_an_email_about_a_lab_test_is_not_an_exam(self):
        j = reader.judge("Lab 9 Oxidase Test worksheet due November 21", today=WED)
        self.assertEqual(j.kind, "assignment")


class NoAI(unittest.TestCase):
    def test_nothing_in_the_app_mentions_a_model_or_a_key(self):
        root = Path(__file__).resolve().parent.parent
        files = [*root.glob("birdbrain/*.py"), root / "birdbrain" / "requirements.txt", root / "build.py"]
        words = re.compile(r"\b(jev|typesafe|anthropic|openai|llm|gpt)\b|api[_ ]key\b")
        found = [f"{f.name}: {m.group(0)}" for f in files
                 if (m := words.search(f.read_text(encoding="utf-8").lower()))]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
