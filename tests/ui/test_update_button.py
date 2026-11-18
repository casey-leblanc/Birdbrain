"""Settings > App > Updates: check, hear the answer, and update with one button."""
from __future__ import annotations

import unittest

from page import PageTest


class Updates(PageTest):
    def actions(self):
        self.calls = []

        def update(body):
            self.calls.append(body)
            if body.get("install"):
                return {"ok": True, "message": "Updating. Birdbrain restarts by itself in a minute or two.",
                        "current": "2.0.0 (abc1234)", "available": "2.0.1 (def5678)", "packaged": True}
            return {"ok": True, "message": "Birdbrain 2.0.1 (def5678) is available.", "current": "2.0.0 (abc1234)",
                    "available": "2.0.1 (def5678)", "packaged": True}
        return {"update": update}

    def test_check_then_update(self):
        self.page.keyboard.press("s")                      # Settings
        self.page.get_by_role("tab", name="App").click()
        section = self.page.locator("#updates-sec")
        button = section.locator("#update-go")
        self.assertFalse(button.is_visible())
        section.get_by_role("button", name="Check for updates").click()
        section.locator("#update-msg", has_text="2.0.1 (def5678) is available").wait_for()
        self.assertEqual(button.inner_text(), "Update to 2.0.1 (def5678) and restart")
        button.click()
        self.page.locator("#toast", has_text="restarts by itself").wait_for()
        self.page.locator("#settings").wait_for(state="hidden")
        self.assertEqual(self.calls, [{"check": True}, {"install": True}])


if __name__ == "__main__":
    unittest.main()
