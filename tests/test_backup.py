"""Backup: what is yours goes into one file, and comes out of it on another computer."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from helpers import NOW, item, store

import backup
import prefs
from server import ListServer


def server(s):
    return ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                      request_mail_scan=lambda d: None, on_change=lambda: None)


class Backup(unittest.TestCase):
    def setUp(self):
        self.old = store()
        srv = server(self.old)
        prefs.update(self.old, {"labels": prefs.load(self.old)["labels"] + [{"id": "band", "name": "Band", "color": "#aa5500"}],
                                "courses": {"CHEM 1212": {"nick": "Orgo", "color": "#336699"}}})
        srv.quick({"text": "dentist tue 3pm #appointment", "save": True}, NOW)
        srv.quick({"text": "gym every mon wed 6pm #life", "save": True}, NOW)
        done = srv.quick({"text": "rehearsal fri 7pm #band", "save": True}, NOW)["id"]
        self.old.set_done(done, True)
        self.old.upsert(item("moodle:cm:1", "Lab report", NOW + timedelta(days=2)))    # from a site: not in the backup
        self.new = store()

    def mine(self, s):
        with s._lock:
            ids = [r[0] for r in s._db.execute("SELECT id FROM items WHERE source='manual' ORDER BY title").fetchall()]
        return [s.get(i) for i in ids]

    def test_the_file_holds_your_items_and_labels_and_nothing_from_your_sites(self):
        data = backup.export(self.old, NOW)
        self.assertEqual(data["birdbrain_backup"], 1)
        self.assertEqual(sorted(i["title"] for i in data["items"]), ["Dentist", "Gym", "Rehearsal"])
        self.assertIn("band", [x["id"] for x in data["labels"]])
        self.assertEqual(data["courses"]["CHEM 1212"]["nick"], "Orgo")
        self.assertNotIn("Lab report", json.dumps(data))
        gym = next(i for i in data["items"] if i["title"] == "Gym")
        self.assertEqual((gym["repeat"], gym["label"]), ("weekly:0,2", "life"))

    def test_importing_on_another_computer_brings_it_all_across(self):
        got = backup.restore(self.new, json.loads(json.dumps(backup.export(self.old, NOW))))
        self.assertEqual((got["added"], got["skipped"], got["labels"]), (3, 0, 1))
        dentist, gym, rehearsal = self.mine(self.new)
        was = {i.title: i for i in self.mine(self.old)}
        for now, title in ((dentist, "Dentist"), (gym, "Gym"), (rehearsal, "Rehearsal")):
            old = was[title]
            self.assertEqual((now.title, now.due, now.label, now.repeat, now.kind, now.timed),
                             (old.title, old.due, old.label, old.repeat, old.kind, old.timed))
        self.assertIsNotNone(rehearsal.done_at)                                 # what was done stays done
        self.assertIsNone(gym.done_at)
        p = prefs.load(self.new)
        self.assertIn("Band", [x["name"] for x in p["labels"]])
        self.assertEqual(p["courses"]["CHEM 1212"]["nick"], "Orgo")

    def test_importing_twice_changes_nothing(self):
        data = backup.export(self.old, NOW)
        backup.restore(self.new, data)
        again = backup.restore(self.new, data)
        self.assertEqual((again["added"], again["skipped"], again["labels"]), (0, 3, 0))
        self.assertEqual(len(self.mine(self.new)), 3)

    def test_what_is_already_here_is_kept_as_it_is(self):
        prefs.update(self.new, {"courses": {"CHEM 1212": {"nick": "Chem"}}})
        backup.restore(self.new, backup.export(self.old, NOW))
        self.assertEqual(prefs.load(self.new)["courses"]["CHEM 1212"]["nick"], "Chem")

    def test_a_file_that_isnt_a_backup_is_refused_and_bad_entries_are_skipped(self):
        for bad in ({}, [], {"birdbrain_backup": 99, "items": []}, {"items": []}, "hello"):
            with self.assertRaisesRegex(ValueError, "isn't a Birdbrain backup"):
                backup.restore(self.new, bad)
        got = backup.restore(self.new, {"birdbrain_backup": 1, "items": [
            {"title": "Fine", "due": "2026-11-20T15:00", "label": "nope", "repeat": "hourly", "kind": "spaceship"},
            {"title": "", "due": "2026-11-20T15:00"}, {"title": "No date"}, "junk", {"title": "Bad date", "due": "soon"}]})
        self.assertEqual(got["added"], 1)
        (fine,) = self.mine(self.new)
        self.assertEqual((fine.label, fine.repeat, fine.kind), ("", "", "assignment"))

    def test_the_action_saves_a_file_and_says_where_and_imports_what_it_reads(self):
        folder, shown = Path(tempfile.mkdtemp()), []
        out = backup.action(self.old, {"export": True}, folder=folder, reveal=shown.append)
        path = folder / out["saved"]
        self.assertTrue(path.name.startswith("Birdbrain-backup-") and path.suffix == ".json")
        self.assertEqual(shown, [path])
        self.assertIn("3 items of yours and 5 labels", out["message"])
        back = backup.action(self.new, {"import": json.loads(path.read_text(encoding="utf-8"))})
        self.assertEqual(back["message"], "Added 3 items and 1 label.")
        self.assertEqual(backup.action(self.new, {"import": json.loads(path.read_text(encoding="utf-8"))})["message"],
                         "Everything in that file is already here. Nothing was changed.")
        with self.assertRaises(ValueError):
            backup.action(self.new, {})


if __name__ == "__main__":
    unittest.main()
