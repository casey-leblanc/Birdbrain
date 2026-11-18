"""Report a problem: what goes in the zip has nothing in it that says who the student is or where they study."""
from __future__ import annotations

import getpass
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from helpers import at, item, store

import trouble

LOG = """2026-11-18 09:02:11 INFO main: Set up: Moodle https://moodle.lsu.edu, Outlook https://outlook.office.com
2026-11-18 09:02:40 INFO moodle: Signed in as jdoe12@lsu.edu (Jordan Doe)
2026-11-18 09:03:05 INFO moodle: Reading 2026 Fall CHEM 1212 for A. Teacher (course 3 of 8)
2026-11-18 09:03:09 INFO moodle: found 'Biochemical Testing - Oxidase Test' due 2026-11-20
2026-11-18 09:03:30 WARNING outlook: couldn't open https://outlook.office.com/mail/inbox/id/AAQkAGI2TG93AAA=?token=abc
2026-11-18 09:03:31 INFO phone: Telegram bot set: @jordans_birdbrain_bot
2026-11-18 09:03:32 ERROR telegram: bad token 1234567890:AAHk3jf93jf02jf93jfk20fj39fj20fj3 at moodle.lsu.edu/my
2026-11-18 09:03:40 INFO main: session saved to HOME/AppData/Roaming/Birdbrain/session.json
2026-11-18 09:04:00 ERROR main: Scan crashed
Traceback (most recent call last):
  File "main.py", line 851, in loop
KeyError: 'timeline'"""


