"""Dragging cards with a real pointer: reorder a day, plan a day, Completed and Archived, the refusal, Esc, Undo."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from page import PageTest


class Moving(PageTest):
    def titles(self, n: int) -> list[str]:
        """The cards under one day (0 today, 1 tomorrow, ...), top to bottom."""
        return [t.strip() for t in self.day_list(n).locator(".row .t").evaluate_all(
            "els => els.map(e => e.firstChild.textContent)")]

    def day_list(self, n: int):
        day = date.today() + timedelta(days=n)
        return self.page.locator(f".bands ul.day[data-day='{day:%Y-%m-%d}']")

    def hold(self, row):
        """Press on a card's title and carry it a little way: enough to pick it up."""
        for _ in range(100):                                                   # nobody grabs a card that's still gliding
            if not self.page.evaluate("() => document.getAnimations().some(a => a.effect.target.closest('.bands'))"):
                break
            self.page.wait_for_timeout(20)
        b = row.locator(".t").bounding_box()
        x, y = b["x"] + 12, b["y"] + b["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 4, y + 9, steps=3)
        self.page.wait_for_selector(".fly.dragging")
        return x, y

    def carry_to(self, x: float, y: float):
        self.page.mouse.move(x, y, steps=8)
        self.page.wait_for_timeout(120)   # a few frames: the card catches up and the list parts

    def over(self, row, where: str = "top"):
        """A point over another card: its upper part (to land before it) or its lower part (after it)."""
        b = row.bounding_box()
        return b["x"] + 60, b["y"] + (b["height"] * (.2 if where == "top" else .85))

    def drop(self):
        self.page.mouse.up()
        self.page.wait_for_selector(".fly", state="detached")

    def toast(self) -> str:
        return self.page.locator("#toast span").first.inner_text()


class Reordering(Moving):
    def test_a_card_picks_up_follows_and_the_others_part(self):
        dentist, catalase = self.row("Dentist"), self.row("Catalase")
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])
        self.hold(catalase)
        ghost = self.page.locator(".fly.dragging")
        self.assertEqual(ghost.count(), 1)
        self.assertIn("placeholder", catalase.get_attribute("class"))           # the gap it left
        self.assertTrue(self.page.locator(".dock").is_visible())                # Completed and Archived come up
        x, y = self.over(dentist)
        self.carry_to(x, y)
        g = ghost.bounding_box()
        self.assertTrue(g["x"] - 4 <= x <= g["x"] + g["width"] + 4 and g["y"] - 4 <= y <= g["y"] + g["height"] + 4,
                        "the lifted card is under the pointer")
        # the others have parted: the gap is now first in the day, before anything is dropped
        self.assertEqual(self.day_list(1).locator(".row").first.get_attribute("data-id"), "moodle:cm:2")
        self.drop()
        self.assertEqual(self.titles(1), ["Biochemical Testing - Catalase Test", "Dentist", "Chapter 7 Quiz"])
        self.assertEqual(self.toast(), "Moved to first of three")
        self.assertEqual(self.page.locator("#announce").text_content(), "Moved to Tomorrow, first of three")
        self.assertEqual(self.page.locator(".dock").count(), 0)
        self.assertNotIn("moving-card", self.page.locator("html").get_attribute("class") or "")
        self.page.reload()                                                      # it was saved, not just shown
        self.page.wait_for_selector(".row")
        self.assertEqual(self.titles(1), ["Biochemical Testing - Catalase Test", "Dentist", "Chapter 7 Quiz"])

    def test_esc_puts_it_back_and_nothing_is_saved(self):
        self.hold(self.row("Catalase"))
        self.carry_to(*self.over(self.row("Dentist")))
        self.page.keyboard.press("Escape")
        self.page.wait_for_selector(".fly", state="detached")
        self.page.mouse.up()
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])
        self.assertIsNone(self.stored("moodle:cm:2").rank)
        self.assertEqual(self.page.locator("dialog[open]").count(), 0)

    def test_letting_go_outside_any_target_puts_it_back(self):
        self.hold(self.row("Catalase"))
        self.carry_to(1260, 20)                                                # the window's corner: nowhere
        self.drop()
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])
        self.assertIsNone(self.stored("moodle:cm:2").rank)

    def test_a_click_still_opens_nothing_by_accident_and_a_drag_never_follows_the_link(self):
        pages = []
        self.context.on("page", lambda p: pages.append(p))
        self.hold(self.row("Catalase"))
        self.carry_to(*self.over(self.row("Dentist")))
        self.drop()
        self.page.wait_for_timeout(200)
        self.assertEqual(pages, [], "letting go of a dragged card must not open its link")

    def test_undo_and_ctrl_z_put_a_moved_card_back(self):
        self.hold(self.row("Catalase"))
        self.carry_to(*self.over(self.row("Dentist")))
        self.drop()
        self.page.locator(".toast-undo").click()
        self.page.locator("#toast", has_text="Put back").wait_for()
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])
        self.assertIsNone(self.stored("moodle:cm:2").rank)
        self.hold(self.row("Catalase"))
        self.carry_to(*self.over(self.row("Dentist")))
        self.drop()
        self.page.locator(".toast-undo").wait_for()
        self.page.keyboard.press("Control+z")
        self.page.locator("#toast", has_text="Put back").wait_for()
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])


