"""The list itself: which day group an item lands in, what its card says, and that the page renders in every look."""
from __future__ import annotations

import unittest
from datetime import timedelta

from helpers import NOW, at, item, store

import prefs
import report
from config import Settings


def board(*items, settings=None):
    s = store()
    for i in items:
        s.upsert(i)
    return report.build(s, settings or Settings(), NOW), s


def group(b, label):
    for c in b.columns:
        for g in c.groups:
            if g.label == label or g.label.startswith(label):
                return [i.title for i in g.items]
    raise AssertionError(f"no group {label!r} in {[g.label for c in b.columns for g in c.groups]}")


class DayGroups(unittest.TestCase):
    def test_each_item_lands_under_its_day(self):
        b, _ = board(
            item("moodle:cm:1", "Late lab", at(-1)),
            item("moodle:cm:2", "Tonight", at(0)),
            item("moodle:cm:3", "Tomorrow night", at(1)),
            item("moodle:cm:4", "Friday essay", at(2)),
            item("moodle:cm:5", "Far off project", at(12)),
        )
        self.assertEqual(group(b, "Overdue"), ["Late lab"])
        self.assertEqual(group(b, "Today"), ["Tonight"])
        self.assertEqual(group(b, "Tomorrow"), ["Tomorrow night"])
        self.assertEqual(group(b, "Friday"), ["Friday essay"])
        self.assertEqual(group(b, "From "), ["Far off project"])
        self.assertEqual((b.overdue, b.due_today, b.tomorrow), (1, 1, 1))

    def test_homework_due_earlier_today_is_overdue_but_a_past_exam_is_not(self):
        b, _ = board(item("moodle:cm:1", "Morning homework", at(0, 8, 0)),
                     item("moodle:cal:2", "Exam 2", at(0, 8, 0), kind="test"))
        self.assertEqual(group(b, "Overdue"), ["Morning homework"])
        self.assertEqual(group(b, "Today"), ["Exam 2"])

    def test_due_at_1159_pm_stays_on_its_own_day(self):
        b, _ = board(item("moodle:cm:1", "Due tonight at 11:59", at(0, 23, 59)),
                     item("moodle:cm:2", "Due at midnight", at(1, 0, 0)))
        self.assertEqual(group(b, "Today"), ["Due tonight at 11:59"])
        self.assertEqual(group(b, "Tomorrow"), ["Due at midnight"])

    def test_outside_the_window_is_left_out(self):
        s = Settings(overdue_days=14, lookahead_days=30)
        b, _ = board(item("moodle:cm:1", "Ancient", at(-20)), item("moodle:cm:2", "Next term", at(45)), settings=s)
        self.assertEqual(sum(c.count for c in b.columns), 0)

    def test_ticked_items_move_to_completed_newest_first(self):
        b, s = board(item("moodle:cm:1", "First done", at(1)), item("moodle:cm:2", "Second done", at(1)))
        s.set_done("moodle:cm:1", True)
        with s._db:   # ticked a while ago
            s._db.execute("UPDATE items SET done_at='2026-11-01T09:00:00' WHERE id='moodle:cm:1'")
        s.set_done("moodle:cm:2", True)
        b = report.build(s, Settings(), NOW)
        self.assertEqual([i.title for i in b.completed], ["Second done", "First done"])
        self.assertEqual(group(b, "Tomorrow"), [])

    def test_archived_and_copies_are_off_the_list(self):
        b, s = board(item("moodle:cm:1", "Experiment 15 Pre-lab", at(2), course="CHEM 1212"),
                     item("outlook-mail:1", "Due on Friday: CHEM 1212 Experiment 15 Pre-lab", at(2), course=""),
                     item("moodle:cm:3", "Reading quiz", at(2)))
        s.set_placement("moodle:cm:3", "archived")
        b = report.build(s, Settings(), NOW)
        self.assertEqual(group(b, "Friday"), ["Experiment 15 Pre-lab"])
        self.assertEqual(sorted(h.item.id for h in b.archived), ["moodle:cm:3", "outlook-mail:1"])


