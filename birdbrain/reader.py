"""Plain rules that read a title or a few lines of text: is this something to do, what kind, and when.

No AI and nothing sent anywhere: a few word lists and ordinary calendar arithmetic. Rules get things wrong
sometimes, so every card lets the student say what it really is, and that answer sticks (store.say_kind).

Kinds: "assignment" (work to hand in), "test" (an assessment you sit; its level is "exam" or "quiz"), "event"
(something to attend or know about on a date), "none".

The rule that matters most: the word "test" alone doesn't make an exam. "Biochemical Testing - Oxidase Test" is a
lab, and "Exam 2 Review" is a study session. Exams are named plainly ("Exam 2", "Midterm", "Final", "Unit 3 Test").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ACTIONABLE_MIN = 0.55   # how sure a reading must be for an email or course-page snippet to go on the list

# --- what kind ------------------------------------------------------------------------------------------------
_QUIZ = re.compile(r"\bquiz(?:zes)?\b", re.I)
_EXAM = re.compile(r"\b(?:exams?|examinations?|midterms?|mid-terms?)\b", re.I)
# "Final" is the final exam unless it's the final version of some piece of work.
_FINAL = re.compile(r"\bfinals?\b(?!\s+(?:draft|project|paper|report|essay|presentation|submission|portfolio|version|"
                    r"grades?|reflection|proposal|lab|homework|assignment|copy|product|poster|review|deliverable))", re.I)
_TEST = re.compile(r"\btests?\b", re.I)
# Work that is about a test or a quiz without being one: "Exam 2 Review", "Practice Quiz", "Test corrections".
_ABOUT = re.compile(r"\b(?:review|practice|study guide|prep|preparation|corrections?|retake request|sign[- ]?up|"
                    r"registration|survey|feedback|answer key|solutions?|reflection|wrapper)\b", re.I)
# Where "test" names a lab procedure or a piece of homework, not an exam.
_WORK = re.compile(r"\b(?:labs?|laboratory|experiments?|exp|testing|pre-?lab|post-?lab|homework|hw|assignments?|"
                   r"worksheets?|reports?|exercises?|activity|activities|simulations?|virtual|discussions?|"
                   r"procedures?|problem sets?|essays?|projects?)\b", re.I)
_ASSIGN = re.compile(r"\b(?:assignments?|homework|hw|due|submit|submission|essays?|lab reports?|pre-?lab|post-?lab|"
                     r"projects?|problem sets?|worksheets?|drafts?|turn in|hand in)\b", re.I)
_EVENT = re.compile(r"\b(?:meetings?|lectures?|seminars?|office hours|presentations?|deadline|register|"
                    r"class (?:is )?(?:cancell?ed|moved)|review session|workshop|field trip)\b", re.I)


def level(title: str) -> str | None:
    """"exam", "quiz", or None if the title doesn't name an assessment the student sits."""
    if _ABOUT.search(title):
        return None
    if _QUIZ.search(title):
        return "quiz"
    if _EXAM.search(title) or _FINAL.search(title):
        return "exam"
    if _TEST.search(title) and not _WORK.search(title):
        return "exam"
    return None


def kind_of(title: str, module: str = "") -> str:
    """The kind of a titled item. `module` is where it came from: Moodle's activity type ("quiz", "assign", ...),
    "calendar" for a calendar entry, or "" for a title from another course site."""
    lvl = level(title)
    if module == "quiz":
        # Moodle's quiz activity also holds labs, check-ins and graded work, so the title decides. One that names
        # neither an assessment nor a piece of work is a quiz.
        if lvl:
            return "test"
        return "assignment" if (_WORK.search(title) or _ASSIGN.search(title) or _ABOUT.search(title)) else "test"
    if module in ("assign", "workshop", "turnitintooltwo", "lti"):
        return "test" if lvl == "exam" and not _WORK.search(title) else "assignment"   # a take-home exam
    if module == "":
        return "test" if lvl else "assignment"
    return "test" if lvl else "event"


def moodle_level(title: str, module: str, kind: str) -> str:
    """A test from Moodle's quiz activity is a quiz unless its title says exam, midterm, final or test."""
    if module == "quiz" and kind == "test":
        return "exam" if level(title) == "exam" else "quiz"
    return ""


# --- receipts ---------------------------------------------------------------------------------------------------
# Notices about work already done: a submission confirmation, a grade released. They aren't something due,
# whatever dates they mention (Gradescope's "Successfully submitted to HW3", "Your submission has been graded").
RECEIPT_RE = re.compile(
    r"\b(successfully submitted|submission (?:received|confirmation|receipt|successful|complete)"
    r"|(?:you|you've|you have|has been|have been|was) (?:successfully )?submitted"
    r"|thank you for (?:your )?submi|we(?:'ve| have) received your"
    r"|(?:grades?|feedback|scores?|results?)\b[^.\n]{0,40}?\b(?:released|posted|now available)"
    r"|(?:was|has been|have been) graded)", re.I)


