"""What the list does back: ripples and sheen on Glass at Full, the drawn tick, the drop-in, the breathing dot, and
cards gliding to their new places. Quieter in Focus and at Subtle; nothing at all when motion is Off."""
from __future__ import annotations

import unittest

from page import PageTest  # first: it sets the import path

import prefs  # noqa: E402


class Feel(PageTest):
    motion = ""   # "" follows the system (Full here), or "full", "subtle", "off"

    def setUp(self):
        super().setUp()
        if self.motion:
            prefs.update(self.store, {"motion": self.motion})
            self.open()

    def ripples(self) -> int:
        return self.page.evaluate("() => window.birdbrainRipples")

    def moving(self, row) -> bool:
        return row.evaluate("el => el.getAnimations().length > 0")

    def tick(self, title: str):
        self.row(title).locator(".tick").click()

    def quick_add(self, words: str):
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for()
        self.page.keyboard.type(words)
        self.page.keyboard.press("Enter")
        self.page.locator(".row.landed").wait_for()

    def over(self, row):
        b = row.bounding_box()
        self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=3)
        self.page.wait_for_timeout(60)
        return b

    def drag_first(self, title: str, onto: str):
        self.settled()
        b = self.row(title).locator(".t").bounding_box()
        self.page.mouse.move(b["x"] + 12, b["y"] + b["height"] / 2)
        self.page.mouse.down()
        self.page.mouse.move(b["x"] + 16, b["y"] + b["height"] / 2 + 9, steps=3)
        self.page.wait_for_selector(".fly.dragging")
        t = self.row(onto).bounding_box()
        self.page.mouse.move(t["x"] + 60, t["y"] + 6, steps=8)
        self.page.wait_for_timeout(120)
        self.page.mouse.up()
        self.page.wait_for_selector(".fly", state="detached")
        self.page.locator(".toast-undo").wait_for()


class GlassAtFull(Feel):
    def test_ticking_sends_a_ripple_from_the_box_and_draws_the_check(self):
        box = self.row("Catalase").locator(".tick").bounding_box()
        self.tick("Catalase")
        ring = self.page.locator(".ripple").first
        ring.wait_for(state="attached")
        self.assertEqual(self.ripples(), 1)
        at = ring.evaluate("el => { const m = new DOMMatrix(getComputedStyle(el).transform); return [m.e, m.f]; }")
        self.assertLess(abs(at[0] - (box["x"] + box["width"] / 2)), 3)          # it starts where the click was
        self.assertLess(abs(at[1] - (box["y"] + box["height"] / 2)), 3)
        self.assertEqual(ring.get_attribute("aria-hidden"), "true")
        ghost = self.page.locator(".fly .tick").first                           # the card that lifts away
        self.assertTrue(ghost.evaluate("el => el.checked"))
        self.assertEqual(ghost.evaluate("el => getComputedStyle(el).animationName"), "tick-pop")
        self.assertEqual(ghost.evaluate("el => getComputedStyle(el, '::before').animationName"), "tick-draw")
        self.page.locator(".toast-undo").wait_for()
        self.page.locator(".ripple").wait_for(state="detached")                 # and it cleans up after itself
        self.assertEqual(self.page.locator(".bin.completed .row", has_text="Catalase").count(), 1)

    def test_a_soft_sheen_follows_the_mouse_over_the_card_under_it(self):
        dentist, quiz = self.row("Dentist"), self.row("Chapter 7 Quiz")
        b = self.over(dentist)
        sheen = self.page.locator("#sheen")
        self.assertEqual(dentist.locator("#sheen.on").count(), 1)
        first = sheen.locator("i").evaluate("el => el.style.transform")
        self.page.mouse.move(b["x"] + 30, b["y"] + 12)
        self.page.wait_for_timeout(60)
        self.assertNotEqual(sheen.locator("i").evaluate("el => el.style.transform"), first, "it moves with the mouse")
        self.assertEqual(sheen.evaluate("el => getComputedStyle(el).pointerEvents"), "none")
        self.over(quiz)
        self.assertEqual(quiz.locator("#sheen").count(), 1)                    # one light, moved from card to card
        self.assertEqual(self.page.locator("#sheen").count(), 1)
        self.page.mouse.move(1270, 500)                                         # off the list
        self.page.wait_for_timeout(60)
        self.assertEqual(self.page.locator("#sheen.on").count(), 0)

    def test_the_sheen_survives_the_list_being_rebuilt_and_never_blocks_a_click(self):
        self.over(self.row("Dentist"))
        self.store.touch()                                                      # as a scan would: the list refreshes
        self.page.wait_for_timeout(6500)
        self.over(self.row("Chapter 7 Quiz"))
        self.over(self.row("Dentist"))
        self.assertEqual(self.row("Dentist").locator("#sheen.on").count(), 1)
        self.row("Dentist").locator(".tick").click()
        self.page.locator(".toast-undo").wait_for()
        self.assertIsNotNone(self.stored("manual:7").done_at)

    def test_a_card_added_by_quick_write_drops_in_with_a_ripple(self):
        self.quick_add("call mom")
        row = self.row("call mom")
        self.assertTrue(self.moving(row), "the new card drops into place")
        self.page.locator(".ripple").first.wait_for(state="attached")
        self.assertEqual(self.ripples(), 1)

    def test_a_dropped_card_sends_a_ripple_too(self):
        self.drag_first("Catalase", "Dentist")
        self.assertEqual(self.ripples(), 1)

    def test_the_status_dot_breathes_while_idle(self):
        dot = self.page.locator("#status-dot .dot")
        self.assertEqual(dot.evaluate("el => getComputedStyle(el).animationName"), "dot-rest")

    def test_filtering_lets_the_cards_that_stay_glide_to_their_places(self):
        quiz = self.row("Chapter 7 Quiz")
        was = quiz.bounding_box()["y"]
        self.page.keyboard.press("@")
        self.page.keyboard.type("math")
        self.page.keyboard.press("Enter")
        self.page.locator("#filter-chip").wait_for()
        self.assertTrue(self.moving(quiz), "the quiz glides up to where it now belongs")
        self.page.wait_for_timeout(500)
        self.assertLess(quiz.bounding_box()["y"], was)
        self.assertFalse(self.moving(quiz))


