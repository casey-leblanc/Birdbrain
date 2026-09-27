---
target: the list page (Focus layout)
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\casey\\OneDrive\\writing and plans\\Documents\\GitHub\\Birdbrain\\design\\critique\\focus.html"
target_fingerprint: "sha256:f335e56a1fa8a9b9277064c19cdc329fcd542e994522e2186bfb0fbb26ef52d3"
target_path: "C:\\Users\\casey\\OneDrive\\writing and plans\\Documents\\GitHub\\Birdbrain\\design\\critique\\focus.html"
timestamp: 2026-09-27T02-18-48Z
slug: design-critique-focus-html
---
Method: dual-agent (A: design review · B: detector and browser evidence, run in isolation)

## Critique: Birdbrain list page, Focus layout (day and night; Glass checked for consistency)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Before the first scan the header shows "0 overdue 0 today 0 tomorrow" while every column says "Waiting for the first scan" |
| 2 | Match System / Real World | 3 | Later shows absolute dates only, no "in 19 days" |
| 3 | User Control and Freedom | 3 | Undo, Ctrl+Z and archive-not-delete are strong; one noisy item can't be hidden without inventing a keyword |
| 4 | Consistency and Standards | 2 | Exams use the overdue red; course colour is text in Focus but a dot in Glass; Focus has no heat colours |
| 5 | Error Prevention | 3 | A course colour that fails contrast is warned in Settings but still applied to the list |
| 6 | Recognition Rather Than Recall | 3 | Title links look identical to plain titles |
| 7 | Flexibility and Efficiency | 1 | Only Ctrl+Z and Esc; no add/settings shortcut, no course filter, 41 tab stops for 15 items |
| 8 | Aesthetic and Minimalist Design | 3 | Calm, but the spacing pushes today's work below the fold; next exam can appear three times |
| 9 | Error Recovery | 3 | Plain, precise messages; the Add item error sits under Notes, not next to Title |
| 10 | Help and Documentation | 3 | Excellent Settings hints; nothing on the list explains title links or Archived |
| **Total** | | **27/40** | **Acceptable, close to Good** |

### Design Specificity Verdict
LLM: Glass is unmistakably Birdbrain; Focus at rest is category-interchangeable (sage canvas, light 39px date, lowercase light headings, text-link actions). Identity appears only in special states (perched bird, flapping mark, tick-off flight and landing). Focus dropped the Cardinal/Oriole/Goldfinch heat colours and uses one red for both late and exam.
Detector: 55 findings on focus.html, 56 on focus-night.html, 6 each on list.html and list-night.html; almost all design-system-color advisories from theme-picker swatches inside the closed Settings sheet. Real signal: #8FD3FF on "CHEM 1212" (matches the 1.38:1 contrast failure). False positives: cramped-padding on the closed sheet and .tabs; "h1 uses sans" (it is Birdbrain Sans); the Fluent icon font on window controls. Minor real drift: 12px and 3px radii, the 1.953rem phone date, night muted #A0B2A6 undocumented.
Overlays: headless only; in-page detector reported no anti-patterns. Glass photos don't load under file://, so Glass contrast was not re-measured.

### Overall Impression
Focus is honest, legible and well built, but its generous spacing puts what's due today below the fold on a normal laptop. Biggest opportunity: pull today's work up and give it the room.

### What's Working
- Honest states: first-scan never claims all clear; all-clear gives the next thing; Undo returns focus to the next row.
- Measured contrast: lowest themed text 6.19:1 by day, 8.05:1 at night; visible focus ring; 44px ticks and header actions; ARIA tabs in Settings.
- Restraint and voice: one family at five sizes, words not icons, specific calming copy.

### Priority Issues
- [P1] Today's work below the fold at 1280x720, 1366x768, 1536x864 (columns start ~y=490; only the 2 overdue items show; Glass starts at y=279). Cause: top padding 72-136px, .top margin-bottom 80px, lone .next band with 96px. Fix: fold next exam/quiz into one line under the counts, cut the header margin to ~40px, target >=5 Now rows visible at 1366x768, consider a wider Now column. Command: /impeccable layout
- [P1] Course colour used as text in Focus: CHEM 1212 #8FD3FF on #E8EEE6 = 1.38:1 (11:1 at night, fine as a Glass dot). Fix: show course colour as a dot (--cc) and keep the code in --struct. Command: /impeccable polish
- [P1] One accent means both overdue and exam: a midterm 19 days out is as loud as a lab 2 days late; today/tomorrow get no heat. Fix: accent for overdue only; exams get their own quieter mark (struct 700 + outlined chip, or an exam token per theme); a light cue for due-today times. Command: /impeccable colorize
- [P2] Header counts contradict first-scan state. Fix: hide counts until the first scan (scanned is already known). Command: /impeccable harden
- [P2] Keyboard and screen-reader gaps: checkbox names lack due date/urgency; Add item type choices 32-39px wide; field borders 1.5:1 (<3:1); title links give no new-tab cue. Fix: aria-describedby to the row meta, 44px min-width on .seg choices, darker field borders, dotted underline + "opens in a new tab". Command: /impeccable audit

### Persona Red Flags
- Alex: no shortcuts for Add item, Settings, column jumps or Scan now; no course filter; no single-item hide; 2 tab stops per row.
- Sam: checkbox names lack due date; CHEM 1212 at 1.38:1; field edges 1.5:1; accent vs struct differ by 1.08:1 in luminance, so red-green colour-blind users can't tell an overdue date from a course code.
- Student between classes at 1366x768: sees date, counts, Exam 1 and two overdue items, then must scroll for today; red exams read as overdue; tonight's quiz looks like next week's homework.

### Minor Observations
- Later's first row starts 28px above Now and This week (no group label).
- Bins don't sit on the column grid.
- At 900px Later's sub-lists fill across then down, scrambling date order.
- All-clear "Next up: Exam 1 on Sunday" repeats the callout above it.
- Uncoloured courses show a filled swatch instead of the dashed empty ring.
- Custom theme card looks identical to Forest until customised.
- The 39px date is the largest element though it's what the student already knows.

### Questions to Consider
- What if the headline were the answer ("2 overdue, 3 due today") and the date a small label?
- Is Focus a calmer Birdbrain, or a different product sharing the data?
- Should column width follow urgency: a wide Now, a narrow Later rail?