class Cards(unittest.TestCase):
    def test_course_code_comes_from_the_course_name(self):
        self.assertEqual(report.course_code(item(course="2026 Fall CHEM 1202 for A. Teacher")), "CHEM 1202")
        self.assertEqual(report.course_code(item("outlook-mail:1", "BE 2352: Exam 1 Friday", course="")), "BE 2352")
        self.assertEqual(report.course_code(item("outlook-mail:2", "Parking notice", course="")), "Email")
        self.assertEqual(report.course_code(item("manual:1", "Dentist", course="")), "Personal")

    def test_title_drops_what_the_course_tag_already_says(self):
        t = report.display_title(item("outlook-mail:1", "Moodle4 - [2026 Fall CE 2450 for B. Teacher] Homework 6 posted"))
        self.assertEqual(t, "Homework 6 posted")
        t = report.display_title(item("outlook-mail:2", "2026 Fall BE 2352 for B. Teacher: Lab moved to Thursday"))
        self.assertEqual(t, "Lab moved to Thursday")
        self.assertEqual(report.display_title(item("manual:1", "[my] own title")), "[my] own title")

    def test_which_items_have_a_time_worth_showing(self):
        self.assertTrue(report.has_time(item("moodle:cm:1", due=at(1, 23, 59))))            # Moodle's own time
        self.assertFalse(report.has_time(item("outlook-mail:1", due=at(1, 23, 59))))        # a date with no time
        self.assertTrue(report.has_time(item("outlook-calendar:1", due=at(1, 14, 30))))
        self.assertFalse(report.has_time(item("moodle:page:1", due=at(1, 14, 30))))         # read from page text
        self.assertFalse(report.has_time(item("gradescope:1", due=at(1, 14, 30), detail="time not stated")))

    def test_exam_or_quiz(self):
        test = lambda title, **m: report.test_level(item("moodle:cal:1", title, kind="test", **m))
        self.assertEqual(test("Exam 2"), "exam")
        self.assertEqual(test("Midterm"), "exam")
        self.assertEqual(test("Chapter 7 Quiz"), "quiz")
        self.assertEqual(test("Unit check", level="quiz"), "quiz")
        self.assertIsNone(report.test_level(item(title="Quiz corrections", kind="assignment")))

    def test_how_pressing(self):
        u = lambda due, kind="assignment": report.urgency(item(due=due, kind=kind), NOW)
        self.assertEqual([u(at(-1)), u(at(0)), u(at(1)), u(at(3)), u(at(6))],
                         ["overdue", "today", "tomorrow", "soon", ""])
        self.assertEqual(u(at(-1), "test"), "")   # a past exam is over, not late


class Page(unittest.TestCase):
    ITEMS = (item("moodle:cm:1", "Late lab <b>report</b>", at(-1)),
             item("moodle:cal:2", "Exam 2", at(2, 9, 30), kind="test"),
             item("manual:3", "Dentist", at(1, 15, 0), kind="event", course=""))

    def test_every_look_renders_with_every_item_and_escapes_titles(self):
        b, s = board(*self.ITEMS)
        for layout, themes in (("glass", prefs.GLASS_THEMES), ("focus", prefs.FOCUS_THEMES)):
            for theme in themes:
                for mode in ("light", "dark"):
                    p = {**prefs.DEFAULTS, "layout": layout, "mode": mode,
                         ("theme" if layout == "glass" else "focus_theme"): theme}
                    page = report.render(b, Settings(), "Updated 10:00 AM.", NOW, "tok", s.version, p)
                    with self.subTest(layout=layout, theme=theme, mode=mode):
                        for title in ("Late lab &lt;b&gt;report&lt;/b&gt;", "Exam 2", "Dentist"):
                            self.assertIn(title, page)
                        self.assertNotIn("<b>report</b>", page)
                        self.assertIn(f'data-layout="{layout}"', page)
                        self.assertIn(f'data-theme="{theme}"', page)

    def test_the_board_alone_is_what_a_live_page_swaps_in(self):
        b, s = board(*self.ITEMS)
        part = report.render_board(b, Settings(), "Updated.", NOW, s.version, prefs.DEFAULTS)
        self.assertIn("Exam 2", part)
        self.assertNotIn("<html", part)

    def test_first_run_page_renders(self):
        self.assertIn("setup-form", report.render_setup("tok", prefs.DEFAULTS))


class Scripts(unittest.TestCase):
    """A slip in the page's script leaves a list that draws but does nothing, so the scripts must at least parse."""

    def test_the_pages_scripts_parse(self):
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path
        node = shutil.which("node")
        if not node:
            self.skipTest("node isn't installed here")
        for name in ("JS", "CHROME_JS", "SETUP_JS", "QUICK_PAGE_JS"):
            with self.subTest(script=name):
                path = Path(tempfile.mkdtemp()) / f"{name}.js"
                path.write_text(getattr(report, name), encoding="utf-8")
                got = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
                self.assertEqual(got.returncode, 0, got.stderr[-600:])

    def test_no_function_in_a_page_script_is_declared_twice(self):
        """A second `function name(){}` silently replaces the first, wherever in the script each one is."""
        import re
        from collections import Counter
        for name in ("JS", "CHROME_JS", "SETUP_JS", "QUICK_PAGE_JS"):
            with self.subTest(script=name):
                names = Counter(re.findall(r"(?m)^function (\w+)\(", getattr(report, name)))
                self.assertEqual([n for n, c in names.items() if c > 1], [])


if __name__ == "__main__":
    unittest.main()
