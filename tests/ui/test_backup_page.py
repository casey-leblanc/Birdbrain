"""Settings > Advanced > Backup: export to a file, and import it somewhere else."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from page import PageTest

import backup


class BackupPage(PageTest):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        super().setUp()

    def actions(self) -> dict:
        return {"backup": lambda body: backup.action(self.store, body, folder=self.folder)}

    def open_fold(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Advanced").click()
        self.page.locator("#fold-backup summary").click()
        self.page.locator("#backup-export").wait_for()

    def test_export_saves_a_file_and_says_where(self):
        self.open_fold()
        self.page.locator("#backup-export").click()
        self.page.locator("#backup-msg", has_text="Saved Birdbrain-backup-").wait_for()
        (saved,) = list(self.folder.iterdir())
        data = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual([i["title"] for i in data["items"]], ["Dentist"])       # yours only: nothing from Moodle
        self.assertIn("1 item of yours", self.page.locator("#backup-msg").inner_text())

    def test_import_adds_what_the_file_holds_and_the_list_shows_it(self):
        other = self.folder / "Birdbrain-backup-20261101-0900.json"
        other.write_text(json.dumps({"birdbrain_backup": 1, "labels": [{"id": "band", "name": "Band", "color": "#aa5500"}], "items": [
            {"title": "Band practice", "kind": "event", "due": self.stored("manual:7").due.isoformat(timespec="minutes"),
             "timed": True, "label": "band", "repeat": "weekly:3"}]}), encoding="utf-8")
        self.open_fold()
        self.page.locator("#backup-file").set_input_files(str(other))
        self.page.locator("#backup-msg", has_text="Added 1 item and 1 label.").wait_for()
        self.page.keyboard.press("Escape")
        row = self.row("Band practice")
        row.wait_for()
        self.assertIn("Band", row.inner_text())
        self.page.locator("#settings").wait_for(state="hidden")
        self.page.keyboard.press("s")                                           # and importing it again changes nothing
        self.page.locator("#settings[open]").wait_for()
        self.page.locator("#backup-file").set_input_files(str(other))
        self.page.locator("#backup-msg", has_text="already here").wait_for()
        self.assertEqual(self.page.locator(".bands .row", has_text="Band practice").count(), 1)

    def test_a_file_that_isnt_one_says_so(self):
        wrong = self.folder / "notes.json"
        wrong.write_text("{\"hello\": 1}", encoding="utf-8")
        broken = self.folder / "broken.json"
        broken.write_text("not json at all", encoding="utf-8")
        self.open_fold()
        for path in (wrong, broken):
            self.page.locator("#backup-file").set_input_files(str(path))
            self.page.locator("#backup-msg", has_text="isn't a Birdbrain backup file").wait_for()
            self.page.locator("#backup-export").focus()
        self.assertEqual(len(self.store.open_items()), 7)

    def test_the_command_line_finds_it(self):
        self.page.keyboard.press("Control+k")
        self.page.keyboard.type("backup")
        self.page.keyboard.press("Enter")
        self.page.locator("#backup-export").wait_for()
        self.assertTrue(self.page.locator("#backup-export").is_visible())


if __name__ == "__main__":
    unittest.main()
