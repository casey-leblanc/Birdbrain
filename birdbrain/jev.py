"""TypeSafe Jev judgments: is this text something to do, what kind, and when.

Follows TypeSafe's date-extraction cookbook: Jev only *reads* (picks month,
day, weekday, ...) and ordinary code does the calendar math. Classification
and date questions go out together, so each text costs one API request.

Without an API key a keyword fallback is used so the app still runs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from config import ACTIONABLE_MIN, REVIEW_BELOW, Settings

log = logging.getLogger(__name__)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ABSENT = "The text does not state this, or it is not this kind of date."

KIND_CRITERIA = {
    "assignment": "Work the student must hand in: homework, essay, lab report, project, problem set, submission.",
    "test": "An assessment the student sits: exam, midterm, final, quiz, test.",
    "event": "Something to attend or be aware of on a date: class meeting, lecture change, presentation, office hours, deadline to register.",
    "none": "Not a task, assessment or event for the student (newsletters, receipts, general info).",
}


@dataclass
class Judgment:
    actionable: float            # Noul, 0..1
    kind: str                    # assignment | test | event | none
    due: date | None
    confidence: float | None
    needs_review: bool
    note: str = ""


def _questions(role: str, today: date):
    from typesafe_sdk import Choice, Noul

    years = [str(y) for y in range(today.year - 1, today.year + 3)]
    return {
        "actionable": Noul(instructions=(
            "Does this text tell a university student about something they must do, "
            "submit, sit, or attend on or by a specific day (an assignment, test, exam, "
            "quiz, or dated event)? Marketing, receipts and general news are not."
        )),
        "kind": Choice(instructions="What kind of item is this for the student?", criteria=KIND_CRITERIA),
        "mode": Choice(
            instructions=(f"How is {role} written? 'absolute' = a calendar date naming the month; "
                          "'relative' = relative to today (tomorrow, next Friday); 'none' = not stated."),
            criteria={"absolute": None, "relative": None, "none": None},
        ),
        "month": Choice(instructions=f"If {role} is absolute, which month?",
                        criteria={m: None for m in MONTHS} | {"none": ABSENT}),
        "day": Choice(instructions=f"If {role} is absolute, which day of the month (1-31)?",
                      criteria={str(d): None for d in range(1, 32)} | {"none": ABSENT}),
        "year": Choice(instructions=f"If {role} is absolute, which year? 'none' if no year is written.",
                       criteria={y: None for y in years} | {"none": "No year stated.",
                                                           "other": "A year outside this list."}),
        "day_anchor": Choice(
            instructions=f"If {role} is relative, which day is meant?",
            criteria={"today": None, "tomorrow": None, "day_after": "The day after tomorrow.",
                      "weekday": "A named weekday such as 'Friday' or 'next Tuesday'.", "none": ABSENT},
        ),
        "weekday": Choice(instructions=f"If {role} names a weekday, which one?",
                          criteria={w: None for w in WEEKDAYS} | {"none": ABSENT}),
        "week_offset": Choice(
            instructions=(f"If {role} names a weekday: 'next' if it says next week / next <day>; "
                          "'current' if it says this <day>; 'none' for a bare weekday."),
            criteria={"current": None, "next": None, "none": ABSENT},
        ),
    }


def _resolve_weekday(today: date, weekday: str, offset: str) -> date:
    w = WEEKDAYS.index(weekday)
    monday = today - timedelta(days=today.weekday())
    if offset == "next":
        return monday + timedelta(days=7 + w)
    if offset == "current":
        return monday + timedelta(days=w)
    return today + timedelta(days=(w - today.weekday()) % 7)


def _assemble(parts: dict, today: date) -> tuple[date | None, list[float], str]:
    """Deterministic calendar math over Jev's readings (cookbook `assemble`)."""
    def c(name):
        return parts[name]["choice"]

    confs = [parts["mode"]["confidence"]]
    mode = c("mode")
    if mode == "absolute":
        confs += [parts[p]["confidence"] for p in ("month", "day", "year")]
        month, day, year = c("month"), c("day"), c("year")
        if month not in MONTHS or not day.isdigit():
            return None, confs, "absolute date incomplete"
        m, d = MONTHS.index(month) + 1, int(day)
        try:
            if year.isdigit():
                return date(int(year), m, d), confs, ""
            resolved = date(today.year, m, d)
            if resolved < today - timedelta(days=60):   # "January 12" read in December
                resolved = date(today.year + 1, m, d)
            return resolved, confs, ""
        except ValueError:
            return None, confs, f"impossible date {month} {day}"
    if mode == "relative":
        confs.append(parts["day_anchor"]["confidence"])
        anchor = c("day_anchor")
        if anchor in ("today", "tomorrow", "day_after"):
            return today + timedelta(days={"today": 0, "tomorrow": 1, "day_after": 2}[anchor]), confs, ""
        if anchor == "weekday" and c("weekday") in WEEKDAYS:
            confs += [parts["weekday"]["confidence"], parts["week_offset"]["confidence"]]
            return _resolve_weekday(today, c("weekday"), c("week_offset")), confs, ""
        return None, confs, "relative day not read"
    return None, confs, "no date stated"


