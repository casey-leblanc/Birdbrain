"""Settings > Advanced > Telegram: four short steps on the page itself, off until they are done."""
from __future__ import annotations

import unittest

from page import PageTest


class TelegramSetup(PageTest):
    available = True

    def setUp(self):
        self.state = {"available": self.available, "on": False, "bot": "", "has_token": False, "linked": False, "code": ""}
        self.asked: list[dict] = []
        super().setUp()

    def actions(self) -> dict:
        def telegram(body: dict) -> dict:
            self.asked.append(body)
            if "token" in body:
                if not body["token"].startswith("1234567890:"):
                    raise ValueError("Telegram didn't accept that token. Copy it again from BotFather's message, all of it.")
                self.state.update(on=True, bot="my_birdbrain_bot", has_token=True, code="482913")
            elif body.get("unlink"):
                self.state.update(linked=False, code="771204")
            elif body.get("off"):
                self.state.update(on=False, bot="", has_token=False, linked=False, code="")
            elif body.get("test"):
                return {"ok": True, **self.state, "message": "Sent. Look at Telegram on your phone."}
            return {"ok": True, **self.state}
        return {"telegram": telegram}

    def open_fold(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Advanced").click()
        self.assertFalse(self.page.locator("#tg-steps").is_visible())           # closed until opened
        self.page.locator("#fold-telegram summary").click()
        self.page.locator("#tg-1.now, #tg-cant:visible").first.wait_for()

    def classes(self):
        return [self.page.locator(f"#tg-{n}").get_attribute("class") for n in (1, 2, 3, 4)]

    def test_the_four_steps_from_nothing_to_linked(self):
        self.open_fold()
        self.assertEqual(self.page.locator("#tg-steps > li").count(), 4)
        self.assertEqual(self.classes(), ["now", "now", "later", "later"])
        self.assertIn("@BotFather", self.page.locator("#tg-1").inner_text())
        self.assertEqual(self.page.locator("#tg-token").get_attribute("type"), "password")

        self.page.locator("#tg-token").fill("1234567890:AAH-test")
        self.page.keyboard.press("Enter")
        self.page.locator("#tg-3.now").wait_for()
        self.assertEqual(self.classes(), ["done", "done", "now", "later"])
        self.assertEqual(self.page.locator("#tg-code").inner_text(), "/start 482913")
        self.assertEqual(self.page.locator("#tg-bot").inner_text(), "@my_birdbrain_bot")
        self.assertEqual(self.page.locator("#tg-bot").get_attribute("href"), "https://t.me/my_birdbrain_bot")
        self.assertEqual(self.page.locator("#tg-token").input_value(), "")      # the token isn't left in the page
        self.assertNotIn("AAH-test", self.page.content())

        self.state["linked"], self.state["code"] = True, ""                     # the phone sends the code
        self.page.locator("#tg-4.now").wait_for(timeout=8000)                   # the page moves on by itself
        self.assertIn("Linked.", self.page.locator("#tg-msg").inner_text())
        self.page.locator("#tg-test").click()
        self.page.locator("#tg-msg", has_text="Sent.").wait_for()
        self.assertEqual(self.asked[-1], {"test": True})

    def test_a_wrong_token_says_so_beside_the_box(self):
        self.open_fold()
        self.page.locator("#tg-token").fill("nonsense")
        self.page.locator("#tg-form button").click()
        self.page.locator("#tg-error", has_text="didn't accept that token").wait_for()
        self.assertEqual(self.classes(), ["now", "now", "later", "later"])
        self.page.locator("#tg-form button").click()                            # and an empty box asks for one
        self.page.locator("#tg-error", has_text="Paste the token first.").wait_for()

    def test_turning_it_off_asks_once_then_forgets(self):
        self.state.update(on=True, bot="my_birdbrain_bot", has_token=True, linked=True)
        self.open_fold_linked()
        self.page.locator("#tg-off").click()
        self.assertEqual(self.page.locator("#tg-off").inner_text(), "Click again to turn off")
        self.assertNotIn({"off": True}, self.asked)
        self.page.locator("#tg-off").click()
        self.page.locator("#tg-1.now").wait_for()
        self.assertIn({"off": True}, self.asked)
        self.assertIn("token has been removed", self.page.locator("#tg-msg").inner_text())

    def test_link_another_phone_shows_a_new_code(self):
        self.state.update(on=True, bot="my_birdbrain_bot", has_token=True, linked=True)
        self.open_fold_linked()
        self.page.locator("#tg-unlink").click()
        self.page.locator("#tg-3.now").wait_for()
        self.assertEqual(self.page.locator("#tg-code").inner_text(), "/start 771204")

    def open_fold_linked(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Advanced").click()
        self.page.locator("#fold-telegram summary").click()
        self.page.locator("#tg-4.now").wait_for()


class NowhereToKeepTheToken(TelegramSetup):
    available = False

    def test_it_says_it_cant_and_offers_no_steps(self):
        self.open_fold()
        self.assertTrue(self.page.locator("#tg-cant").is_visible())
        self.assertFalse(self.page.locator("#tg-steps").is_visible())

    test_the_four_steps_from_nothing_to_linked = test_a_wrong_token_says_so_beside_the_box = None
    test_turning_it_off_asks_once_then_forgets = test_link_another_phone_shows_a_new_code = None


if __name__ == "__main__":
    unittest.main()
