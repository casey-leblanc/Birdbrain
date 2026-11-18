"""Quick write's reader: one typed line becomes a title, a day, and whatever else was said. A table of phrases
against a fixed now (Wednesday, November 18, 2026, 10:00)."""
from __future__ import annotations

import unittest
from datetime import date, time

import helpers  # noqa: F401  (sets the data folder and the import path)
from helpers import NOW

import quickwrite

COURSES = ["CHEM 1202", "MATH 1550", "ENGL 2000", "BIOL 1201", "BIOL 1208"]
LABELS = {"life": "Life", "extracurricular": "Extracurricular", "appointment": "Appointment", "work": "Work"}
D = lambda m, d, y=2026: date(y, m, d)
T = time
WED, THU, FRI, SAT, MON, TUE = D(11, 18), D(11, 19), D(11, 20), D(11, 21), D(11, 23), D(11, 24)

# what was typed -> title, day, time, label, class, kind
TABLE = [
    ("chem lab report fri 5pm #life", "Chem lab report", FRI, T(17), "life", "", "assignment"),
    ("buy milk", "Buy milk", WED, None, "", "", "assignment"),
    # days
    ("call mom today", "Call mom", WED, None, "", "", "assignment"),
    ("laundry tmr", "Laundry", THU, None, "", "", "assignment"),
    ("laundry tmrw", "Laundry", THU, None, "", "", "assignment"),
    ("laundry tomorrow", "Laundry", THU, None, "", "", "assignment"),
    ("study group tonight", "Study group", WED, None, "", "", "assignment"),
    ("essay fri", "Essay", FRI, None, "", "", "assignment"),
    ("essay friday", "Essay", FRI, None, "", "", "assignment"),
    ("essay due fri", "Essay", FRI, None, "", "", "assignment"),
    ("essay by friday", "Essay", FRI, None, "", "", "assignment"),
    ("read ch 4 wed", "Read ch 4", WED, None, "", "", "assignment"),
    ("read ch 4 thu", "Read ch 4", THU, None, "", "", "assignment"),
    ("read ch 4 thurs", "Read ch 4", THU, None, "", "", "assignment"),
    ("gym mon", "Gym", MON, None, "", "", "assignment"),
    ("gym next mon", "Gym", MON, None, "", "", "assignment"),
    ("gym next fri", "Gym", D(11, 27), None, "", "", "assignment"),
    ("gym this fri", "Gym", FRI, None, "", "", "assignment"),
    ("project next week", "Project", D(11, 25), None, "", "", "assignment"),
    ("return book in 3 days", "Return book", SAT, None, "", "", "assignment"),
    ("pay rent in 2 weeks", "Pay rent", D(12, 2), None, "", "", "assignment"),
    ("renew pass in a week", "Renew pass", D(11, 25), None, "", "", "assignment"),
    ("dentist 11/21", "Dentist", SAT, None, "", "", "assignment"),
    ("dentist 11/21/27", "Dentist", D(11, 21, 2027), None, "", "", "assignment"),
    ("dentist 1/5", "Dentist", D(1, 5, 2027), None, "", "", "assignment"),          # already past this year
    ("dentist nov 21", "Dentist", SAT, None, "", "", "assignment"),
    ("dentist november 21st", "Dentist", SAT, None, "", "", "assignment"),
    ("dentist 21 nov", "Dentist", SAT, None, "", "", "assignment"),
    ("dentist on nov 21", "Dentist", SAT, None, "", "", "assignment"),
    ("taxes apr 15", "Taxes", D(4, 15, 2027), None, "", "", "assignment"),
    ("party dec 5", "Party", D(12, 5), None, "", "", "assignment"),
    ("may 5 concert", "Concert", D(5, 5, 2027), None, "", "", "assignment"),
    ("essay nov 18", "Essay", WED, None, "", "", "assignment"),                       # today is not past
    # times
    ("meeting 5pm", "Meeting", WED, T(17), "", "", "assignment"),
    ("meeting 5 pm", "Meeting", WED, T(17), "", "", "assignment"),
    ("meeting 5p", "Meeting", WED, T(17), "", "", "assignment"),
    ("meeting 5:30p", "Meeting", WED, T(17, 30), "", "", "assignment"),
    ("meeting 5:30pm", "Meeting", WED, T(17, 30), "", "", "assignment"),
    ("meeting 17:00", "Meeting", WED, T(17), "", "", "assignment"),
    ("meeting noon", "Meeting", WED, T(12), "", "", "assignment"),
    ("essay midnight", "Essay", WED, T(23, 59), "", "", "assignment"),
    ("essay 11:59", "Essay", WED, T(23, 59), "", "", "assignment"),
    ("essay 11:59pm", "Essay", WED, T(23, 59), "", "", "assignment"),
    ("class 9am", "Class", WED, T(9), "", "", "assignment"),
    ("class 12am", "Class", WED, T(0), "", "", "assignment"),
    ("class at 9", "Class", WED, T(9), "", "", "assignment"),
    ("dinner at 6", "Dinner", WED, T(18), "", "", "assignment"),
    ("dinner at 6:30", "Dinner", WED, T(18, 30), "", "", "assignment"),
    ("lunch at 12", "Lunch", WED, T(12), "", "", "assignment"),
    ("breakfast 7:30", "Breakfast", WED, T(7, 30), "", "", "assignment"),
    ("review 09:00", "Review", WED, T(9), "", "", "assignment"),
    ("call 3:15", "Call", WED, T(15, 15), "", "", "assignment"),
    ("nov 21 dentist at 3", "Dentist", SAT, T(15), "", "", "assignment"),
    # labels
    ("dentist tue 3pm #appointment", "Dentist", TUE, T(15), "appointment", "", "event"),
    ("dentist tue 3pm #app", "Dentist", TUE, T(15), "appointment", "", "event"),
    ("club meeting thu 6pm #extra", "Club meeting", THU, T(18), "extracurricular", "", "assignment"),
    ("shift sat 8am #work", "Shift", SAT, T(8), "work", "", "assignment"),
    ("groceries #life", "Groceries", WED, None, "life", "", "assignment"),
    ("groceries #LIFE", "Groceries", WED, None, "life", "", "assignment"),
    ("#life groceries", "Groceries", WED, None, "life", "", "assignment"),
    ("groceries #nothing", "Groceries #nothing", WED, None, "", "", "assignment"),      # no such label: left alone
    # classes
    ("problem set 9 @math fri", "Problem set 9", FRI, None, "", "MATH 1550", "assignment"),
    ("lab writeup @chem1202", "Lab writeup", WED, None, "", "CHEM 1202", "assignment"),
    ("lab writeup @1202", "Lab writeup", WED, None, "", "CHEM 1202", "assignment"),
    ("lab writeup @CHEM", "Lab writeup", WED, None, "", "CHEM 1202", "assignment"),
    ("notes @biol", "Notes @biol", WED, None, "", "", "assignment"),                    # two BIOL courses: not sure
    ("notes @biol1208", "Notes", WED, None, "", "BIOL 1208", "assignment"),
    ("notes @physics", "Notes @physics", WED, None, "", "", "assignment"),
    # types
    ("quiz ch 5 fri", "Quiz ch 5", FRI, None, "", "", "quiz"),
    ("exam 2 @math dec 9 9:30am", "Exam 2", D(12, 9), T(9, 30), "", "MATH 1550", "exam"),
    ("test 1 @chem mon", "Test 1", MON, None, "", "CHEM 1202", "exam"),
    ("midterm fri 10am", "Midterm", FRI, T(10), "", "", "exam"),
    ("event career fair thu 2pm", "Career fair", THU, T(14), "", "", "event"),
    ("final project draft fri", "Final project draft", FRI, None, "", "", "assignment"),
    ("midterm review session thu", "Midterm review session", THU, None, "", "", "assignment"),
    ("study for exam fri", "Study for exam", FRI, None, "", "", "assignment"),         # only a type word at the start
    # things that only look like dates and times stay in the title
    ("5k run sat", "5k run", SAT, None, "", "", "assignment"),
    ("read 30 pages", "Read 30 pages", WED, None, "", "", "assignment"),
    ("room 204 at 2", "Room 204", WED, T(14), "", "", "assignment"),
    ("call 555-1234 fri", "Call 555-1234", FRI, None, "", "", "assignment"),
    ("2/30 party", "2/30 party", WED, None, "", "", "assignment"),
    ("13pm nap", "13pm nap", WED, None, "", "", "assignment"),
    ("meet may at 5", "Meet may", WED, T(17), "", "", "assignment"),
    ("friend's birthday", "Friend's birthday", WED, None, "", "", "assignment"),
    ("sunscreen", "Sunscreen", WED, None, "", "", "assignment"),
    # the first day and the first time win
    ("essay fri sat", "Essay sat", FRI, None, "", "", "assignment"),
    ("essay 5pm 6pm", "Essay 6pm", WED, T(17), "", "", "assignment"),
    ("Email Dr. Smith, fri", "Email Dr. Smith", FRI, None, "", "", "assignment"),
    ("   ", "", WED, None, "", "", "assignment"),
]