class GlassAtSubtle(Feel):
    motion = "subtle"

    def test_cards_still_move_but_there_is_no_ripple_and_no_sheen(self):
        self.over(self.row("Dentist"))
        self.assertEqual(self.page.locator("#sheen").count(), 0)
        self.tick("Catalase")
        self.page.locator(".fly").first.wait_for(state="attached")              # the card still lifts and travels
        self.assertEqual(self.page.locator(".fly .tick").first.evaluate("el => getComputedStyle(el, '::before').animationName"), "tick-draw")
        self.page.locator(".toast-undo").wait_for()
        self.quick_add("call mom")
        self.assertTrue(self.moving(self.row("call mom")))
        self.assertEqual(self.ripples(), 0)
        self.assertEqual(self.page.locator(".ripple").count(), 0)
        self.assertEqual(self.page.locator("#status-dot .dot").evaluate("el => getComputedStyle(el).animationName"), "none")


class FocusAtFull(Feel):
    layout = "focus"

    def test_the_same_answers_quieter_no_ripple_no_sheen(self):
        self.over(self.row("Dentist"))
        self.assertEqual(self.page.locator("#sheen").count(), 0)
        self.tick("Catalase")
        self.page.locator(".fly").first.wait_for(state="attached")
        self.assertEqual(self.page.locator(".fly .tick").first.evaluate("el => getComputedStyle(el, '::before').animationName"), "tick-draw")
        self.page.locator(".toast-undo").wait_for()
        self.quick_add("call mom")
        self.assertTrue(self.moving(self.row("call mom")))
        self.drag_first("Chapter 7 Quiz", "Dentist")
        self.assertEqual(self.ripples(), 0)
        self.assertEqual(self.page.locator("#status-dot .dot").evaluate("el => getComputedStyle(el).animationName"), "dot-rest")


class Off(Feel):
    motion = "off"

    def test_nothing_moves_and_everything_still_works(self):
        self.over(self.row("Dentist"))
        self.assertEqual(self.page.locator("#sheen").count(), 0)
        self.tick("Catalase")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.page.locator(".fly").count(), 0)
        self.assertIsNotNone(self.stored("moodle:cm:2").done_at)
        self.quick_add("call mom")
        self.assertFalse(self.moving(self.row("call mom")))
        self.drag_first("Chapter 7 Quiz", "Dentist")                            # dragging still works, without the motion
        self.assertEqual(self.stored("moodle:cm:5").rank, 0.0)
        self.assertEqual(self.ripples(), 0)
        self.assertEqual(self.page.locator("#status-dot .dot").evaluate("el => getComputedStyle(el).animationName"), "none")


if __name__ == "__main__":
    unittest.main()