class OtherDays(Moving):
    def test_a_later_card_moves_to_today_and_still_shows_its_real_deadline(self):
        urease = self.row("Urease")
        due = self.stored("moodle:cm:3").due
        self.hold(urease)
        self.carry_to(*self.over(self.row("Oxidase"), "bottom"))
        self.drop()
        self.assertEqual(self.group_of(self.row("Urease")), "today")
        self.assertEqual(self.stored("moodle:cm:3").planned, date.today())
        self.assertEqual(self.stored("moodle:cm:3").due, due)                   # the deadline itself never moves
        self.assertIn("due", self.row("Urease").locator("time.plan").inner_text().lower())
        self.assertIn("Today", self.toast())

    def test_something_from_a_site_cant_be_planned_past_its_deadline(self):
        oxidase = self.row("Oxidase")                                          # due today
        self.hold(oxidase)
        self.carry_to(*self.over(self.row("Dentist")))
        self.assertIn("wary", self.page.locator(".fly.dragging").get_attribute("class"))
        self.assertEqual(self.day_list(1).locator(".row.placeholder").count(), 0, "no gap opens where it can't go")
        self.page.mouse.up()
        self.page.locator("#toast", has_text="can't be planned for later").wait_for()
        self.page.wait_for_selector(".fly", state="detached")
        self.assertEqual(self.group_of(self.row("Oxidase")), "today")
        self.assertIsNone(self.stored("moodle:cm:1").planned)

    def test_your_own_card_goes_to_any_day_and_its_date_changes(self):
        was = self.stored("manual:7").due
        self.hold(self.row("Dentist"))
        self.carry_to(*self.over(self.row("Urease")))
        self.drop()
        now = self.stored("manual:7").due
        self.assertEqual(now.date(), date.today() + timedelta(days=3))
        self.assertEqual((now.hour, now.minute), (was.hour, was.minute))        # 3:00 PM stays 3:00 PM
        self.assertEqual(self.titles(3)[0], "Dentist")

    def test_an_empty_day_shows_up_as_a_place_to_drop(self):
        empty = self.day_list(4)
        self.assertFalse(empty.is_visible())
        self.hold(self.row("Dentist"))
        self.assertTrue(empty.is_visible())
        b = empty.bounding_box()
        self.carry_to(b["x"] + 80, b["y"] + b["height"] / 2)
        self.drop()
        self.assertEqual(self.stored("manual:7").due.date(), date.today() + timedelta(days=4))


class Bins(Moving):
    def dock(self, kind: str):
        b = self.page.locator(f".dock [data-bin={kind}]").bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

    def test_dropping_on_completed_ticks_it_off_and_undo_brings_it_back(self):
        self.hold(self.row("Catalase"))
        self.carry_to(*self.dock("completed"))
        self.assertIn("aimed", self.page.locator(".dock [data-bin=completed]").get_attribute("class"))
        self.drop()
        self.page.locator(".toast-undo").wait_for()
        self.assertIsNotNone(self.stored("moodle:cm:2").done_at)
        self.assertEqual(self.page.locator(".bands .row", has_text="Catalase").count(), 0)
        self.assertEqual(self.page.locator(".bin.completed .row", has_text="Catalase").count(), 1)
        self.page.locator(".toast-undo").click()
        self.page.locator(".bands .row", has_text="Catalase").wait_for()
        self.assertIsNone(self.stored("moodle:cm:2").done_at)

    def test_dropping_on_archived_hides_it(self):
        self.hold(self.row("Catalase"))
        self.carry_to(*self.dock("archived"))
        self.drop()
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.store.placements().get("moodle:cm:2"), "archived")
        self.assertEqual(self.page.locator(".bands .row", has_text="Catalase").count(), 0)
        self.assertEqual(self.page.locator(".bin.archived .row", has_text="Catalase").count(), 1)

    def test_a_card_drags_back_out_of_completed(self):
        self.store.set_done("moodle:cm:2", True)
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.page.locator(".bin.completed summary").click()
        done = self.page.locator(".bin.completed .row", has_text="Catalase")
        done.wait_for()
        done.scroll_into_view_if_needed()
        self.hold(done)
        dentist = self.row("Dentist")
        self.carry_to(*self.over(dentist))
        self.drop()
        self.page.locator(".bands .row", has_text="Catalase").wait_for()
        self.assertIsNone(self.stored("moodle:cm:2").done_at)
        self.assertEqual(self.titles(1)[0], "Biochemical Testing - Catalase Test")


    def test_a_card_drags_back_out_of_archived(self):
        self.store.set_placement("moodle:cm:2", "archived")
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.page.locator(".bin.archived summary").click()
        hidden = self.page.locator(".bin.archived .row", has_text="Catalase")
        hidden.wait_for()
        hidden.scroll_into_view_if_needed()
        self.page.wait_for_timeout(400)                                         # the bin finishes opening
        self.hold(hidden)
        self.carry_to(*self.over(self.row("Dentist")))
        self.drop()
        self.page.locator(".bands .row", has_text="Catalase").wait_for()
        self.assertIsNone(self.store.placements().get("moodle:cm:2"))