class Table(unittest.TestCase):
    def test_there_are_plenty_of_phrases(self):
        self.assertGreaterEqual(len(TABLE), 60)

    def test_every_phrase(self):
        for typed, title, day, at, label, course, kind in TABLE:
            with self.subTest(typed=typed):
                got = quickwrite.read(typed, NOW, COURSES, LABELS)
                self.assertEqual((got.title, got.day, got.time, got.label, got.course, got.kind),
                                 (title, day, at, label, course, kind))


class Chips(unittest.TestCase):
    def test_each_thing_read_says_how_it_was_understood(self):
        typed = "chem lab report fri 5pm #life"
        got = quickwrite.read(typed, NOW, COURSES, LABELS)
        self.assertEqual([(c.what, c.text, c.says) for c in got.chips],
                         [("day", "fri", "Friday, Nov 20"), ("time", "5pm", "5:00 PM"), ("label", "#life", "Life")])
        self.assertEqual([typed[:c.end].split()[-1] for c in got.chips], ["fri", "5pm", "#life"])   # where each ends

    def test_no_day_typed_says_today(self):
        got = quickwrite.read("buy milk", NOW)
        self.assertEqual([(c.what, c.text, c.says) for c in got.chips], [("day", "", "Today")])

    def test_how_days_are_said(self):
        say = lambda typed: quickwrite.read(typed, NOW).chips[0].says
        self.assertEqual([say("x tmr"), say("x mon"), say("x 1/5"), say("x in 2 weeks")],
                         ["Tomorrow", "Monday, Nov 23", "Tuesday, Jan 5, 2027", "Wednesday, Dec 2"])

    def test_a_word_handed_back_is_kept_as_plain_text(self):
        got = quickwrite.read("friday night lights tmr", NOW, skip=["friday"])
        self.assertEqual((got.title, got.day), ("Friday night lights", date(2026, 11, 19)))
        got = quickwrite.read("order 5pm special", NOW, skip=["5pm"])
        self.assertEqual((got.title, got.time), ("Order 5pm special", None))
        got = quickwrite.read("quiz ch 5", NOW, skip=["quiz"])
        self.assertEqual(got.kind, "assignment")

    def test_due_is_the_end_of_the_day_when_no_time_was_said(self):
        self.assertEqual(quickwrite.read("essay fri", NOW).due.strftime("%Y-%m-%d %H:%M"), "2026-11-20 23:59")
        self.assertEqual(quickwrite.read("essay fri 5pm", NOW).due.strftime("%Y-%m-%d %H:%M"), "2026-11-20 17:00")

    def test_a_very_long_line_is_cut_not_choked_on(self):
        got = quickwrite.read("word " * 500 + "fri", NOW)
        self.assertLessEqual(len(got.title), 300)


if __name__ == "__main__":
    unittest.main()
