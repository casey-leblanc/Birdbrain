"""Repeating items of your own: "gym every mon wed 6pm", "rent monthly on the 1st". Plain rules, no AI.

What quick write (and the Repeats box in a card's details) understands:

    daily, every day                      every day
    weekdays, every weekday               Monday to Friday
    every mon wed, every monday and wed   those days each week
    weekly, every week                    each week, on the day the item is on
    monthly, every month                  each month, on the day of the month the item is on
    monthly on the 1st, every month on the 15th
                                          each month on that day (the last day, in a month too short for it)

A rule is kept on the card as a short string: "daily", "weekly:0,2" (Monday is 0), "monthly:1". There is only ever
one card of a repeating item on the list: ticking it off brings the next one (store.set_done), and unticking it
takes that one away again.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_WEEKDAY = re.compile(r"(mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?s?")
_NTH = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?")
_RULE = re.compile(r"daily|weekly:[0-6](,[0-6])*|monthly:([1-9]|[12]\d|3[01])")
HELP = "Try “every mon wed”, “daily”, “weekly” or “monthly on the 1st”."


def valid(rule: str) -> bool:
    return bool(_RULE.fullmatch(rule or ""))


def _weekday(word: str) -> int | None:
    m = _WEEKDAY.fullmatch(word)
    return DAYS.index(m.group(1)[:3].capitalize()) if m else None


def find(low: list[str], start: int) -> tuple[str, int] | None:
    """A repeat phrase beginning at word `start` of the lowercased words: (what it asks for, how many words it
    takes). What it asks for is a rule, or "weekly" / "monthly" when the day comes from the item's own date."""
    w = low[start].strip(",.;")
    rest = [x.strip(",.;") for x in low[start + 1:start + 9]]
    if w in ("daily", "everyday"):
        return "daily", 1
    if w == "weekdays":
        return "weekly:0,1,2,3,4", 1
    if w in ("weekly", "monthly") or (w == "every" and rest[:1] in (["week"], ["month"])):
        used = 1 if w != "every" else 2
        kind = "weekly" if w == "weekly" or rest[:1] == ["week"] else "monthly"
        after = rest[used - 1:]
        if kind == "monthly":   # "monthly on the 1st", "every month on 15th"
            n = 0
            if after[:1] == ["on"]:
                n = 2 if after[1:2] == ["the"] else 1
            if n and len(after) > n and (m := _NTH.fullmatch(after[n])) and 1 <= int(m.group(1)) <= 31:
                return f"monthly:{int(m.group(1))}", used + n + 1
            return "monthly", used
        if after[:1] == ["on"] and len(after) > 1 and (d := _weekday(after[1])) is not None:   # "weekly on fri"
            return f"weekly:{d}", used + 2
        return "weekly", used
    if w != "every" or not rest:
        return None
    if rest[0] == "day":
        return "daily", 2
    if rest[0] in ("weekday", "weekdays"):
        return "weekly:0,1,2,3,4", 2
    days, n = [], 0
    while n < len(rest):
        if (d := _weekday(rest[n])) is not None:
            days.append(d)
            n += 1
        elif rest[n] in ("and", "&") and n + 1 < len(rest) and _weekday(rest[n + 1]) is not None and days:
            n += 1
        else:
            break
    if not days:
        return None
    return "weekly:" + ",".join(str(d) for d in sorted(set(days))), 1 + n


def settle(asked: str, day: date) -> str:
    """Turn "weekly" or "monthly" into a full rule, using the day the item is on."""
    return f"weekly:{day.weekday()}" if asked == "weekly" else f"monthly:{day.day}" if asked == "monthly" else asked


def parse(text: str, day: date) -> str:
    """The rule a few typed words ask for, for an item on `day`; "" for no words (never). ValueError if the words
    aren't understood."""
    words = text.lower().replace(",", " ").split()
    if not words or words in (["never"], ["no"], ["none"], ["once"]):
        return ""
    for lead in (["repeats"], ["repeat"]):
        if words[:1] == lead:
            words = words[1:]
    got = find(words, 0) if words else None
    if not got or got[1] != len(words):
        raise ValueError("Couldn't read how often that repeats. " + HELP)
    return settle(got[0], day)


def _month_day(year: int, month: int, n: int) -> date:
    return date(year, month, min(n, calendar.monthrange(year, month)[1]))


def on_or_after(rule: str, day: date) -> date:
    """The first day the rule lands on, from `day` on."""
    if rule == "daily" or not valid(rule):
        return day
    kind, _, arg = rule.partition(":")
    if kind == "weekly":
        days = {int(x) for x in arg.split(",")}
        return next(day + timedelta(days=n) for n in range(7) if (day + timedelta(days=n)).weekday() in days)
    n = int(arg)
    this = _month_day(day.year, day.month, n)
    if this >= day:
        return this
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return _month_day(year, month, n)


def next_after(rule: str, day: date, today: date | None = None) -> date:
    """The next time after `day`, and never a day that has already gone by."""
    start = day + timedelta(days=1)
    return on_or_after(rule, max(start, today) if today else start)


def say(rule: str) -> str:
    """"Every Mon, Wed", "Every day", "Monthly on the 1st"; "" for no rule."""
    if not valid(rule):
        return ""
    kind, _, arg = rule.partition(":")
    if kind == "daily":
        return "Every day"
    if kind == "weekly":
        days = [int(x) for x in arg.split(",")]
        if days == [0, 1, 2, 3, 4]:
            return "Every weekday"
        if len(days) == 7:
            return "Every day"
        return "Every " + ", ".join(DAYS[d] for d in days)
    n = int(arg)
    nth = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"Monthly on the {n}{nth}"