class Keyboard(Moving):
    """The same moves without a pointer: M picks up, arrows move, Enter drops, Esc puts back; D is Completed."""

    def heard(self) -> str:
        return self.page.locator("#announce").text_content()

    def pick_up(self, title: str):
        self.row(title).locator(".tick").focus()
        self.page.keyboard.press("m")
        self.page.locator(".row.carried").wait_for()

    def test_m_picks_up_arrows_move_enter_drops(self):
        self.pick_up("Catalase")
        self.assertIn("Picked up. Tomorrow, third of three", self.heard())
        self.assertEqual(self.page.locator("#app-menu:visible").count(), 0, "M on a card picks it up; it doesn't open the menu")
        self.page.keyboard.press("ArrowUp")
        self.assertEqual(self.heard(), "Tomorrow, second of three")
        self.page.keyboard.press("ArrowUp")
        self.assertEqual(self.heard(), "Tomorrow, first of three")
        self.assertEqual(self.titles(1)[0], "Biochemical Testing - Catalase Test")
        self.assertIsNone(self.stored("moodle:cm:2").rank)                      # nothing is saved until Enter
        self.page.keyboard.press("Enter")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.heard(), "Moved to Tomorrow, first of three")
        self.assertEqual(self.titles(1), ["Biochemical Testing - Catalase Test", "Dentist", "Chapter 7 Quiz"])
        self.assertEqual(self.stored("moodle:cm:2").rank, 0.0)
        self.assertEqual(self.page.locator(".row.carried").count(), 0)
        focused = self.page.evaluate_handle("document.activeElement").as_element()
        self.assertIn("Catalase", focused.evaluate("e => e.closest('.row').textContent"))   # focus stays on the card

    def test_arrows_carry_a_card_to_another_day(self):
        self.pick_up("Urease")                                                 # Saturday, in the next column
        self.page.keyboard.press("ArrowUp")                                    # up out of its day: the end of Friday
        self.assertIn("second of two", self.heard())
        self.page.keyboard.press("ArrowLeft")                                  # the column beside: Now
        self.assertEqual(self.heard(), "Today, first of two")
        self.page.keyboard.press("Enter")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.stored("moodle:cm:3").planned, date.today())
        self.assertIn("still due", self.toast())
        self.assertEqual(self.titles(0), ["Biochemical Testing - Urease Test", "Biochemical Testing - Oxidase Test"])

    def test_esc_puts_it_back(self):
        self.pick_up("Catalase")
        self.page.keyboard.press("ArrowUp")
        self.page.keyboard.press("ArrowUp")
        self.page.keyboard.press("ArrowUp")                                    # into Today
        self.assertEqual(self.group_of(self.row("Catalase")), "today")
        self.page.keyboard.press("Escape")
        self.assertEqual(self.heard(), "Put back.")
        self.assertEqual(self.titles(1), ["Dentist", "Chapter 7 Quiz", "Biochemical Testing - Catalase Test"])
        self.assertIsNone(self.stored("moodle:cm:2").planned)
        self.assertEqual(self.page.locator(".row.carried").count(), 0)

    def test_a_card_wont_step_past_its_deadline(self):
        self.pick_up("Oxidase")                                                # due today
        self.page.keyboard.press("ArrowDown")
        self.assertIn("can't be planned for later", self.heard())
        self.assertEqual(self.group_of(self.row("Oxidase")), "today")
        self.page.keyboard.press("Escape")

    def test_d_sends_a_card_to_completed_and_a_archives(self):
        self.row("Catalase").locator(".tick").focus()
        self.page.keyboard.press("d")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.toast(), "Moved to Completed")
        self.assertIsNotNone(self.stored("moodle:cm:2").done_at)
        focused = self.page.evaluate_handle("document.activeElement").as_element()
        self.assertIsNotNone(focused.evaluate("e => e.closest('.row') && e.closest('.row').dataset.id"), "focus moves to a neighbour")
        self.page.keyboard.press("Control+z")
        self.page.locator("#toast", has_text="Put back").wait_for()
        self.assertIsNone(self.stored("moodle:cm:2").done_at)
        self.row("Dentist").locator(".tick").focus()
        self.page.keyboard.press("a")
        self.page.locator(".bin.archived .row", has_text="Dentist").wait_for(state="attached")
        self.assertEqual(self.store.placements().get("manual:7"), "archived")

    def test_the_keys_window_lists_them(self):
        self.page.keyboard.press("?")
        keys = self.page.locator("dialog[open]").inner_text()
        self.assertIn("Pick it up", keys)
        self.assertIn("Send it to Completed", keys)


class FocusLayout(Reordering):
    layout = "focus"


class FocusKeyboard(Keyboard):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
