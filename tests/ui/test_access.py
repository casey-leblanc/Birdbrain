"""A pass for access: every action by keyboard, a visible focus, text that can be read in every theme, a name for
every control, and a text size setting."""
from __future__ import annotations

import unittest
from datetime import date

from page import PageTest  # first: it sets the import path

import contrast  # noqa: E402
import glass  # noqa: E402
import prefs  # noqa: E402
import theme  # noqa: E402

LOOKS = [("glass", "theme", k) for k in glass.SCHEMES] + [("focus", "focus_theme", k) for k in theme.THEMES]
SHEET_TEXT = ("#settings .tab", "#settings h2", "#settings .set-sec h3", "#settings .hint", "#settings .check span", "#settings .btn",
              "#settings .sub", "#settings .seg span")
QUICK_TEXT = ("#quick-line", "#quick .chip", "#quick .quick-hint", "#quick .quick-hint kbd")

NAMELESS = """() => {
  const out = [];
  const name = el => {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    const by = el.getAttribute('aria-labelledby');
    if (by) return by.split(' ').map(id => (document.getElementById(id) || {}).textContent || '').join(' ').trim();
    if (el.labels && el.labels.length) return [...el.labels].map(l => l.textContent).join(' ').trim();
    if (el.closest('label')) return el.closest('label').textContent.trim();
    return (el.textContent || '').trim() || el.title || '';
  };
  const controls = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=tab], [role=menuitem], [role=option], [tabindex="0"]';
  for (const el of document.querySelectorAll(controls)) if (!name(el)) out.push(el.outerHTML.slice(0, 120));
  for (const d of document.querySelectorAll('dialog'))
    if (!d.getAttribute('aria-label') && !d.getAttribute('aria-labelledby')) out.push('a window with no name: #' + d.id);
  for (const el of document.querySelectorAll('img')) if (!el.hasAttribute('alt')) out.push('a picture with no alt: ' + el.outerHTML.slice(0, 80));
  for (const el of document.querySelectorAll('svg'))
    if (el.getAttribute('aria-hidden') !== 'true' && !el.getAttribute('aria-label') && !el.closest('[aria-hidden=true]'))
      out.push('a drawing neither named nor hidden: ' + el.outerHTML.slice(0, 80));
  return out;
}"""

# Tab once, then say what has the focus and whether it shows. Each stop is numbered the first time it is met.
NEXT_STOP = """() => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const again = a.dataset.auditStop !== undefined;
  if (!again) a.dataset.auditStop = String(window.__stops = (window.__stops || 0) + 1);
  const cs = getComputedStyle(a), box = a.type === 'checkbox' || a.type === 'radio' ? a.closest('label') || a : a;
  const seen = el => { const s = getComputedStyle(el);
    return (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 1.5) || s.boxShadow !== 'none'; };
  // a radio or tick box drawn as something else shows its focus on what stands in for it
  const ring = seen(a) || (box !== a && (seen(box) || [...box.querySelectorAll('*')].some(seen)));
  return {again, ring, what: (a.getAttribute('aria-label') || a.textContent || a.id || a.name || a.tagName).trim().slice(0, 40)};
}"""


