# Birdbrain experimental: checklist

Work on the `birdbrain-experimental` branch, based on Birdbrain 1.1.2. `[x]` done and proven, `[~]` blocked
(see NEEDS-HUMAN.md), `[ ]` to do.

## 1. Foundation

- [x] 1. Branch, this checklist, NEEDS-HUMAN.md, version 2.0.0 in `birdbrain/version.py`
- [x] 2. Offline unit tests in `tests/` for the store, dates, filters and the list page
- [ ] 3. Build workflow: tests, build, packaged self-test, real start, pre-release `exp-<version>-<sha7>`, `--build-info`
- [ ] 4. No AI: Jev and TypeSafe removed; plain rules; a lab with "test" in its name is an assignment
- [ ] 5. "What is this?": correct a card's kind once, sticks for the series
- [ ] 6. Fixes: one running copy, scan after sleep and stay awake, 11:59 PM and no-time dates, sign-in card
- [ ] 7. Self-update from `exp-` pre-releases, no token, SHA-256 checked
- [ ] 8. Header removed: list fills the window, one status dot, one menu
- [ ] 9. README for students, with the LSU sentence (also on the welcome page and in About)

### Decisions

- Version 2.0.0: the list, the keys and the data all change shape from 1.1.2, so it is a new major version.
