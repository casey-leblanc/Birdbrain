"""Motion levels: the system's setting is where it starts, Settings is where it's chosen, and Off means still."""
from __future__ import annotations

import unittest

from page import PageTest

import prefs


class Levels(PageTest):
    def level(self):
        return self.page.evaluate("document.documentElement.dataset.motion")

    def pace(self, name="--m-base"):
        return self.page.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()")

    def test_it_starts_at_full_with_the_shared_timings(self):
        self.assertEqual(self.level(), "full")
        self.assertEqual(self.pace(), "200ms")
        self.assertTrue(self.pace("--m-spring").startswith(("linear(", "cubic-bezier(")))

    def test_the_systems_reduce_motion_setting_starts_it_at_off(self):
        self.page.emulate_media(reduced_motion="reduce")
        self.open()
        self.assertEqual(self.level(), "off")
        self.assertEqual(self.pace(), "0ms")

    def test_choosing_a_level_in_settings_takes_effect_at_once_and_is_kept(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Look").click()
        self.assertTrue(self.page.locator("input[name=motion][value=full]").is_checked())
        self.page.locator(".seg.motion label", has_text="Subtle").click()
        self.assertEqual(self.level(), "subtle")
        self.assertIn("No ripples or sheen", self.page.locator("#motion-hint").inner_text())
        self.page.locator(".seg.motion label", has_text="Off").click()
        self.assertEqual((self.level(), self.pace()), ("off", "0ms"))
        self.page.wait_for_timeout(200)
        self.assertEqual(prefs.load(self.store)["motion"], "off")
        self.open()                                                      # and it is still off after a reload
        self.assertEqual(self.level(), "off")

    def test_a_chosen_level_beats_the_systems_setting(self):
        prefs.update(self.store, {"motion": "full"})
        self.page.emulate_media(reduced_motion="reduce")
        self.open()
        self.assertEqual(self.level(), "full")

    def test_with_motion_off_nothing_on_the_page_animates(self):
        prefs.update(self.store, {"motion": "off"})
        self.open()
        self.page.keyboard.press("Space")                                # quick write would spring in
        self.page.locator("#quick-line").wait_for(state="visible")
        running = self.page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length")
        self.assertEqual(running, 0)
        self.page.keyboard.type("still tmr")
        self.page.keyboard.press("Enter")
        card = self.row("Still")
        card.wait_for()
        self.assertEqual(self.page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length"), 0)


class LevelsInFocus(Levels):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
