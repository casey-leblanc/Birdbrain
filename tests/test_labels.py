"""Labels: the four to begin with and your own; renaming, recolouring and deleting; colours checked in every look."""
from __future__ import annotations

import unittest

from helpers import NOW, at, item, store

import prefs
import report
import theme
from config import Settings
from server import ListServer


def server(s, changed=None):
    return ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                      request_mail_scan=lambda d: None,
                      on_change=(lambda: changed.append(1)) if changed is not None else (lambda: None))


class Saving(unittest.TestCase):
    def setUp(self):
        self.store = store()
        self.srv = server(self.store)
        self.labels = lambda: prefs.load(self.store)["labels"]

    def save(self, labels, **more):
        return self.srv.save_prefs({"labels": labels, **more})

    def test_a_new_label_gets_an_id_from_its_name(self):
        got = self.save(self.labels() + [{"name": "Study  Group!", "color": "#ABCDEF"}])
        self.assertEqual(got["prefs"]["labels"][-1], {"id": "study-group", "name": "Study Group!", "color": "#abcdef"})
        self.assertEqual(len(self.labels()), 5)

    def test_renaming_keeps_the_id_so_items_keep_their_label(self):
        self.store.upsert(item("manual:1", "Groceries", at(1), course="", label="life"))
        labels = self.labels()
        labels[0]["name"] = "Home"
        self.save(labels)
        self.assertEqual(self.labels()[0], {"id": "life", "name": "Home", "color": "#3fa7a0"})
        self.assertEqual(self.store.get("manual:1").label, "life")
        page = report.render_board(report.build(self.store, Settings(), NOW), Settings(), "", NOW, prefs=prefs.load(self.store))
        self.assertIn('data-label="life" style="--lab:#3fa7a0">Home</span>', page)

    def test_deleting_a_label_leaves_its_items_with_everything_else(self):
        self.store.upsert(item("manual:1", "Shift", at(1, 8, 0), course="", label="work", detail="bring badge", timed=True))
        self.store.upsert(item("manual:2", "Groceries", at(1), course="", label="life"))
        got = self.save([x for x in self.labels() if x["id"] != "work"])
        self.assertEqual(got["cleared"], {"work": ["manual:1"]})
        shift = self.store.get("manual:1")
        self.assertEqual((shift.label, shift.title, shift.detail, shift.due), ("", "Shift", "bring badge", at(1, 8, 0)))
        self.assertEqual(self.store.get("manual:2").label, "life")

    def test_undo_brings_the_label_and_its_items_back(self):
        self.store.upsert(item("manual:1", "Shift", at(1), course="", label="work"))
        before = self.labels()
        cleared = self.save([x for x in before if x["id"] != "work"])["cleared"]
        self.save(before, relabel=cleared)
        self.assertEqual([x["id"] for x in self.labels()], [x["id"] for x in before])
        self.assertEqual(self.store.get("manual:1").label, "work")

    def test_names_must_be_there_and_be_different(self):
        with self.assertRaisesRegex(ValueError, "Give the label a name"):
            self.save(self.labels() + [{"name": "   "}])
        with self.assertRaisesRegex(ValueError, "already a label called life"):
            self.save(self.labels() + [{"name": "life"}])
        self.assertEqual(len(self.labels()), 4)

    def test_a_name_that_would_collide_gets_its_own_id(self):
        labels = self.labels()
        labels[0]["name"] = "Home"                        # the id "life" stays with Home
        got = self.save(labels + [{"name": "Life", "color": "#101010"}])
        self.assertEqual([x["id"] for x in got["prefs"]["labels"]][-1], "life-2")

    def test_saving_labels_tells_open_pages(self):
        changed = []
        srv = server(self.store, changed)
        srv.save_prefs({"labels": self.labels()})
        self.assertTrue(changed)
        changed.clear()
        srv.save_prefs({"sound": False})                  # other preferences don't rebuild the list
        self.assertEqual(changed, [])

    def test_the_other_preferences_are_left_alone(self):
        self.srv.save_prefs({"layout": "focus"})
        self.save(self.labels()[:2])
        self.assertEqual((prefs.load(self.store)["layout"], len(self.labels())), ("focus", 2))


class Colours(unittest.TestCase):
    def test_the_four_to_begin_with_show_in_every_look(self):
        for x in prefs.LABELS:
            self.assertEqual(theme.hard_to_see(x["color"]), [], x["name"])

    def test_white_blends_into_day_looks_and_near_black_into_night_ones(self):
        white, black = theme.hard_to_see("#ffffff"), theme.hard_to_see("#101010")
        self.assertIn("Paper, day", white)
        self.assertNotIn("Paper, night", white)
        self.assertIn("Paper, night", black)
        self.assertIn("Glass", black)
        self.assertNotIn("Glass", white)

    def test_every_theme_and_both_modes_are_checked(self):
        names = {w.split(",")[0] for w in theme.hard_to_see("#ffffff")} | {w.split(",")[0] for w in theme.hard_to_see("#000000")}
        self.assertEqual(names - {"Glass"}, {t["name"] for t in theme.THEMES.values()})

    def test_settings_is_told_which_looks_a_colour_is_weak_in(self):
        s = store()
        got = server(s).save_prefs({"labels": [{"name": "Ghost", "color": "#ffffff"}, {"name": "Fine", "color": "#3fa7a0"}]})
        self.assertIn("Blends into the page in Forest, day", got["label_notes"]["ghost"])
        self.assertIn("thin outline", got["label_notes"]["ghost"])
        self.assertNotIn("fine", got["label_notes"])

    def test_every_tag_is_drawn_with_an_outline_so_none_is_lost(self):
        self.assertIn(".lab::before{", report.TOOLS_CSS)
        rule = report.TOOLS_CSS.split(".lab::before{")[1].split("}")[0]
        self.assertIn("box-shadow:0 0 0 1px", rule)


if __name__ == "__main__":
    unittest.main()
