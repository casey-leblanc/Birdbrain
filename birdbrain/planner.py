"""Where a card sits, and where the student may move it.

A card sits under the day it's due unless the student has planned it for another day ("I'll do it then"), and within
a day in time order unless the student has put that day's cards in an order of their own. Both are theirs: a scan
never changes them.

Moves, as the page asks for them (move()):

- within a day: the day's cards take the order they were dropped in. A new card later joins by its time.
- to Completed or Archived, and back out onto a day.
- to another day. Something from one of your sites keeps its deadline: planned for an earlier day it sits under that
  day and still says when it's really due; it can't be planned for later than its deadline, and move() refuses with
  the reason. Something already overdue can be planned for any day from today. One of your own items simply changes
  its date, either way.

A plan for a day that has gone by is forgotten: the card is back where its deadline puts it.
"""
from __future__ import annotations

from datetime import date, datetime

from store import Item, Store

ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")


class Refused(ValueError):
    """A move that can't be made, with the one line that says why."""


def planned_for(i: Item, today: date) -> date | None:
    """The day the student planned this for, while that day hasn't gone by and still differs from its due date."""
    if i.planned and i.planned >= today and i.planned != i.due.date():
        return i.planned
    return None


def day_of(i: Item, today: date) -> date:
    """The day a card sits under."""
    return planned_for(i, today) or i.due.date()


def ordered(items: list[Item]) -> list[Item]:
    """A day's cards in the order to show them: the student's order where they made one, and anything they haven't
    placed (a new card) slotted in by its time."""
    placed = sorted((i for i in items if i.rank is not None), key=lambda i: i.rank)
    for new in sorted((i for i in items if i.rank is None), key=lambda i: i.due):
        earlier = [n for n, other in enumerate(placed) if other.due <= new.due]
        placed.insert(earlier[-1] + 1 if earlier else 0, new)   # after the last card that isn't later than it
    return placed


def say_day(day: date, today: date) -> str:
    gap = (day - today).days
    return "Today" if gap == 0 else "Tomorrow" if gap == 1 else f"{day:%A}" if 1 < gap < 7 else f"{day:%A}, {day:%b} {day.day}"


def say_place(position: int, total: int) -> str:
    """"second of four"."""
    numbers = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
    nth = ORDINALS[position - 1] if position <= len(ORDINALS) else f"number {position}"
    return f"{nth} of {numbers[total - 1] if total <= len(numbers) else total}"


def _day_cards(store: Store, day: date, today: date, without: str) -> list[Item]:
    places = store.placements()
    return ordered([i for i in store.open_items()
                    if i.id != without and places.get(i.id) != "archived" and day_of(i, today) == day])


def move(store: Store, item_id: str, to: str, day: date | None = None, before: str | None = None,
         now: datetime | None = None) -> dict:
    """Move a card: to "completed", to "archived", or to a "day" (before the card `before`, or last). Returns what
    to say, where it ended up, and a snapshot that undoes it. Raises Refused with the reason if it can't go there."""
    now = now or datetime.now()
    today = now.date()
    item = store.get(item_id)
    if not item or not item.due:
        raise Refused("That item isn't on your list any more.")
    if to in ("completed", "archived"):
        undo = store.snapshot([item_id])
        if to == "completed":
            store.set_done(item_id, True)
        else:
            store.set_placement(item_id, "archived")
        return {"ok": True, "says": f"Moved to {to.capitalize()}", "to": to, "undo": undo}
    if to != "day" or day is None:
        raise Refused("That isn't somewhere a card can go.")
    if day < today:
        raise Refused("That day has gone by.")
    there = _day_cards(store, day, today, without=item_id)
    undo = store.snapshot([item_id] + [i.id for i in there])
    deadline = item.due.date()
    note = ""
    if item.source == "manual":
        if day != deadline:
            store.set_due(item_id, datetime.combine(day, item.due.time()))
        store.plan(item_id, None)
    elif day == deadline:
        store.plan(item_id, None)
    elif day > deadline >= today and item.due >= now:
        when = say_day(deadline, today)
        raise Refused(f"It's due {when.lower() if when in ('Today', 'Tomorrow') else when}, so it can't be planned for later than that.")
    else:   # an earlier day; or any day from today for something already overdue
        store.plan(item_id, day)
        note = f"; still due {say_day(deadline, today)}" if deadline >= today else f"; it was due {deadline:%b} {deadline.day}"
    if item.done_at:
        store.set_done(item_id, False)
    if store.placements().get(item_id) == "archived":
        store.set_placement(item_id, None)
    at = next((n for n, other in enumerate(there) if other.id == before), len(there))
    order = [i.id for i in there[:at]] + [item_id] + [i.id for i in there[at:]]
    store.set_ranks({i: float(n) for n, i in enumerate(order)})
    where = say_day(day, today)
    return {"ok": True, "to": "day", "day": day.isoformat(), "position": at + 1, "of": len(order), "undo": undo,
            "says": f"Moved to {where}{note}", "heard": f"Moved to {where}, {say_place(at + 1, len(order))}{note}"}
