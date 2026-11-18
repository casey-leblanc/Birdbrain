"""No header: the list is the page. A status dot and a menu sit in the corner, and tags say the rest."""
from __future__ import annotations

import unittest

from helpers import NOW, at, item, store

import prefs
import report
from config import Settings


def board(status="Updated 10:32 AM.", progress=None, *items):
    s = store()
    for i in items or (item(),):
        s.upsert(i)
    return report.render_board(report.build(s, Settings(), NOW), Settings(), status, NOW, progress=progress)


class StatusDot(unittest.TestCase):
    def test_what_the_dot_shows(self):
        state = report.status_state
        self.assertEqual(state("Updated 10:32 AM."), "idle")
        self.assertEqual(state("Updated 10:32 AM.", scanning=True), "scanning")
        self.assertEqual(state("Updated 10:32 AM. Moodle needs sign-in."), "problem")
        self.assertEqual(state("Last scan failed (see log)"), "problem")
        self.assertEqual(state("Updated 10:32 AM. Couldn't reach Outlook."), "problem")
        self.assertEqual(state("The update didn't go in: Couldn't reach GitHub."), "problem")
        self.assertEqual(state("Not scanned yet"), "note")
        self.assertEqual(state("Back from sleep. Scanning as soon as the network is up…"), "note")
        self.assertEqual(state("Updated 10:32 AM. Waiting for you to sign in to Moodle."), "note")

    def test_the_dot_carries_the_status_words_and_scans_when_clicked(self):
        page = board("Updated 10:32 AM. Moodle needs sign-in.")
        self.assertIn('<button id="status-dot" class="status problem"', page)
        self.assertIn('<span class="st">Updated 10:32 AM. Moodle needs sign-in.</span>', page)
        self.assertIn('title="Scan now (R)"', page)

    def test_while_scanning_it_says_what_it_is_reading(self):
        page = board(progress={"text": "Scanning Moodle: CHEM 1212 (course 3 of 8)", "value": .4})
        self.assertIn('class="status scanning"', page)
        self.assertIn("Scanning Moodle: CHEM 1212 (course 3 of 8)", page)
        self.assertIn('role="progressbar"', page)


class NoHeader(unittest.TestCase):
    def test_the_header_and_the_next_exam_strip_are_gone(self):
        page = board()
        for gone in ('class="top"', 'class="today"', 'class="counts"', 'class="next"', 'class="nx', 'id="scan-top"',
                     'id="open-add"', 'id="open-settings"', "Next exam", "Next quiz", "Start here"):
            self.assertNotIn(gone, page)
        self.assertIn('<h1 class="sr">Birdbrain</h1>', page)   # the page still has a name for screen readers

    def test_the_list_comes_straight_after_the_corner_tools(self):
        page = board()
        tools, bands = page.index('class="tools needs-app"'), page.index('<main class="bands">')
        self.assertLess(tools, bands)
        between = page[page.index("</div>", page.index('id="app-menu"')) + 12:bands]
        self.assertEqual(between, "")

    def test_one_menu_holds_everything_else(self):
        page = board()
        menu = page[page.index('id="app-menu"'):page.index('<main class="bands">')]
        want = ["Quick write", "Add item", "Settings", "Scan now", "Check for updates", "Quit Birdbrain"]
        self.assertEqual([w for w in want if w in menu], want)
        self.assertEqual(menu.count('role="menuitem"'), len(want))

    def test_both_layouts_carry_the_corner_styles_and_none_of_the_headers(self):
        s = store()
        s.upsert(item())
        for layout in ("glass", "focus"):
            p = {**prefs.DEFAULTS, "layout": layout}
            page = report.render(report.build(s, Settings(), NOW), Settings(), "Updated 10:32 AM.", NOW, "tok", prefs=p)
            style = page[:page.index("</head>")]
            with self.subTest(layout=layout):
                self.assertIn(".tools{position:absolute", style)
                self.assertIn("--tools-top", style)
                for gone in (".counts{", ".today{", ".nx{", ".top{"):
                    self.assertNotIn(gone, style)


class Tags(unittest.TestCase):
    def test_an_exam_further_off_says_how_far(self):
        page = board("Updated 10:32 AM.", None,
                     item("moodle:cal:1", "Exam 2", at(5, 9, 30), kind="test"),
                     item("moodle:cm:2", "Chapter 7 Quiz", at(1, 17, 0), kind="test", level="quiz"),
                     item("moodle:cm:3", "Essay 2", at(5)))
        self.assertEqual(page.count('<span class="in">'), 1)   # not for tomorrow's quiz, not for homework
        self.assertIn('<span class="kind">exam</span><span class="in">in 5 days</span>', page)


if __name__ == "__main__":
    unittest.main()
