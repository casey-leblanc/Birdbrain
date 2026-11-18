"""What Birdbrain says about itself: not LSU's, no AI, and where your data stays. In the app and in both READMEs."""
from __future__ import annotations

import unittest
from pathlib import Path

from helpers import NOW, item, store

import prefs
import report
from config import Settings

ROOT = Path(__file__).resolve().parent.parent
SENTENCE = ("Birdbrain is a student project. It is not affiliated with, endorsed by or supported by "
            "Louisiana State University.")


def one_line(text: str) -> str:
    return " ".join(text.replace("> ", " ").replace("**", "").split())


class SaidPlainly(unittest.TestCase):
    def test_the_sentence_is_the_agreed_one(self):
        self.assertEqual(report.NOT_LSU, SENTENCE)

    def test_near_the_top_of_both_readmes(self):
        for name in ("README.md", "birdbrain/README.md"):
            with self.subTest(readme=name):
                text = one_line((ROOT / name).read_text(encoding="utf-8"))
                self.assertIn(SENTENCE, text)
                self.assertLess(text.index(SENTENCE), 900)

    def test_on_the_welcome_page(self):
        page = report.render_setup("tok", prefs.DEFAULTS)
        self.assertIn(SENTENCE, page)
        self.assertIn("Birdbrain never sees it", page)

    def test_in_settings_about(self):
        s = store()
        s.upsert(item())
        page = report.render(report.build(s, Settings(), NOW), Settings(), "", NOW, "tok")
        about = page[page.index('id="about-sec"'):]
        about = about[:about.index("<h3>Quit</h3>")]
        self.assertIn(SENTENCE, about)
        self.assertIn("stay on this computer", about)
        self.assertIn("There is no AI in Birdbrain", about)


class Readmes(unittest.TestCase):
    def test_they_are_for_students_and_say_where_data_stays(self):
        root = (ROOT / "README.md").read_text(encoding="utf-8")
        for words in ("## Get it", "## First run", "## Where your data stays", "On your computer",
                      "Your password is never seen by Birdbrain", "No AI", "Pre-release"):
            self.assertIn(words, root)

    def test_nothing_about_a_model_or_a_key_is_left(self):
        for name in ("README.md", "birdbrain/README.md"):
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            for word in ("jev", "typesafe", "api key", "api_key"):
                self.assertNotIn(word, text, name)

    def test_the_guide_matches_the_app(self):
        guide = (ROOT / "birdbrain" / "README.md").read_text(encoding="utf-8")
        for _, label, _ in report.MENU:           # every menu entry is explained
            self.assertIn(label.replace(" Birdbrain", ""), guide)
        for gone in ("next exam", "Scan now, Add item and Settings buttons", "counts of what's overdue"):
            self.assertNotIn(gone, guide)         # the header it used to describe is gone


if __name__ == "__main__":
    unittest.main()
