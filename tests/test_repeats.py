"""Repeating items of your own: read from quick write, and ticking one brings the next."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from helpers import NOW, store

import quickwrite
import repeats
from server import ListServer

TODAY = NOW.date()                       # Wednesday, Nov 18, 2026, 10:00
D = lambda n: TODAY + timedelta(days=n)


class Reading(unittest.TestCase):
    def read(self, text, now=NOW):
        return quickwrite.read(text, now)

    def test_the_two_from_the_brief(self):
        gym = self.read("gym every mon wed 6pm")
        self.assertEqual((gym.title, gym.repeat, gym.day, gym.time.hour), ("Gym", "weekly:0,2", TODAY, 18))
        self.assertEqual([(c.what, c.says) for c in gym.chips], [("day", "Today"), ("time", "6:00 PM"), ("repeat", "Every Mon, Wed")])
        rent = self.read("rent monthly on the 1st")
        self.assertEqual((rent.title, rent.repeat, rent.day), ("Rent", "monthly:1", date(2026, 12, 1)))
        self.assertEqual(rent.chips[-1].says, "Monthly on the 1st")

    def test_it_starts_the_first_time_it_comes_round(self):
        self.assertEqual(self.read("gym every mon wed 6pm", NOW.replace(hour=19)).day, D(5))    # tonight's has gone: Monday
        self.assertEqual(self.read("gym every tue thu").day, D(1))
        self.assertEqual(self.read("meds daily 9am").day, D(1))                                 # 9 AM has passed today
        self.assertEqual(self.read("meds daily 9pm").day, TODAY)

    def test_the_ways_of_saying_it(self):
        for text, rule in (("stretch every day", "daily"), ("stretch daily", "daily"), ("standup weekdays 9am", "weekly:0,1,2,3,4"),
                           ("standup every weekday", "weekly:0,1,2,3,4"), ("club every monday and wednesday", "weekly:0,2"),
                           ("lab every Tue, Thu 2pm", "weekly:1,3"), ("laundry weekly", "weekly:2"),
                           ("laundry every week on sat", "weekly:5"), ("call home fri weekly", "weekly:4"),
                           ("rent every month on the 15th", "monthly:15"), ("budget monthly", "monthly:18"),
                           ("budget nov 30 monthly", "monthly:30")):
            with self.subTest(text=text):
                self.assertEqual(self.read(text).repeat, rule)

    def test_a_typed_day_wins_and_the_words_leave_the_title(self):
        got = self.read("gym every mon wed starting next mon 6pm")
        self.assertEqual((got.day, got.repeat), (D(5), "weekly:0,2"))
        self.assertEqual(quickwrite.read("rent monthly on the 1st #life", NOW, labels={"life": "Life"}).title, "Rent")

    def test_words_that_only_look_like_it_stay_in_the_title(self):
        for text in ("read everything", "every other tuesday review", "plan every"):
            with self.subTest(text=text):
                self.assertEqual(self.read(text).repeat, "")
        handed_back = quickwrite.read("the daily planet", NOW, skip=["daily"])
        self.assertEqual((handed_back.repeat, handed_back.title), ("", "The daily planet"))


class Rules(unittest.TestCase):
    def test_next_after(self):
        self.assertEqual(repeats.next_after("weekly:0,2", D(0)), D(5))                 # Wed -> Mon
        self.assertEqual(repeats.next_after("weekly:0,2", D(5)), D(7))                 # Mon -> Wed
        self.assertEqual(repeats.next_after("daily", D(0)), D(1))
        self.assertEqual(repeats.next_after("monthly:1", date(2026, 12, 1)), date(2027, 1, 1))
        self.assertEqual(repeats.next_after("monthly:31", date(2027, 1, 31)), date(2027, 2, 28))   # a short month
        self.assertEqual(repeats.next_after("weekly:0", D(-9), today=TODAY), D(5))     # ticked late: never a day gone by

    def test_say_and_parse_agree(self):
        for rule in ("daily", "weekly:0,2", "weekly:0,1,2,3,4", "weekly:4", "monthly:1", "monthly:22", "monthly:3"):
            with self.subTest(rule=rule):
                self.assertEqual(repeats.parse(repeats.say(rule), TODAY), rule)
        self.assertEqual(repeats.parse("", TODAY), "")
        self.assertEqual(repeats.parse("never", TODAY), "")
        with self.assertRaisesRegex(ValueError, "every mon wed"):
            repeats.parse("whenever", TODAY)
        self.assertFalse(repeats.valid("weekly:9"))
        self.assertFalse(repeats.valid("monthly:0"))


class TickingBringsTheNext(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.srv = ListServer(self.s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                              request_mail_scan=lambda d: None, on_change=lambda: None)
        self.now = datetime.now().replace(second=0, microsecond=0)
        self.id = self.srv.quick({"text": "gym every day 11:59pm #life", "save": True}, self.now)["id"]

    def mine(self):
        return sorted((i for i in self.s.open_items() if i.source == "manual"), key=lambda i: i.due)

    def test_quick_write_keeps_the_rule_on_the_card(self):
        (gym,) = self.mine()
        self.assertEqual((gym.title, gym.repeat, gym.label), ("Gym", "daily", "life"))

    def test_ticking_brings_the_next_and_says_when(self):
        got = self.srv.set_done({"id": self.id, "done": True})
        (nxt,) = self.mine()
        self.assertEqual(got["next"], {"id": nxt.id, "day": "Tomorrow"})
        self.assertNotEqual(nxt.id, self.id)
        first = self.s.get(self.id)
        self.assertEqual((nxt.title, nxt.repeat, nxt.label, nxt.due), ("Gym", "daily", "life", first.due + timedelta(days=1)))
        self.assertIsNotNone(first.done_at)

    def test_unticking_takes_the_next_one_away_again(self):
        self.srv.set_done({"id": self.id, "done": True})
        self.srv.set_done({"id": self.id, "done": False})
        self.assertEqual([i.id for i in self.mine()], [self.id])

    def test_ticking_twice_doesnt_pile_them_up(self):
        self.s.set_done(self.id, True)
        self.s.set_done(self.id, True)
        self.assertEqual(len(self.mine()), 1)

    def test_the_next_one_ticked_too_is_kept_when_the_first_is_unticked(self):
        self.s.set_done(self.id, True)
        second = self.mine()[0]
        self.s.set_done(second.id, True)
        self.s.set_done(self.id, False)
        self.assertIsNotNone(self.s.get(second.id))                             # that's history now, not a spare

    def test_a_one_off_brings_nothing(self):
        one = self.srv.quick({"text": "dentist tomorrow 3pm", "save": True}, self.now)["id"]
        self.assertNotIn("next", self.srv.set_done({"id": one, "done": True}))
        self.assertEqual(len(self.mine()), 1)

    def test_the_details_box_changes_or_stops_it(self):
        fields = {"title": "Gym", "kind": "event", "date": self.now.date().isoformat(), "time": "18:00", "label": "life"}
        self.srv.update_item({**fields, "id": self.id, "repeat_text": "every mon wed"})
        self.assertEqual(self.s.get(self.id).repeat, "weekly:0,2")
        with self.assertRaisesRegex(ValueError, "how often"):
            self.srv.update_item({**fields, "id": self.id, "repeat_text": "sometimes"})
        self.srv.update_item({**fields, "id": self.id, "repeat_text": ""})
        self.assertEqual(self.s.get(self.id).repeat, "")
        self.assertNotIn("next", self.srv.set_done({"id": self.id, "done": True}))

    def test_deleting_and_undoing_keeps_the_rule(self):
        gone = self.srv.delete_item({"id": self.id})
        self.srv.restore_item(gone["item"])
        self.assertEqual(self.s.get(self.id).repeat, "daily")


if __name__ == "__main__":
    unittest.main()
