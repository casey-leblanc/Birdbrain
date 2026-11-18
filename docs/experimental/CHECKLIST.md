# Birdbrain experimental: checklist

Work on the `birdbrain-experimental` branch, based on Birdbrain 1.1.2. `[x]` done and proven, `[~]` blocked
(see NEEDS-HUMAN.md), `[ ]` to do.

## 1. Foundation

- [x] 1. Branch, this checklist, NEEDS-HUMAN.md, version 2.0.0 in `birdbrain/version.py`
- [x] 2. Offline unit tests in `tests/` for the store, dates, filters and the list page
- [x] 3. Build workflow: tests, build, packaged self-test, real start, pre-release `exp-<version>-<sha7>`, `--build-info`
- [x] 4. No AI: Jev and TypeSafe removed; plain rules; a lab with "test" in its name is an assignment
- [x] 5. "What is this?": correct a card's kind once, sticks for the series
- [x] 6. Fixes: one running copy, scan after sleep and stay awake, 11:59 PM and no-time dates, sign-in card
- [x] 7. Self-update from `exp-` pre-releases, no token, SHA-256 checked
- [x] 8. Header removed: list fills the window, one status dot, one menu
- [x] 9. README for students, with the LSU sentence (also on the welcome page and in About)

### Decisions

- Version 2.0.0: the list, the keys and the data all change shape from 1.1.2, so it is a new major version.
- Jev's replacement is `reader.py`: word lists and calendar arithmetic. "test" alone is an exam only when no lab
  or homework word is near it; "review", "practice" and "corrections" are never the exam itself.
- Kinds are no longer cached per title, so a wrong answer saved by 1.1.2 is replaced at the next scan.
- A day worked out from "Friday" or "tomorrow" keeps the "check" tag; a stated month and day doesn't.
- Experimental builds are tagged `exp-<version>-<commit>` and published with `--prerelease --latest=false`, so
  v1.1.2 stays the release students see. The first one, `exp-2.0.0-c4a2b05`, built, self-tested and started clean.
- "What is this?" is a small "?" on each scraped card, shown on hover or focus like Archive, so cards keep their
  height. It moves into the details sheet in project 2. A series answer needs a course code: an email's lead-in
  ("Reminder: …") is not a series.
- Browser tests live in `tests/ui` (their own job on GitHub, on Linux, before the Windows build). Locally:
  `BIRDBRAIN_TEST_CHROME=/opt/pw-browsers/chromium python3 -m unittest discover tests/ui`.
- An item with no real time shows no time on its card (never a stand-in "11:59 PM"); a screen reader hears "no time
  given". 11:59 PM on Moodle, Gradescope and Connect is a real deadline and is shown.
- The morning wake task from the private fork was not ported: nothing here needs the PC woken yet.
- The header's date, counts and "next exam / next quiz" strip are gone, not hidden. The day groups already say
  what is overdue, today and tomorrow; an exam or quiz two or more days off carries an "in N days" tag instead.
- The status dot keeps its words hidden when the last scan simply worked ("Updated 10:32 AM."), and shows them
  while scanning, on a problem, on hover or focus, and for anything else worth reading ("Not scanned yet").
- The dot and menu sit in the padding at the top corner, so they take no height from the list. Add item is in the
  menu until quick write replaces it in project 2. M opens the menu. Quit from the menu asks "Click again to quit".
- A unit test runs the page's scripts through `node --check`: one stray bracket leaves a list that draws but does
  nothing.
- The updater follows only `exp-` pre-releases and needs no token (the repository is public). Checked here against
  the real GitHub: found the newest build, downloaded it, SHA-256 matched. `--install-update <zip>` installs a
  build from a file; the build on GitHub uses it to do a real update on Windows before anything is published.
- The root README is the short student page; `birdbrain/README.md` is the full guide and ships in the zip. A test
  holds the LSU sentence to the agreed wording in both, on the welcome page and in Settings › About.

## 2. Quick write and labels

- [x] 1. Personal items in the store, with a label; a 1.1.2 database opens and keeps everything
- [x] 2. The reader for what a student types (`quickwrite.py`), with a table test of 60+ phrases
- [x] 3. Quick write in the window: Space, chips for what was understood, Enter, Ctrl+Enter, Esc, Backspace
- [x] 4. Space no longer ticks: X ticks, E opens details, ? shows every key; arrows and J/K across day groups
- [ ] 5. Fill in later: the details sheet for personal cards, and (locked) for scraped ones with "What is this?"
- [ ] 6. System-wide hotkey on Windows (Ctrl+Alt+Space), changeable, with a small always-on-top quick write
- [ ] 7. Labels: four to begin with plus your own, tags on cards, filter by tag, Settings › Labels
- [ ] 8. Keyboard-only UI test of the whole thing, under a second of the page's own time

### Decisions

- An item stores its label's id ("life"), not its name, so renaming a label in Settings renames it everywhere.
- "No time" for your own items stays 11:59 PM in the database, as in 1.1.2, so old items need no conversion.
- Quick write's reader runs in Python only (`quickwrite.py`); the page asks it as you type. One set of rules, one
  table test (88 phrases), and nothing to keep in step with a second copy in the page's script.
- A weekday means the coming one, today included ("wed" typed on a Wednesday is today); "next fri" is the Friday
  of next week. A bare hour needs "at" ("at 5" is 5 PM, "at 9" is 9 AM); "11:59" is the deadline, 11:59 PM.
- A type word at the start sets the kind but stays in the title ("Quiz ch 5", "Exam 2"), and the app's own rules
  have the last word: "midterm review session" is not an exam. `#appointment` makes it an event, so it is never
  shown as overdue homework.
- An unknown `#label`, or an `@class` that could be two courses, is left in the title rather than guessed.
- What you type stays in the line as you typed it; the chips under it say how it was read. Backspace right after a
  word that was read hands that word back as plain text (the next Backspace deletes as usual). This replaces "on an
  empty line": the words never leave the line, so there is nothing to put back into it.
- Your own items now record whether their time is real (`timed`), so "11:59pm" typed on purpose is shown, while
  an item with only a day still shows none. Items made before 2.0 keep the old rule (11:59 PM meant no time).
- A card with a label shows the label in place of the "Personal" tag.
- Space opens quick write from anywhere outside a text field, including on a focused tick box or button; inside
  the corner menu, Space presses the menu item as menus do.
- `?` opens its own sheet with every key, in two columns so it fits one screen; Settings › App points to it.
  Until the details sheet arrives (item 5), E opens the edit form for your own items and "What is this?" for others.
