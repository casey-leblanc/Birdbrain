"""How much a day holds, in a few words: "3 due · 1 exam". And whether that makes it a heavy day.

A day's heading says its load once it holds more than one card (one card says it all by itself). A heavy day ahead
is called out once, early: two or three days before, "Thursday is heavy: 4 due · 1 exam" (notices.py).

A day is heavy at four points: a thing to hand in or a quiz is one, an exam is two. Things to attend are counted in
the words but not in the weight.
"""
from __future__ import annotations

HEAVY = 4


def count(items, level_of) -> dict:
    """{"due": n, "exam": n, "quiz": n, "event": n} for a day's cards. `level_of(item)` says "exam", "quiz" or None."""
    got = {"due": 0, "exam": 0, "quiz": 0, "event": 0}
    for i in items:
        level = level_of(i)
        got["exam" if level == "exam" else "quiz" if level == "quiz" else "event" if i.kind == "event" else "due"] += 1
    return got


def words(items, level_of) -> str:
    """"3 due · 1 exam"; "" for a day with fewer than two cards."""
    if len(items) < 2:
        return ""
    c = count(items, level_of)
    parts = [f"{c['due']} due" if c["due"] else "",
             f"{c['exam']} exam{'s' if c['exam'] > 1 else ''}" if c["exam"] else "",
             f"{c['quiz']} quiz{'zes' if c['quiz'] > 1 else ''}" if c["quiz"] else "",
             f"{c['event']} event{'s' if c['event'] > 1 else ''}" if c["event"] else ""]
    return " · ".join(p for p in parts if p)


def heavy(items, level_of) -> bool:
    c = count(items, level_of)
    return c["due"] + c["quiz"] + 2 * c["exam"] >= HEAVY
