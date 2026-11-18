"""Where a card may go: a new place in its day, Completed, Archived, an earlier day. And where it may not."""
from __future__ import annotations

import unittest
from datetime import datetime

from helpers import NOW, at, item, store

import planner
import report
from config import Settings
from server import ListServer

TODAY = NOW.date()
D = lambda n: at(n).date()


def board(s):
    return report.build(s, Settings(), NOW)


def under(b, label):
    for c in b.columns:
        for g in c.groups:
            if g.label.startswith(label):
                return [i.title for i in g.items]
    raise AssertionError(label)


class Reorder(unittest.TestCase):
    def setUp(self):
        self.s = store()
        for n, (title, hour) in enumerate((("Reading", 9), ("Problem set", 13), ("Lab report", 23)), 1):
            self.s.upsert(item(f"moodle:cm:{n}", title, at(1, hour, 0)))

    def test_a_days_cards_take_the_order_they_are_dropped_in(self):
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Reading", "Problem set", "Lab report"])
        got = planner.move(self.s, "moodle:cm:3", "day", D(1), before="moodle:cm:1", now=NOW)
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Lab report", "Reading", "Problem set"])
        self.assertEqual((got["position"], got["of"], got["heard"]), (1, 3, "Moved to Tomorrow, first of three"))
        planner.move(self.s, "moodle:cm:1", "day", D(1), before=None, now=NOW)        # no card after it: last
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Lab report", "Problem set", "Reading"])

    def test_the_order_survives_the_next_scan(self):
        planner.move(self.s, "moodle:cm:3", "day", D(1), before="moodle:cm:1", now=NOW)
        for n, (title, hour) in enumerate((("Reading", 9), ("Problem set", 13), ("Lab report", 23)), 1):
            self.s.upsert(item(f"moodle:cm:{n}", title, at(1, hour, 0)))
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Lab report", "Reading", "Problem set"])

    def test_a_new_card_joins_by_its_time(self):
        planner.move(self.s, "moodle:cm:3", "day", D(1), before="moodle:cm:1", now=NOW)   # Lab report (11 PM) first
        self.s.upsert(item("moodle:cm:9", "Quiz at noon", at(1, 12, 0), kind="test"))
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Lab report", "Reading", "Quiz at noon", "Problem set"])

    def test_undo_puts_the_day_back_in_its_old_order(self):
        got = planner.move(self.s, "moodle:cm:3", "day", D(1), before="moodle:cm:1", now=NOW)
        self.s.restore(got["undo"])
        self.assertEqual(under(board(self.s), "Tomorrow"), ["Reading", "Problem set", "Lab report"])


class AnotherDay(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))          # due Friday
        self.s.upsert(item("moodle:cm:2", "Reading", at(1, 9, 0)))

    def test_an_earlier_day_means_I_will_do_it_then_and_it_still_says_when_it_is_due(self):
        got = planner.move(self.s, "moodle:cm:1", "day", D(0), now=NOW)
        b = board(self.s)
        self.assertEqual(under(b, "Today"), ["Lab report"])
        self.assertEqual(under(b, "Friday"), [])
        self.assertEqual(got["says"], "Moved to Today; still due Friday")
        page = report.render_board(b, Settings(), "", NOW)
        self.assertIn('class="w plan"', page)
        self.assertIn(">due Fri 11:59 PM</time>", page)

    def test_the_plan_survives_a_scan_and_is_forgotten_once_its_day_has_gone_by(self):
        planner.move(self.s, "moodle:cm:1", "day", D(0), now=NOW)
        self.s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))
        self.assertEqual(under(board(self.s), "Today"), ["Lab report"])
        tomorrow = report.build(self.s, Settings(), at(1, 10, 0))                    # the planned day passed, undone
        self.assertEqual(under(tomorrow, "Tomorrow"), ["Lab report"])               # back under its deadline

    def test_it_cannot_be_planned_for_later_than_it_is_due(self):
        with self.assertRaises(planner.Refused) as no:
            planner.move(self.s, "moodle:cm:1", "day", D(4), now=NOW)
        self.assertEqual(str(no.exception), "It's due Friday, so it can't be planned for later than that.")
        self.assertEqual(under(board(self.s), "Friday"), ["Lab report"])             # nothing changed
        with self.assertRaisesRegex(planner.Refused, "It's due tomorrow, so"):
            planner.move(self.s, "moodle:cm:2", "day", D(3), now=NOW)

    def test_back_onto_its_own_day_drops_the_plan(self):
        planner.move(self.s, "moodle:cm:1", "day", D(0), now=NOW)
        planner.move(self.s, "moodle:cm:1", "day", D(2), now=NOW)
        self.assertIsNone(self.s.get("moodle:cm:1").planned)
        self.assertNotIn("plan", report.render_board(board(self.s), Settings(), "", NOW).split("Lab report")[1][:400])

    def test_something_already_overdue_can_be_planned_for_any_day_from_today(self):
        self.s.upsert(item("moodle:cm:5", "Late essay", at(-1, 23, 59)))
        self.assertEqual(under(board(self.s), "Overdue"), ["Late essay"])
        got = planner.move(self.s, "moodle:cm:5", "day", D(1), now=NOW)
        b = board(self.s)
        self.assertEqual((under(b, "Overdue"), under(b, "Tomorrow")), ([], ["Reading", "Late essay"]))
        self.assertIn("it was due Nov 17", got["says"])
        self.assertIn(">was due Tue 11:59 PM</time>", report.render_board(b, Settings(), "", NOW))

    def test_a_day_that_has_gone_by_is_not_somewhere_to_go(self):
        with self.assertRaisesRegex(planner.Refused, "That day has gone by"):
            planner.move(self.s, "moodle:cm:1", "day", D(-1), now=NOW)

    def test_one_of_your_own_changes_its_date_either_way_and_keeps_its_time(self):
        self.s.upsert(item("manual:1", "Dentist", at(1, 15, 0), kind="event", course="", timed=True))
        planner.move(self.s, "manual:1", "day", D(4), now=NOW)                        # later: fine, it's yours
        self.assertEqual(self.s.get("manual:1").due, at(4, 15, 0))
        planner.move(self.s, "manual:1", "day", D(0), now=NOW)                        # and earlier
        mine = self.s.get("manual:1")
        self.assertEqual((mine.due, mine.planned), (at(0, 15, 0), None))
        self.assertNotIn("plan", report.render_board(board(self.s), Settings(), "", NOW).split("Dentist")[1][:300])