class Contrast(PageTest):
    def context_options(self) -> dict:
        return {"viewport": {"width": 1280, "height": 1700}}     # tall enough for the whole list and both bins

    def setUp(self):
        super().setUp()
        self.store.set_done("moodle:cm:5", True)                  # something in Completed, in Archived, and back from snooze
        self.store.set_placement("moodle:cm:3", "archived")
        self.store.snooze("manual:7", date.today())
        prefs.update(self.store, {"bins": {"completed": True, "archived": True}, "motion": "off"})

    def look(self, layout: str, key: str, name: str, mode: str):
        prefs.update(self.store, {"layout": layout, key: name, "mode": mode})
        self.page.goto(self.server.url)
        self.page.wait_for_selector(".row")
        self.page.wait_for_timeout(350)                           # the photo behind the glass

    def test_the_list_can_be_read_in_every_theme_day_and_night(self):
        measured = 0
        for layout, key, name in LOOKS:
            for mode in ("dark", "light"):
                with self.subTest(layout=layout, theme=name, mode=mode):
                    self.look(layout, key, name, mode)
                    got = contrast.measure(self.page)
                    measured += len(got)
                    self.assertGreater(len(got), 30, "the audit found too little text to mean anything")
                    self.assertEqual([f'{m["sel"]} “{m["text"]}” {m["ratio"]}:1' for m in got if m["ratio"] < m["need"]], [])
        self.assertGreater(measured, 28 * 30)

    def test_settings_and_quick_write_can_be_read_in_every_theme(self):
        for layout, key, name in LOOKS:
            for mode in ("dark", "light"):
                with self.subTest(layout=layout, theme=name, mode=mode):
                    self.look(layout, key, name, mode)
                    self.page.keyboard.press("s")
                    self.page.locator("#settings[open]").wait_for()
                    self.assertEqual(contrast.failures(self.page, SHEET_TEXT), [])
                    self.page.keyboard.press("Escape")
                    self.page.locator("#settings").wait_for(state="hidden")
                    self.page.keyboard.press("Space")
                    self.page.locator("#quick[open]").wait_for()
                    self.page.keyboard.type("essay fri 5pm")
                    self.page.locator("#quick .chip", has_text="5:00 PM").wait_for()   # the chips have settled
                    self.assertEqual(contrast.failures(self.page, QUICK_TEXT), [])

    def test_the_audit_itself_catches_text_that_cant_be_read(self):
        self.look("glass", "theme", "forest", "dark")
        self.page.evaluate("() => document.querySelectorAll('.row .t').forEach(e => e.style.color = 'rgb(70,60,90)')")
        self.assertGreaterEqual(len(contrast.failures(self.page)), 5)


class Names(PageTest):
    def test_every_control_window_and_picture_has_a_name(self):
        self.store.set_done("moodle:cm:5", True)
        self.store.set_placement("moodle:cm:3", "archived")
        prefs.update(self.store, {"bins": {"completed": True, "archived": True}})
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.assertEqual(self.page.evaluate(NAMELESS), [])        # the list, and every window, which are all in the page

    def test_what_changes_is_announced(self):
        for region in ("#announce", "#toast"):
            self.assertEqual(self.page.locator(region).get_attribute("aria-live"), "polite")
        self.page.keyboard.press("j")
        self.page.keyboard.press("x")                             # tick the first card
        self.page.locator("#toast.show").wait_for()
        self.assertIn("Moved to Completed", self.page.locator("#toast").inner_text())
        box = self.page.locator(".bands .row .tick").first
        self.assertTrue(box.get_attribute("aria-label").startswith("Done: "))
        self.assertTrue(box.get_attribute("aria-describedby"))


class NamesInFocus(Names):
    layout = "focus"


class FocusShows(PageTest):
    def stops(self, limit: int = 160) -> list[dict]:
        seen = []
        for _ in range(limit):
            self.page.keyboard.press("Tab")
            stop = self.page.evaluate(NEXT_STOP)
            if stop is None:                                      # out of the page (the browser's own bar): come round again
                continue
            if stop["again"]:
                break
            seen.append(stop)
        return seen

    def test_every_tab_stop_on_the_list_shows_where_you_are(self):
        self.store.set_done("moodle:cm:5", True)
        prefs.update(self.store, {"bins": {"completed": True}})
        self.page.reload()
        self.page.wait_for_selector(".row")
        stops = self.stops()
        self.assertGreater(len(stops), 25)                        # ticks, titles, the buttons on each card, the corner, the bins
        self.assertEqual([s["what"] for s in stops if not s["ring"]], [])

    def test_every_tab_stop_in_settings_shows_where_you_are(self):
        self.page.keyboard.press("s")
        self.page.locator("#settings[open]").wait_for()
        for tab in ("Sign-ins", "Look", "Notifications", "Keys", "Labels", "Updates", "About", "Advanced"):
            with self.subTest(section=tab):
                self.page.get_by_role("tab", name=tab).click()
                self.page.evaluate("() => { document.querySelectorAll('[data-audit-stop]').forEach(e => delete e.dataset.auditStop); }")
                stops = self.stops(60)
                self.assertGreater(len(stops), 2)
                self.assertEqual([s["what"] for s in stops if not s["ring"]], [])


class FocusShowsInFocus(FocusShows):
    layout = "focus"


