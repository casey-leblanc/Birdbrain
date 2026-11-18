"""The whole of quick write, with the keyboard only: Space, type a line, Enter. No mouse is touched.

The measure is five seconds from Space to a saved item. Typing is the student's share of that; this checks the page
and the app keep theirs under one second."""
from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta

from page import PageTest

LINE = "chem lab report fri 5pm #life"


def fridays_group() -> str:
    """The heading the coming Friday sits under, as the list words it."""
    today = datetime.now()
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    days = (friday.date() - today.date()).days
    if days == 0:   # on a Friday evening, 5 PM today has already gone by
        return "overdue" if today.hour >= 17 else "today"
    return "tomorrow" if days == 1 else f"{friday:%A, %b} {friday.day}".lower()


class WholeThing(PageTest):
    def test_space_type_enter(self):
        page = self.page
        page.evaluate("""() => { window.mouseUsed = 0;
            for (const ev of ['mousedown', 'pointerdown', 'click', 'dblclick'])
                document.addEventListener(ev, () => { window.mouseUsed++; }, true); }""")
        began = time.perf_counter()
        page.keyboard.press("Space")
        page.locator("#quick-line").wait_for(state="visible")
        opened = time.perf_counter() - began                         # the page's share: opening the line

        page.keyboard.type(LINE)                                     # the student's share
        page.locator("#quick-chips .chip[data-what=label]", has_text="Life").wait_for()
        self.assertEqual(page.locator("#quick-chips .chip").all_inner_texts()[1:], ["5:00 PM", "Life"])

        enter = time.perf_counter()
        page.keyboard.press("Enter")
        card = self.row("Chem lab report")
        card.wait_for()
        saved = time.perf_counter() - enter                          # the page's share: saving and showing the card

        self.assertEqual(self.group_of(card), fridays_group())
        self.assertEqual(card.locator("time").inner_text(), "5:00 PM")
        self.assertEqual(card.locator(".lab").inner_text(), "Life")
        self.assertEqual(card.locator(".t").inner_text(), "Chem lab report")
        self.assertFalse(page.locator("#quick-line").is_visible())
        self.assertEqual(page.evaluate("window.mouseUsed"), 0, "the mouse was used")

        mine = self.store.get(card.get_attribute("data-id"))
        self.assertEqual((mine.source, mine.title, mine.label, mine.due.strftime("%A %H:%M"), mine.timed),
                         ("manual", "Chem lab report", "life", "Friday 17:00", True))
        self.assertLess(opened + saved, 1.0, f"opening took {opened:.2f}s and saving {saved:.2f}s")

    def test_it_can_be_done_in_five_seconds_at_an_ordinary_typing_speed(self):
        """Forty words a minute is about 3.3 characters a second; this types at that pace, start to finish."""
        began = time.perf_counter()
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for(state="visible")
        self.page.keyboard.type("lab report fri", delay=300)         # 14 characters, one every 0.3 s
        self.page.keyboard.press("Enter")
        self.row("Lab report").wait_for()
        self.assertLess(time.perf_counter() - began, 5.0)


class WholeThingInFocus(WholeThing):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