class Scrubbing(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Biochemical Testing - Oxidase Test", at(2), course="2026 Fall CHEM 1212 for A. Teacher",
                           detail="Bring goggles to room 214 Williams Hall"))
        self.s.upsert(item("manual:9", "Call Dr. Okafor about the scholarship", at(1), course="", source="manual"))
        self.names = trouble.known(self.s)

    def test_the_log_keeps_what_went_wrong_and_loses_who_and_where(self):
        out = trouble.scrub(LOG.replace("HOME", str(Path.home())), self.names)
        for gone in ("lsu.edu", "jdoe12", "outlook.office.com", "CHEM 1212", "A. Teacher", "Oxidase", "AAHk3jf93", "AAQkAGI2",
                     "token=abc", "jordans_birdbrain_bot", "moodle.lsu", str(Path.home())):
            self.assertNotIn(gone, out, gone)
        for kept in ("Scan crashed", "KeyError: 'timeline'", 'File "main.py", line 851, in loop', "course 3 of 8", "WARNING outlook",
                     "2026-11-18 09:03:05", "[email]", "[address]", "[token]", "[course]", "[title]", "~"):
            self.assertIn(kept, out, kept)

    def test_titles_notes_and_teachers_birdbrain_knows_are_replaced_wherever_they_appear(self):
        out = trouble.scrub("Said to be assignment: 'Biochemical Testing - Oxidase Test'; note: bring goggles to room 214 williams hall; "
                            "also 'Call Dr. Okafor about the scholarship' and 2026 Fall MATH 1550 for B. Other", self.names)
        self.assertEqual(out, "Said to be assignment: '[title]'; note: [note]; also '[title]' and 2026 Fall [course] for [name]")

    def test_the_computers_user_name_goes(self):
        user = getpass.getuser()
        if len(user) < 3:
            self.skipTest("the user name here is too short to tell from a word")
        self.assertNotIn(user, trouble.scrub(f"C:\\Users\\{user}\\AppData and /home/{user}/x and started by {user}", {}))

    def test_ordinary_words_and_numbers_are_left_alone(self):
        plain = "Updated 10:32 AM. 14 items, 3 new; scan took 42.5 s (interval 60 minutes); version 2.0.0 (73d77c1)"
        self.assertEqual(trouble.scrub(plain, {}), plain)

    def test_settings_keep_the_switches_and_lose_the_addresses(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            path.write_text(json.dumps({"moodle_url": "https://moodle.lsu.edu", "outlook_url": "https://outlook.office.com",
                                        "interval_minutes": 60, "notify": True, "morning_list": "07:30", "telegram_on": True,
                                        "telegram_bot": "jordans_birdbrain_bot", "telegram_chat": "4242", "hidden_keywords": ["rush week"],
                                        "mcgraw_sections": ["https://connect.example/section/9"], "typesafe_api_key": "sk-old-key-123",
                                        "gradescope_url": ""}), encoding="utf-8")
            out = json.loads(trouble.settings_text(path))
        self.assertEqual((out["interval_minutes"], out["notify"], out["morning_list"], out["telegram_on"]), (60, True, "07:30", True))
        for key in ("moodle_url", "outlook_url", "telegram_bot", "telegram_chat", "hidden_keywords", "mcgraw_sections", "typesafe_api_key"):
            self.assertEqual(out[key], "[removed]", key)
        self.assertEqual(out["gradescope_url"], "")                             # nothing there to remove

    def test_about_counts_cards_without_naming_any(self):
        about = trouble.about_text(self.s, "Updated 10:32 AM.")
        self.assertIn("1 moodle assignment (0 done)", about)
        self.assertIn("Last status: Updated 10:32 AM.", about)
        self.assertNotIn("Oxidase", about)


class TheZip(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Biochemical Testing - Oxidase Test", at(2), course="2026 Fall CHEM 1212 for A. Teacher"))
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "birdbrain.log"
        self.log.write_text(LOG, encoding="utf-8")

    def test_what_is_shown_is_exactly_what_is_saved(self):
        shown = trouble.gather(self.s, "Updated 10:32 AM.", "It stopped after my CHEM 1212 quiz, email me at jdoe12@lsu.edu", log=self.log)
        self.assertEqual([f["name"] for f in shown], ["what-happened.txt", "about.txt", "settings.txt", "log.txt"])
        self.assertEqual(shown[0]["text"], "It stopped after my [course] quiz, email me at [email]")
        path = trouble.save(shown, self.dir)
        self.assertTrue(path.name.startswith("Birdbrain-report-") and path.suffix == ".zip")
        with zipfile.ZipFile(path) as z:
            self.assertEqual(z.namelist(), [f["name"] for f in shown])
            for f in shown:
                self.assertEqual(z.read(f["name"]).decode("utf-8"), f["text"])
            everything = "".join(z.read(n).decode("utf-8") for n in z.namelist())
        for gone in ("lsu.edu", "jdoe12", "CHEM 1212", "Oxidase", "A. Teacher"):
            self.assertNotIn(gone, everything)

    def test_only_the_end_of_a_long_log_goes_in(self):
        self.log.write_text("\n".join(f"line {n}" for n in range(5000)), encoding="utf-8")
        text = trouble.log_text(self.log)
        self.assertEqual(len(text.splitlines()), trouble.LOG_TAIL)
        self.assertTrue(text.endswith("line 4999"))

    def test_no_log_and_no_note_still_make_a_report(self):
        files = trouble.gather(self.s, log=self.dir / "none.log", settings=self.dir / "none.json")
        self.assertEqual([f["name"] for f in files], ["about.txt", "settings.txt", "log.txt"])
        self.assertIn("no log yet", files[2]["text"])

    def test_the_action_previews_then_saves_and_never_sends(self):
        import inspect
        shown = trouble.action(self.s, {})
        self.assertNotIn("saved", shown)
        revealed = []
        saved = trouble.action(self.s, {"save": True, "note": "the list is empty"}, folder=self.dir, reveal=revealed.append)
        self.assertTrue((self.dir / saved["saved"]).exists())
        self.assertEqual(revealed, [self.dir / saved["saved"]])
        self.assertIn("Nothing was sent anywhere", saved["message"])
        code = inspect.getsource(trouble)
        for word in ("urllib", "requests", "socket", "http.client", "smtplib"):
            self.assertNotIn(word, code)                                        # it has no way to send anything


if __name__ == "__main__":
    unittest.main()
