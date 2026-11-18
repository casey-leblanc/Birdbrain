"""Labels in Settings, and showing only one label or class on the list."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from page import PageTest

from store import Item


class WithLabelledItems(PageTest):
    def setUp(self):
        super().setUp()
        day = lambda n: (datetime.now() + timedelta(days=n)).replace(hour=23, minute=59, second=0, microsecond=0)
        for n, (title, label) in enumerate((("Groceries", "life"), ("Call home", "life"), ("Shift at the desk", "work"))):
            self.store.upsert(Item(f"manual:lab{n}", "manual", "assignment", title, day(1), "", label=label, timed=False))
        self.open()

    def shown(self):
        return self.page.locator(".bands .row:visible .t").evaluate_all(
            "els => els.map(e => e.firstChild.textContent)")


class Filter(WithLabelledItems):
    def test_clicking_a_tag_shows_only_that_label_and_escape_shows_everything(self):
        everything = self.shown()
        self.row("Groceries").locator(".lab").click()
        self.assertEqual(sorted(self.shown()), ["Call home", "Groceries"])
        self.assertEqual(self.page.locator("#filter-chip").inner_text(), "Only Life ✕")
        visible_groups = self.page.locator(".bands h3.grp:visible").all_inner_texts()
        self.assertEqual([g.lower() for g in visible_groups], ["tomorrow"])      # empty days step out of the way
        self.page.keyboard.press("Escape")
        self.assertEqual(self.shown(), everything)
        self.assertEqual(self.page.locator("#filter-chip").count(), 0)

    def test_hash_then_the_start_of_a_label(self):
        self.page.keyboard.press("#")
        self.page.locator("#filter-line").wait_for(state="visible")
        self.page.keyboard.type("wo")
        self.assertEqual(self.shown(), ["Shift at the desk"])                    # narrows as you type
        self.assertEqual(self.page.locator("#filter-says").inner_text(), "Only Work")
        self.page.keyboard.press("Enter")
        self.page.locator("#filter-line").wait_for(state="hidden")
        self.assertEqual(self.shown(), ["Shift at the desk"])                    # Enter keeps it
        self.page.locator("#filter-chip").click()                                # and the chip lets go of it
        self.assertGreater(len(self.shown()), 5)

    def test_at_then_the_start_of_a_class(self):
        self.page.keyboard.press("@")
        self.page.locator("#filter-line").wait_for(state="visible")
        self.page.keyboard.type("math")
        self.assertEqual(sorted(self.shown()), ["Chapter 7 Quiz", "Exam 2"])
        self.page.keyboard.press("Escape")                                       # Esc in the line: everything again
        self.page.locator("#filter-line").wait_for(state="hidden")
        self.assertGreater(len(self.shown()), 5)

    def test_the_filter_stays_on_when_the_list_is_rebuilt(self):
        self.row("Groceries").locator(".lab").click()
        self.page.keyboard.press("Space")
        self.page.keyboard.type("water plants tmr #life")
        self.page.locator("#quick-chips .chip[data-what=label]").wait_for()
        self.page.keyboard.press("Enter")
        self.row("Water plants").wait_for()
        self.assertEqual(sorted(self.shown()), ["Call home", "Groceries", "Water plants"])

    def test_clicking_a_course_tag_shows_only_that_class(self):
        self.row("Exam 2").locator(".code").click()
        self.assertEqual(sorted(self.shown()), ["Chapter 7 Quiz", "Exam 2"])
        self.row("Exam 2").locator(".code").click()                              # the same tag again lets go
        self.assertGreater(len(self.shown()), 5)


class LabelsInSettings(WithLabelledItems):
    def setUp(self):
        super().setUp()
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Labels").click()
        self.names = lambda: self.page.locator("#label-list .nick").evaluate_all("els => els.map(e => e.value)")

    def labels(self):
        import prefs
        return prefs.load(self.store)["labels"]

    def test_the_four_to_begin_with(self):
        self.assertEqual(self.names(), ["Life", "Extracurricular", "Appointment", "Work"])

    def test_rename_and_the_cards_follow(self):
        name = self.page.locator("#label-list .nick").first
        name.fill("Home")
        self.page.keyboard.press("Escape")
        self.page.locator(".row .lab", has_text="Home").first.wait_for()
        self.assertEqual(self.labels()[0]["name"], "Home")
        self.assertEqual(self.store.get("manual:lab0").label, "life")            # the items never changed

    def test_add_one_with_the_keyboard_and_use_it(self):
        self.page.locator("#label-new").focus()
        self.page.keyboard.type("Gym")
        self.page.keyboard.press("Enter")
        self.page.locator("#label-list li[data-id=gym]").wait_for()
        self.assertEqual(self.names()[-1], "Gym")
        self.page.keyboard.press("Escape")
        self.page.locator("#settings").wait_for(state="hidden")
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for(state="visible")
        self.page.keyboard.type("leg day tmr #gym")
        self.page.locator("#quick-chips .chip[data-what=label]", has_text="Gym").wait_for()
        self.page.keyboard.press("Enter")
        self.assertEqual(self.row("Leg day").locator(".lab").inner_text(), "Gym")

    def test_delete_takes_the_label_off_its_items_only_and_undo_puts_it_back(self):
        delete = self.page.locator("#label-list li[data-id=life] .label-del")
        delete.click()
        self.assertEqual(delete.inner_text(), "Click again to delete")
        delete.click()
        self.page.locator("#label-msg", has_text="Deleted the label “Life”. 2 items lost it").wait_for()
        self.assertEqual(self.names(), ["Extracurricular", "Appointment", "Work"])
        self.assertEqual((self.store.get("manual:lab0").label, self.store.get("manual:lab0").title), ("", "Groceries"))
        self.assertEqual(self.store.get("manual:lab2").label, "work")
        self.page.locator("#label-msg button", has_text="Undo").click()
        self.page.locator("#label-msg", has_text="is back").wait_for()
        self.assertEqual(self.names(), ["Life", "Extracurricular", "Appointment", "Work"])
        self.assertEqual(self.store.get("manual:lab0").label, "life")

    def test_a_colour_that_blends_in_is_said(self):
        colour = self.page.locator("#label-list li[data-id=work] input[type=color]")
        colour.fill("#ffffff")
        self.page.locator("#label-list li[data-id=work] .warn", has_text="Blends into the page in").wait_for()
        self.assertEqual(self.labels()[-1]["color"], "#ffffff")

    def test_two_labels_cannot_share_a_name(self):
        self.page.locator("#label-new").fill("work")
        self.page.keyboard.press("Enter")
        self.page.locator("#label-error", has_text="already a label called work").wait_for()
        self.assertEqual(len(self.labels()), 4)

    def test_the_details_sheet_offers_a_label_added_just_now(self):
        self.page.locator("#label-new").fill("Family")
        self.page.keyboard.press("Enter")
        self.page.locator("#label-list li[data-id=family]").wait_for()
        options = self.page.locator("#add-form [name=label] option").all_inner_texts()
        self.assertEqual(options, ["None", "Life", "Extracurricular", "Appointment", "Work", "Family"])


class FilterInFocus(Filter):
    layout = "focus"


class LabelsInSettingsInFocus(LabelsInSettings):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