def is_receipt(text: str) -> bool:
    return bool(RECEIPT_RE.search(text))


# --- when ------------------------------------------------------------------------------------------------------
_MON = "|".join(m[:3] for m in MONTHS)
_DAY = "|".join(w[:3] for w in WEEKDAYS)
_MONTH_DAY = re.compile(rf"\b({_MON})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", re.I)
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON})[a-z]*\.?(?:,?\s+(\d{{4}}))?\b", re.I)
# Numbers and weekday names only count next to a word that says a date is coming: an email's row also carries
# the day it arrived ("Wed 9/23"), which is not when anything is due.
_CUE = r"(?:due|by|on|until|before|deadline(?: is)?|closes?|ends?|is|this|next)\s+(?:on\s+|by\s+)?"
_NUMERIC = re.compile(rf"\b{_CUE}(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?\b", re.I)
_WEEKDAY = re.compile(rf"\b({_CUE})((?:{_DAY})[a-z]*)\b", re.I)
_RELATIVE = re.compile(r"\b(day after tomorrow|tomorrow|tonight|today)\b", re.I)


def _this_or_next_year(today: date, month: int, day: int, year: str | None) -> date | None:
    try:
        if year:
            y = int(year)
            return date(y + 2000 if y < 100 else y, month, day)
        d = date(today.year, month, day)
        return date(today.year + 1, month, day) if d < today - timedelta(days=60) else d   # "January 12" in December
    except ValueError:
        return None


def _weekday(today: date, name: str, cue: str) -> date:
    w = [d[:3].lower() for d in WEEKDAYS].index(name[:3].lower())
    monday = today - timedelta(days=today.weekday())
    if cue.lower().startswith("next"):
        return monday + timedelta(days=7 + w)
    return today + timedelta(days=(w - today.weekday()) % 7)


def find_date(text: str, today: date) -> tuple[date | None, bool]:
    """The day the text is about and whether it was stated outright (a month and a day) rather than worked out from
    "Friday" or "tomorrow". `today` is the day the text was written."""
    months = [m[:3].lower() for m in MONTHS]
    if m := _MONTH_DAY.search(text):
        d = _this_or_next_year(today, months.index(m.group(1)[:3].lower()) + 1, int(m.group(2)), m.group(3))
        if d:
            return d, True
    if m := _DAY_MONTH.search(text):
        d = _this_or_next_year(today, months.index(m.group(2)[:3].lower()) + 1, int(m.group(1)), m.group(3))
        if d:
            return d, True
    if m := _NUMERIC.search(text):
        d = _this_or_next_year(today, int(m.group(1)), int(m.group(2)), m.group(3))
        if d:
            return d, True
    if m := _RELATIVE.search(text):
        word = m.group(1).lower()
        return today + timedelta(days=2 if word.startswith("day after") else 1 if word == "tomorrow" else 0), False
    if m := _WEEKDAY.search(text):
        return _weekday(today, m.group(2), m.group(1)), False
    return None, False


# --- a few lines of text: an email, a snippet of a course page ----------------------------------------------------
@dataclass
class Judgment:
    actionable: float            # 0..1: how sure the rules are that this is something to do
    kind: str                    # assignment | test | event | none
    due: date | None
    confidence: float | None
    needs_review: bool           # the card says "check": the day was worked out, not stated
    note: str = ""


def judge(text: str, today: date | None = None, sent: date | None = None) -> Judgment:
    """Read `text` for what it is and when. `sent` anchors relative days in emails ("due tomorrow" means the day
    after it was sent)."""
    anchor = sent or today or date.today()
    text = text.strip()[:4000]
    if is_receipt(text):   # work already handed in or marked: never a new deadline
        return Judgment(0.0, "none", None, None, False, "receipt")
    kind = ("test" if level(text) else "assignment" if _ASSIGN.search(text)
            else "event" if _EVENT.search(text) else "none")
    due, stated = find_date(text, anchor)
    return Judgment(actionable=0.7 if kind != "none" else 0.1, kind=kind, due=due, confidence=None,
                    needs_review=due is None or not stated, note="" if stated else "day worked out")


def is_actionable(j: Judgment) -> bool:
    return j.actionable >= ACTIONABLE_MIN and j.kind != "none"


def at_end_of(day: date) -> datetime:
    return datetime.combine(day, time(23, 59))
