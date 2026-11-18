# Birdbrain experimental: checklist

Work on the `birdbrain-experimental` branch, based on Birdbrain 1.1.2. `[x]` done and proven, `[~]` blocked
(see NEEDS-HUMAN.md), `[ ]` to do.

## 1. Foundation

- [x] 1. Branch, this checklist, NEEDS-HUMAN.md, version 2.0.0 in `birdbrain/version.py`
- [x] 2. Offline unit tests in `tests/` for the store, dates, filters and the list page
- [x] 3. Build workflow: tests, build, packaged self-test, real start, pre-release `exp-<version>-<sha7>`, `--build-info`
- [x] 4. No AI: Jev and TypeSafe removed; plain rules; a lab with "test" in its name is an assignment
- [x] 5. "What is this?": correct a card's kind once, sticks for the series
- [ ] 6. Fixes: one running copy, scan after sleep and stay awake, 11:59 PM and no-time dates, sign-in card
- [ ] 7. Self-update from `exp-` pre-releases, no token, SHA-256 checked
- [ ] 8. Header removed: list fills the window, one status dot, one menu
- [ ] 9. README for students, with the LSU sentence (also on the welcome page and in About)

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
