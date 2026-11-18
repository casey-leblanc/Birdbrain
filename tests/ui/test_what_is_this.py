"""The details sheet: everything about a card. Yours can be changed; one from your sites is locked, except what it
is, and one answer about what it is fixes the whole series."""
from __future__ import annotations

import unittest

from page import PageTest


class Details(PageTest):
    def setUp(self):
        super().setUp()
        self.sheet = self.page.locator("#add-item")
        self.field = lambda name: self.page.locator(f"#add-form [name={name}]").first

    def test_saying_a_lab_is_an_assignment_fixes_the_series(self):
        lab = self.row("Oxidase Test")
        self.assertEqual(lab.locator("span.kind").inner_text().lower(), "exam")   # what the old rules said
        lab.hover()
        lab.locator(".act.whatis").click()
        self.sheet.wait_for(state="visible")
        self.assertEqual(self.page.locator("#add-title").text_content(), "Details")
        self.assertEqual(self.field("title").input_value(), "Biochemical Testing - Oxidase Test")
        self.assertEqual(self.page.locator("#add-form [name=kind]:checked").get_attribute("value"), "exam")
        self.page.locator("#add-form label", has_text="Assignment").click()
        self.page.locator("#toast", has_text="2 more like it").wait_for()
        self.sheet.wait_for(state="hidden")
        for title in ("Oxidase Test", "Catalase Test", "Urease Test"):
            self.assertEqual(self.row(title).locator("span.kind").count(), 0, title)
        self.assertEqual(self.row("Exam 2").locator("span.kind").inner_text().lower(), "exam")   # a real exam stays one
        self.assertEqual([self.stored(f"moodle:cm:{n}").kind for n in (1, 2, 3)], ["assignment"] * 3)

    def test_what_came_from_a_site_is_shown_but_locked(self):
        self.row("Exam 2").locator(".tick").focus()
        self.page.keyboard.press("e")
        self.sheet.wait_for(state="visible")
        for name in ("title", "date", "time", "course", "label", "notes"):
            self.assertTrue(self.field(name).is_disabled(), name)
        self.assertEqual((self.field("title").input_value(), self.field("time").input_value(), self.field("course").input_value()),
                         ("Exam 2", "09:30", "MATH 1550"))
        self.assertFalse(self.page.locator("#add-form button[type=submit]").is_visible())
        self.assertIn("This came from Moodle", self.page.locator("#locked-note").inner_text())
        self.assertEqual(self.page.evaluate("document.activeElement.name"), "kind")   # the one thing you can change
        self.page.keyboard.press("Escape")
        self.sheet.wait_for(state="hidden")
        self.assertEqual(self.stored("moodle:cal:4").level, "")   # looking changed nothing

    def test_by_keyboard_arrow_keys_choose_what_it_is(self):
        self.row("Chapter 7 Quiz").locator(".tick").focus()
        self.page.keyboard.press("e")
        self.sheet.wait_for(state="visible")
        self.assertEqual(self.page.locator("#add-form [name=kind]:checked").get_attribute("value"), "quiz")
        self.page.keyboard.press("ArrowLeft")                       # exam sits before quiz
        self.page.locator("#toast", has_text="Marked as an exam").wait_for()
        got = self.stored("moodle:cm:5")
        self.assertEqual((got.kind, got.level), ("test", "exam"))

    def test_yours_can_be_changed_in_every_field_and_filled_in_later(self):
        self.page.keyboard.press("Space")
        self.page.keyboard.type("study group")
        self.page.keyboard.press("Enter")
        card = self.row("Study group")
        card.wait_for()
        self.page.keyboard.press("e")                               # focus is on the new card
        self.sheet.wait_for(state="visible")
        self.assertFalse(self.field("title").is_disabled())
        self.assertTrue(self.page.locator("#add-form button[type=submit]").is_visible())
        self.field("title").fill("Study group, ch 9")
        self.field("time").fill("18:30")
        self.field("course").fill("CHEM 1212")
        self.field("label").select_option("extracurricular")
        self.field("notes").fill("room 204")
        self.page.locator("#add-form label", has_text="Event").click()
        self.page.keyboard.press("Enter")
        self.sheet.wait_for(state="hidden")
        card = self.row("Study group, ch 9")
        card.wait_for()
        self.assertEqual(card.locator("time").inner_text(), "6:30 PM")
        self.assertEqual(card.locator(".lab").inner_text(), "Extracurricular")
        self.assertIn("CHEM 1212", card.locator(".code").inner_text())
        saved = self.store.get(card.get_attribute("data-id"))
        self.assertEqual((saved.kind, saved.detail, saved.label, saved.timed), ("event", "room 204", "extracurricular", True))

    def test_double_click_opens_a_cards_details(self):
        self.row("Dentist").locator(".t").dblclick()
        self.sheet.wait_for(state="visible")
        self.assertEqual(self.field("title").input_value(), "Dentist")
        self.assertFalse(self.field("title").is_disabled())

    def test_after_a_locked_card_add_item_is_a_blank_unlocked_form_again(self):
        self.row("Exam 2").locator(".tick").focus()
        self.page.keyboard.press("e")
        self.sheet.wait_for(state="visible")
        self.page.keyboard.press("Escape")
        self.sheet.wait_for(state="hidden")
        self.page.keyboard.press("n")
        self.sheet.wait_for(state="visible")
        self.assertEqual(self.page.locator("#add-title").text_content(), "Add item")
        self.assertFalse(self.field("title").is_disabled())
        self.assertEqual(self.field("title").input_value(), "")
        self.assertTrue(self.page.locator("#add-form button[type=submit]").is_visible())


class DetailsInFocus(Details):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