class Bins(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))

    def test_onto_completed_and_back_out_onto_a_day(self):
        got = planner.move(self.s, "moodle:cm:1", "completed", now=NOW)
        self.assertIsNotNone(self.s.get("moodle:cm:1").done_at)
        self.assertEqual(got["says"], "Moved to Completed")
        planner.move(self.s, "moodle:cm:1", "day", D(1), now=NOW)                    # dragged back out, a day early
        back = self.s.get("moodle:cm:1")
        self.assertEqual((back.done_at, back.planned), (None, D(1)))

    def test_onto_archived_and_undo(self):
        got = planner.move(self.s, "moodle:cm:1", "archived", now=NOW)
        self.assertEqual(self.s.placements(), {"moodle:cm:1": "archived"})
        self.assertEqual([h.item.id for h in board(self.s).archived], ["moodle:cm:1"])
        self.s.restore(got["undo"])
        self.assertEqual(self.s.placements(), {})

    def test_undo_after_a_trip_through_completed_restores_everything(self):
        planner.move(self.s, "moodle:cm:1", "day", D(0), now=NOW)
        was = self.s.get("moodle:cm:1")
        got = planner.move(self.s, "moodle:cm:1", "completed", now=NOW)
        self.s.restore(got["undo"])
        now = self.s.get("moodle:cm:1")
        self.assertEqual((now.done_at, now.planned, now.rank), (None, was.planned, was.rank))


class AsThePageAsks(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))
        self.changed = []
        self.srv = ListServer(self.s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                              request_mail_scan=lambda d: None, on_change=lambda: self.changed.append(1))

    def test_a_move_and_its_undo(self):
        got = self.srv.move({"id": "moodle:cm:1", "to": "day", "day": D(0).isoformat()}, NOW)
        self.assertEqual((got["to"], got["day"], got["position"]), ("day", D(0).isoformat(), 1))
        self.assertEqual(self.s.get("moodle:cm:1").planned, D(0))
        self.srv.move_undo({"undo": got["undo"]})
        self.assertIsNone(self.s.get("moodle:cm:1").planned)
        self.assertEqual(len(self.changed), 2)

    def test_a_refusal_reaches_the_page_as_its_one_line(self):
        with self.assertRaisesRegex(ValueError, "It's due Friday, so it can't be planned for later than that."):
            self.srv.move({"id": "moodle:cm:1", "to": "day", "day": D(5).isoformat()}, NOW)
        self.assertEqual(self.changed, [])

    def test_nonsense_is_refused(self):
        for body in ({"id": "nope", "to": "completed"}, {"id": "moodle:cm:1", "to": "moon"},
                     {"id": "moodle:cm:1", "to": "day", "day": "soon"}, {"id": "moodle:cm:1", "to": "day"}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.srv.move(body, NOW)
        with self.assertRaises(ValueError):
            self.srv.move_undo({"undo": "x"})


class OnThePage(unittest.TestCase):
    def test_every_day_is_somewhere_to_drop_even_with_nothing_in_it(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))
        page = report.render_board(board(s), Settings(), "", NOW)
        for n in range(7):
            self.assertIn(f'data-day="{D(n).isoformat()}"', page)
        self.assertIn(f'<ul class="day empty" data-day="{D(0).isoformat()}"></ul>', page)
        self.assertIn(f'<ul class="day" data-day="{D(2).isoformat()}">', page)
        self.assertIn("all clear", page)                                              # and Now still says so

    def test_a_card_says_whether_it_is_yours_and_when_it_is_really_due(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))
        s.upsert(item("manual:1", "Dentist", at(1, 15, 0), kind="event", course="", timed=True))
        page = report.render_board(board(s), Settings(), "", NOW)
        self.assertIn(f'data-deadline="{D(2).isoformat()}"><label', page)
        self.assertIn(f'data-deadline="{D(1).isoformat()}" data-own="1"><label', page)

    def test_how_a_place_is_said(self):
        self.assertEqual([planner.say_place(1, 1), planner.say_place(2, 4), planner.say_place(11, 12)],
                         ["first of one", "second of four", "number 11 of 12"])
        self.assertEqual([planner.say_day(D(0), TODAY), planner.say_day(D(1), TODAY), planner.say_day(D(3), TODAY),
                          planner.say_day(D(9), TODAY)], ["Today", "Tomorrow", "Saturday", "Friday, Nov 27"])

    def test_a_database_from_before_plans_opens_and_takes_one(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Lab report", at(2, 23, 59)))
        got = s.get("moodle:cm:1")
        self.assertEqual((got.planned, got.rank), (None, None))
        s.plan("moodle:cm:1", D(1))
        self.assertEqual(s.get("moodle:cm:1").planned, D(1))
        self.assertIsInstance(datetime.fromisoformat(s.snapshot(["moodle:cm:1"])[0]["due"]), datetime)


if __name__ == "__main__":
    unittest.main()
