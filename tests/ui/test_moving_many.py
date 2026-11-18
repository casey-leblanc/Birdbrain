"""Moving cards in a long list: 200 cards stay smooth, the list scrolls at its edges, and a finger can do it too."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from page import CHEM, PageTest
from store import Item

WATCH = """() => {
  window.__long = []; window.__gaps = []; let last = performance.now();
  new PerformanceObserver(l => l.getEntries().forEach(e => window.__long.push(Math.round(e.duration)))).observe({entryTypes: ['longtask']});
  (function f(){ const t = performance.now(); window.__gaps.push(t - last); last = t; requestAnimationFrame(f); })();
}"""
RESET = "() => { window.__long = []; window.__gaps = []; window.__m0 = window.birdbrainMeasures; }"
READ = "() => ({long: window.__long, worst: Math.max(0, ...window.__gaps.slice(1)), measures: window.birdbrainMeasures - window.__m0})"


class Many(PageTest):
    cards = 200

    def setUp(self):
        super().setUp()
        now = datetime.now()
        for n in range(self.cards):
            due = (now + timedelta(days=n % 10)).replace(hour=8 + n % 12, minute=0, second=0, microsecond=0)
            self.store.upsert(Item(f"moodle:cm:{100 + n}", "moodle", "assignment", f"Homework {n + 1}", due, CHEM, "https://example.edu/h"))
        self.open()

    def hold(self, row):
        row.scroll_into_view_if_needed()
        b = row.locator(".t").bounding_box()
        x, y = b["x"] + 12, b["y"] + b["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 4, y + 9, steps=3)
        self.page.wait_for_selector(".fly.dragging")
        return x + 4, y + 9


class Smooth(Many):
    """No long task (script or layout over 50 ms) while a card is dragged, dropped, or the list is filtered; and
    nothing is measured while the card only follows the pointer."""

    def test_dragging_dropping_and_filtering_200_cards(self):
        self.assertGreaterEqual(self.page.locator(".bands .row").count(), 200)
        self.page.evaluate(WATCH)
        x, y = self.hold(self.row("Homework 12"))

        # following the pointer inside one landing place: not one layout read
        self.page.evaluate(RESET)
        for k in range(40):
            self.page.mouse.move(x + k % 5, y + k % 3)
            self.page.wait_for_timeout(16)
        still = self.page.evaluate(READ)
        self.assertEqual(still["measures"], 0, "the drag loop measured the page while nothing changed")
        self.assertEqual(still["long"], [])

        # across the list and back: the page is read only when the landing place changes
        self.page.evaluate(RESET)
        for k in range(60):
            self.page.mouse.move(x + k * 2, y + (k if k < 30 else 60 - k) * 10)
            self.page.wait_for_timeout(16)
        moved = self.page.evaluate(READ)
        self.assertEqual(moved["long"], [], "a long task while dragging")
        self.assertLess(moved["worst"], 250, "a frame took far too long while dragging")
        self.assertLess(moved["measures"], 12 * (self.cards + 40), "the page was measured more often than the landing place changed")

        self.page.evaluate(RESET)
        gap = self.page.locator(".row.placeholder")
        above, below = gap.locator("xpath=preceding-sibling::li[1]"), gap.locator("xpath=following-sibling::li[1]")
        if above.count():                                                      # land before the card above
            b = above.bounding_box()
            self.page.mouse.move(b["x"] + 60, b["y"] + 6, steps=6)
        else:                                                                  # it's first: land after the card below
            b = below.bounding_box()
            self.page.mouse.move(b["x"] + 60, b["y"] + b["height"] - 4, steps=6)
        self.page.wait_for_timeout(80)
        self.page.mouse.up()
        self.page.wait_for_selector(".fly", state="detached")
        self.page.locator("#toast.show").wait_for()
        dropped = self.page.evaluate(READ)
        self.assertEqual(dropped["long"], [], "a long task while dropping")
        self.assertLess(dropped["worst"], 250)

        self.page.evaluate(RESET)
        self.page.keyboard.press("Escape")
        self.page.keyboard.press("@")
        self.page.keyboard.type("math")
        self.page.keyboard.press("Enter")
        self.page.locator("#filter-chip").wait_for()
        self.assertEqual(self.page.locator(".bands .row:visible").count(), 2)   # Exam 2 and the quiz
        self.page.locator("#filter-chip").click()
        self.page.locator(".bands .row:visible").nth(150).wait_for()
        filtered = self.page.evaluate(READ)
        self.assertEqual(filtered["long"], [], "a long task while filtering")
        self.assertLess(filtered["worst"], 250)


class SmoothInFocus(Smooth):
    layout = "focus"


class Edges(Many):
    cards = 60

    def test_holding_a_card_near_the_bottom_edge_scrolls_the_list(self):
        self.page.set_viewport_size({"width": 1280, "height": 600})
        self.page.evaluate("() => window.scrollTo(0, 0)")
        x, y = self.hold(self.page.locator(".bands ul.day[data-day] .row").first)
        self.assertEqual(self.page.evaluate("() => window.scrollY"), 0)
        self.page.mouse.move(x, 585, steps=6)
        self.page.wait_for_timeout(500)
        down = self.page.evaluate("() => window.scrollY")
        self.assertGreater(down, 100, "the list scrolls while the card is held at the bottom edge")
        self.page.mouse.move(x, 300, steps=4)
        self.page.wait_for_timeout(200)
        rest = self.page.evaluate("() => window.scrollY")
        self.page.wait_for_timeout(200)
        self.assertEqual(self.page.evaluate("() => window.scrollY"), rest, "away from the edges it stays put")
        self.page.mouse.move(x, 20, steps=4)
        self.page.wait_for_timeout(300)
        self.assertLess(self.page.evaluate("() => window.scrollY"), rest, "and it scrolls back up at the top edge")
        self.page.keyboard.press("Escape")
        self.page.wait_for_selector(".fly", state="detached")
        self.page.mouse.up()
        self.assertEqual([i.id for i in self.store.open_items() if i.rank is not None or i.planned], [])   # nothing was saved


class Touch(PageTest):
    """A finger: press and hold picks a card up; a finger that moves straight away is scrolling."""

    def context_options(self) -> dict:
        return {**super().context_options(), "has_touch": True}

    def setUp(self):
        super().setUp()
        self.cdp = self.context.new_cdp_session(self.page)

    def finger(self, kind: str, x: float = 0, y: float = 0):
        self.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})

    def test_press_and_hold_then_drag(self):
        b = self.row("Catalase").locator(".t").bounding_box()
        x, y = b["x"] + 12, b["y"] + b["height"] / 2
        d = self.row("Dentist").bounding_box()
        self.finger("touchStart", x, y)
        self.page.wait_for_selector(".fly.dragging")                           # after the hold, without moving
        for k in range(1, 9):
            self.finger("touchMove", x + 6, y + (d["y"] + 8 - y) * k / 8)
            self.page.wait_for_timeout(20)
        self.page.wait_for_timeout(100)
        self.finger("touchEnd")
        self.page.wait_for_selector(".fly", state="detached")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.stored("moodle:cm:2").rank, 0.0)

    def test_a_finger_that_moves_straight_away_doesnt_pick_up(self):
        b = self.row("Catalase").locator(".t").bounding_box()
        x, y = b["x"] + 12, b["y"] + b["height"] / 2
        self.finger("touchStart", x, y)
        for k in range(1, 6):
            self.finger("touchMove", x, y - k * 12)
            self.page.wait_for_timeout(16)
        self.page.wait_for_timeout(450)
        self.assertEqual(self.page.locator(".fly").count(), 0)
        self.finger("touchEnd")
        self.assertIsNone(self.stored("moodle:cm:2").rank)


if __name__ == "__main__":
    unittest.main()
