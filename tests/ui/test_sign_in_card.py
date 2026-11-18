"""A site that needs signing in to again says so at the top of the list, with one button."""
from __future__ import annotations

import unittest

from page import PageTest


class SignInCard(PageTest):
    needs_sign_in = ["Moodle"]

    def actions(self):
        self.asked = []
        return {"sign-in": lambda body: self.asked.append(body) or {"ok": True}}

    def test_the_card_is_above_the_list_and_its_button_opens_the_sign_in_window(self):
        card = self.page.locator(".banner")
        self.assertIn("Moodle needs signing in to again", card.inner_text())
        self.assertLess(card.bounding_box()["y"], self.page.locator(".row").first.bounding_box()["y"])
        card.get_by_role("button", name="Sign in").click()
        self.page.locator("#toast", has_text="sign-in window is opening").wait_for()
        self.assertEqual(len(self.asked), 1)

    def test_it_goes_when_the_site_is_signed_in(self):
        type(self).needs_sign_in = []
        try:
            self.open()
            self.assertEqual(self.page.locator(".banner").count(), 0)
        finally:
            type(self).needs_sign_in = ["Moodle"]


class SignInCardInFocus(SignInCard):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
