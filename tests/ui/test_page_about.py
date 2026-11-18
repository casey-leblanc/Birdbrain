"""Settings > App > About says whose project this is and where your data stays."""
from __future__ import annotations

import unittest

from page import PageTest


class About(PageTest):
    def test_about_is_readable_in_settings(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="App").click()
        about = self.page.locator("#about-sec")
        about.scroll_into_view_if_needed()
        self.assertTrue(about.is_visible())
        text = about.inner_text()
        self.assertIn("not affiliated with, endorsed by or supported by Louisiana State University", text)
        self.assertIn("stay on this computer", text)


if __name__ == "__main__":
    unittest.main()
