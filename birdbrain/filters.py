"""Which stored items the list shows.

Two things get moved out of the list into its "Archived" section:

- Keyword matches: any item whose title or course contains one of the
  user's hidden keywords (case-insensitive), e.g. "Absence Documentation".
- Duplicates: an email, Outlook calendar entry, or course-page snippet that
  repeats an activity Moodle already lists with an exact date, e.g. Moodle's
  "Due on Saturday: ..." reminder emails, or the course-page text next to a
  quiz that the quiz itself already covers.

Nothing is deleted; removing a keyword brings its items straight back. The student's own call on one item beats
both rules: they can archive any item themselves, or show one the rules would archive.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from store import Item

# Moodle activities and calendar events with dates straight from Moodle.
STRUCTURED = ("moodle:cm:", "moodle:idx:", "moodle:cal:")

_STOP = set("""
a an and or of for to in on at by with from this that these is are be will your you all
due re fw fwd via hi dear please regarding amp nbsp s moodle moodle4
am pm today tomorrow fall spring summer
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
monday tuesday wednesday thursday friday saturday sunday mon tue tues wed thu thurs fri sat sun
""".split())
COURSE_CODE = re.compile(r"\b([A-Z]{2,4})\s?(\d{4})\b")   # "CHEM 1212", "BE 2352"
SAME_ACTIVITY = 0.6     # share of the Moodle title's words found in the other item
SAME_DAY_MATCH = 0.3    # lower bar when both fall on the same day
MAX_DATE_GAP = 21       # days; a course page may state a stale or tentative date


@dataclass
class Hidden:
    item: Item
    reason: str


def _text(i: Item) -> str:
    return html.unescape(f"{i.title} {i.course} {i.detail}")


def _tokens(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", html.unescape(s).lower())
            if w not in _STOP and not (w.isdigit() and len(w) == 4)]


def _codes(s: str) -> set[str]:
    return {a + b for a, b in COURSE_CODE.findall(html.unescape(s))}


def _containment(moodle_title: str, other_words: list[str]) -> float:
    """Fraction of the Moodle title's words that appear in the other item.
    A truncated word ("Analys") counts for the full one ("Analysis")."""
    want = set(_tokens(moodle_title))
    if not want:
        return 0.0
    have = set(other_words)
    hits = sum(1 for w in want if w in have or any(len(h) >= 4 and w.startswith(h) for h in have))
    return hits / len(want)


# Other course sites with their own exact dates (Gradescope, McGraw Hill Connect). Their items are real work, so they
# only count as a copy of a Moodle item under the strict same_assignment() test, never the looser one for emails.
SITES = ("gradescope:", "mcgraw:")


def same_assignment(item: Item, other: Item) -> bool:
    """Strictly the same piece of work on two sites: the same course code, due within two days, and titles that match
    once spacing and punctuation are ignored ("HW 3" and "HW3") or share nearly all their words."""
    codes = _codes(f"{item.course} {item.title}")
    if not (codes and item.due and other.due) or not codes & (_codes(other.course) | _codes(other.title)):
        return False
    if abs((item.due.date() - other.due.date()).days) > 2:
        return False
    plain = lambda t: re.sub(r"[^a-z0-9]", "", html.unescape(t).lower())
    return plain(item.title) == plain(other.title) or (
        len(set(_tokens(other.title))) >= 2 and _containment(other.title, _tokens(item.title)) >= .8)


def duplicate_of(item: Item, structured: list[Item]) -> Item | None:
    if item.id.startswith(STRUCTURED) or item.source == "manual" or not item.due:
        return None  # things you added yourself are never treated as duplicates
    if item.id.startswith(SITES):
        fits = [s for s in structured if same_assignment(item, s)]
        return fits[0] if len(fits) == 1 else None
    words, codes = _tokens(_text(item)), _codes(_text(item))
    best, best_score = None, 0.0
    for s in structured:
        s_codes = _codes(s.course) | _codes(s.title)
        if codes and s_codes and not codes & s_codes:
            continue  # different course (e.g. BE 2352 "Exam 1" vs CE 2450 "Exam 1")
        gap = abs((item.due.date() - s.due.date()).days)
        if gap > MAX_DATE_GAP:
            continue
        sim = _containment(s.title, words)
        same_course = (item.course and item.course == s.course) or bool(codes & s_codes)
        if (sim >= SAME_ACTIVITY and len(set(_tokens(s.title))) >= 2) \
                or (gap == 0 and sim >= SAME_DAY_MATCH) \
                or (gap == 0 and same_course and item.kind == s.kind):
            score = 2 * sim + (0.5 if gap == 0 else 0)  # an exact title beats a same-day neighbour
            if score > best_score:
                best, best_score = s, score
    return best


def keyword_hit(item: Item, keywords: list[str]) -> str | None:
    hay = html.unescape(f"{item.title} {item.course}").lower()
    return next((k for k in keywords if k.strip() and k.strip().lower() in hay), None)


def split(items: list[Item], keywords: list[str], pool: list[Item] | None = None,
          placement: dict[str, str] | None = None) -> tuple[list[Item], list[Hidden]]:
    """Return (shown, archived). Duplicates are judged against `pool`
    (defaults to `items`), so a new email can be checked against everything stored. `placement` is the student's
    own call per item id ("archived" or "shown"), which comes first."""
    structured = [i for i in (pool if pool is not None else items) if i.id.startswith(STRUCTURED)]
    placement = placement or {}
    shown, hidden = [], []
    for i in items:
        how = placement.get(i.id)
        if how == "archived":
            hidden.append(Hidden(i, "you archived it"))
        elif how == "shown":
            shown.append(i)
        elif k := keyword_hit(i, keywords):
            hidden.append(Hidden(i, f"keyword “{k}”"))
        elif d := duplicate_of(i, structured):
            hidden.append(Hidden(i, f"duplicate of “{html.unescape(d.title)}” ({d.due:%b %d})"))
        else:
            shown.append(i)
    return shown, hidden