class KeyboardOnly(PageTest):
    """One sitting with no mouse: everything a card can have done to it, and everything round the list."""

    def toast(self, words: str):
        self.page.locator("#toast", has_text=words).wait_for()

    def test_a_whole_sitting_without_the_mouse(self):
        key = self.page.keyboard.press
        key("m")                                                  # the menu (on a card, M picks the card up instead)
        self.page.locator("#app-menu").wait_for(state="visible")
        key("Escape")
        self.page.locator("#app-menu").wait_for(state="hidden")
        key("j")                                                  # onto the first card
        first = self.page.evaluate("() => document.activeElement.closest('.row').dataset.id")
        self.assertEqual(first, "moodle:cm:6")
        key("x"); self.toast("Moved to Completed")                # tick it off
        key("Control+z"); self.toast("Put back")                  # and undo
        key("ArrowDown")
        key("e")                                                  # its details
        self.page.locator("#add-item[open]").wait_for()
        key("Escape")
        self.page.locator("#add-item").wait_for(state="hidden")
        key("a"); self.toast("Moved to Archived")                 # archive
        key("Control+z"); self.toast("Back on your list")
        self.page.locator(".bands .row[data-id='manual:7'] .tick").focus()
        key("s")                                                  # snooze
        self.page.locator("#snooze[open]").wait_for()
        key("t"); self.toast("Snoozed until tomorrow")
        key("Control+z"); self.toast("Back on your list")
        self.page.locator(".bands .row[data-id='moodle:cm:5'] .tick").focus()
        key("m"); key("ArrowUp"); key("Enter")                    # move it up its day
        self.toast("Moved to")
        key("d"); self.toast("Moved to Completed")                # send to Completed
        key("Space")                                              # quick write
        self.page.locator("#quick-line").wait_for()
        self.page.keyboard.type("call mom")
        key("Enter"); self.toast("Added")
        self.page.locator("#quick").wait_for(state="hidden")
        key("Control+k")                                          # search and commands
        self.page.locator("#filter[open]").wait_for()
        self.page.keyboard.type("keys")
        key("Enter")
        self.page.locator("#keys[open]").wait_for()
        key("Escape")
        self.page.locator("#keys").wait_for(state="hidden")
        key("Control+k")                                          # settings, from a card, by its command
        self.page.locator("#filter[open]").wait_for()
        self.page.keyboard.type("settings")
        key("Enter")
        self.page.locator("#settings[open]").wait_for()
        self.page.locator("#settings [role=tab][aria-selected=true]").focus()
        key("ArrowDown")
        self.assertTrue(self.page.locator("#pane-look").is_visible())
        key("Escape")
        self.assertIsNotNone(self.stored("moodle:cm:5").done_at)
        self.assertEqual(len([i for i in self.store.open_items() if i.title == "Call mom"]), 1)


class TextSize(PageTest):
    def size_of(self, selector: str) -> float:
        return self.page.locator(selector).first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")

    def test_larger_text_scales_everything_at_once_and_is_kept(self):
        title, meta, heading = self.size_of(".row .t"), self.size_of(".row .meta"), self.size_of(".band h2")
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Look").click()
        self.assertEqual(self.page.locator(".seg.text-size label").all_inner_texts(), ["Smaller", "Standard", "Larger", "Largest"])
        self.assertTrue(self.page.locator("input[name=text-size][value='']").is_checked())
        self.page.locator(".seg.text-size label", has_text="Largest").click()
        self.assertAlmostEqual(self.size_of(".row .t"), title * 1.3, delta=.6)
        self.assertAlmostEqual(self.size_of(".row .meta"), meta * 1.3, delta=.6)
        self.assertAlmostEqual(self.size_of(".band h2"), heading * 1.3, delta=.8)
        self.assertAlmostEqual(self.size_of("#settings .hint"), 13 * 1.3, delta=.6)   # the windows too
        self.page.wait_for_timeout(300)
        self.assertEqual(prefs.load(self.store)["text"], "larger")
        self.page.reload()                                        # kept, and there before the page is drawn
        self.page.wait_for_selector(".row")
        self.assertAlmostEqual(self.size_of(".row .t"), title * 1.3, delta=.6)
        self.assertEqual(self.page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"), True,
                         "nothing is pushed off the side at the largest size")

    def test_smaller_and_back_to_standard_by_keyboard(self):
        title = self.size_of(".row .t")
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Look").click()
        self.page.locator("input[name=text-size][value='']").focus()
        self.page.keyboard.press("ArrowLeft")
        self.assertAlmostEqual(self.size_of(".row .t"), title * .9, delta=.5)
        self.page.keyboard.press("ArrowRight")
        self.assertAlmostEqual(self.size_of(".row .t"), title, delta=.2)


class TextSizeInFocus(TextSize):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