class Jev:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        if settings.api_key:
            try:
                from typesafe_sdk import TypeSafeClient
                self._client = TypeSafeClient(api_key=settings.api_key,
                                              model=settings.typesafe_model, timeout=30.0)
            except Exception:
                log.exception("TypeSafe client unavailable; using keyword fallback")
        else:
            log.warning("No TYPESAFE_API_KEY set; using keyword fallback instead of Jev")

    @property
    def online(self) -> bool:
        return self._client is not None

    def judge(self, text: str, role: str = "the due date or event date",
              today: date | None = None, sent: date | None = None) -> Judgment:
        """Classify `text` and extract its date. `sent` anchors relative dates
        in emails ("due tomorrow" means the day after it was sent)."""
        today = today or date.today()
        anchor = sent or today
        text = text.strip()[:4000]
        if not self._client:
            return _keyword_judge(text, anchor)
        try:
            state = {"today": anchor.strftime("%A, %B %d, %Y"), "text": text}
            answers = self._client.system_one(state=state, questions=_questions(role, anchor)).answers
        except Exception:
            log.exception("Jev request failed; using keyword fallback for this item")
            return _keyword_judge(text, anchor)

        parts = {k: {"choice": getattr(a, "choice", None), "confidence": getattr(a, "confidence", None)}
                 for k, a in answers.items()}
        actionable = float(getattr(answers["actionable"], "noul", 0.0) or 0.0)
        due, confs, note = _assemble(parts, anchor)
        confs.append(parts["kind"]["confidence"])
        usable = [x for x in confs if x is not None]
        conf = min(usable) if usable else None
        return Judgment(
            actionable=actionable,
            kind=parts["kind"]["choice"] or "none",
            due=due,
            confidence=conf,
            needs_review=due is None or conf is None or conf < REVIEW_BELOW,
            note=note,
        )

    def classify_title(self, title: str, module: str = "") -> str:
        """Moodle already gives exact dates; only ask what kind of item it is
        (a 'quiz' module named 'Midterm' is a test, a 'page' named 'Essay 2' is not)."""
        if module == "quiz":
            # Moodle's quiz activity also holds surveys, check-ins and graded work named
            # "... Assignment", so the title decides. One that names neither is a quiz.
            if _TEST_RE.search(title):
                return "test"
            return "assignment" if _ASSIGN_RE.search(title) else "test"
        if module in ("assign", "workshop", "turnitintooltwo", "lti"):
            base = "assignment"
        else:
            base = "event"
        if not self._client:
            return "test" if _TEST_RE.search(title) else base
        # A submission activity is homework unless it's really a take-home exam;
        # never let it become an "event".
        options = ("assignment", "test") if base == "assignment" else ("test", "event")
        try:
            from typesafe_sdk import Choice
            res = self._client.system_one(
                state={"moodle_activity_type": module or "calendar event", "title": title},
                questions={"kind": Choice(instructions="What kind of item is this for the student?",
                                          criteria={k: KIND_CRITERIA[k] for k in options})},
            )
            a = res.answers["kind"]
            return a.choice if a.choice in options and (a.confidence or 0) >= REVIEW_BELOW else base
        except Exception:
            log.exception("Jev classify failed")
            return base

    @staticmethod
    def is_actionable(j: Judgment) -> bool:
        return j.actionable >= ACTIONABLE_MIN and j.kind != "none"


# --- keyword fallback (no API key) -------------------------------------------
_TEST_RE = re.compile(r"\b(exam|midterm|mid-term|final|quiz|test)\b", re.I)
# Exam or quiz, for items that are tests (report.test_level and Moodle's quiz activities).
EXAM_RE = re.compile(r"\b(exams?|midterms?|mid-terms?|finals?|tests?)\b", re.I)
QUIZ_RE = re.compile(r"\bquiz(zes)?\b", re.I)
_ASSIGN_RE = re.compile(r"\b(assignment|homework|due|submit|submission|essay|lab report|project|problem set)\b", re.I)
_EVENT_RE = re.compile(r"\b(meeting|lecture|seminar|office hours|presentation|deadline|register)\b", re.I)


def _keyword_judge(text: str, today: date) -> Judgment:
    from dateutil import parser as dparser

    kind = ("test" if _TEST_RE.search(text) else "assignment" if _ASSIGN_RE.search(text)
            else "event" if _EVENT_RE.search(text) else "none")
    due = None
    m = re.search(r"(?:" + "|".join(m[:3] for m in MONTHS) + r")[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?", text, re.I)
    if m:
        try:
            due = dparser.parse(m.group(0), default=datetime.combine(today, time())).date()
        except (ValueError, OverflowError):
            pass
    elif re.search(r"\btomorrow\b", text, re.I):
        due = today + timedelta(days=1)
    elif re.search(r"\b(today|tonight)\b", text, re.I):
        due = today
    return Judgment(actionable=0.7 if kind != "none" else 0.1, kind=kind, due=due,
                    confidence=None, needs_review=True, note="keyword fallback")
