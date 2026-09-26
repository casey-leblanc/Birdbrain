# Round 2 context: Birdbrain list page

Status: **Direction locked.** Direction E was explicitly locked by the user on Sep 25, 2026, with one
correction. The other nine Round 1 directions are closed. This file governs every Round 2 artifact.

Source files: `design/round-1/E.html`, `design/round-1/capsules/E.md`, `design/round-1/capsules/EVIDENCE.md`.

## Human decisions at lock

1. **Lock E**: "very punchy and eye catching".
2. **Correction:** replace the course-code organisation with the Now / This week / Later organisation.
3. Reactions recorded for context: B "relaxed and calm"; A "bland".
4. Standing decisions from earlier in the project stay in force: the three time columns (Now, This week,
   Later), exams outrank quizzes, themes with dark and light modes, the Atkinson Hyperlegible family,
   Completed and Archived bins, add/edit your own items, course nicknames and colours, an app title
   ("Birdbrain").

## Locked capsule (E, original text)

**Premise.** A student's week is organised by course codes. The page groups everything under large course
codes, and the time bands become words inside each course.

**Fonts.** Atkinson Hyperlegible Next (roman, italic) with Atkinson Hyperlegible Mono for course codes.
Braille Institute of America / Applied Design Works, SIL Open Font License 1.1.

**Hierarchy and type.** Course codes 2.6rem Mono weight 300 as headings. Items 1.05rem; times 0.9rem.
Time-band words italic 0.95rem inside each course. Title 3.4rem/800. Next exam 1.5rem/700; next quiz 1.25rem/500.

**Colour.** Canvas #F2F4F8. Primary #1A1B22 (titles, about 55%). Secondary #4B3F8F (structure, about 20%).
Tertiary #62646E (times, labels, date, about 18%). Accent #A3261C (overdue, "2 overdue", the next-exam
label, the exam itself, about 7%). Four active text colours.

**Space.** Columns about 17rem wide with 3.5rem gaps; blocks don't break across columns. 4.5rem below the header.

**Signature.** Large, light, monospaced headings as the page's structure.

**Invariants.** Accent only for overdue work and exams.

**Prohibited normalisation.** Shrinking the monospaced headings back into small tags.

## How the correction applies (translation rules)

- The **large light Mono headings stay the page's structure**, but they now name the time bands:
  **Now**, **This week**, **Later** (secondary colour, Mono 300, about 2.6rem). The signature carries
  over; only the grouping changes.
- The **three bands are the three columns**, sitting directly on the canvas with 3.5rem gutters. No
  card panels: structure comes from type and space, as in E.
- Course codes move into each item as **Mono text in the secondary colour** at body-adjacent size (never
  shrunk into pill tags). Your per-course colours and nicknames recolour and rename this code text.
- Inside a band, sub-groups (Overdue, Today, Tomorrow, weekday names, Exams, Quizzes, Events,
  Assignments) are **italic tertiary labels**, the role E gave its band words.
- **Accent is only for overdue work and exams.** Exams: accent, bold title. Quizzes: one step lower,
  primary colour at semi-bold, with an italic "quiz" label. Assignments and events: primary, regular.
- Title "Birdbrain": 3.4rem, weight 800, tight tracking. The date (tertiary) and counts ("2 overdue" in
  accent bold, the rest tertiary) sit beside it.
- Next exam and next quiz: E's header pair. Label (accent for exam, tertiary for quiz), large title
  (exam 1.5rem/700, quiz 1.25rem/500), Mono code, tertiary time.

## Round 2 additions (required by a working interface; derived from the type)

- Controls are **typographic**: text buttons ("Add item", "Settings", "Details", "Edit", "Delete",
  "Close") with a visible focus outline. No icon glyphs; no SVG anywhere.
- Checkboxes are the one required mark: a small square in the tertiary colour, filled with the primary
  colour when ticked.
- Dialogs (Settings, Add/Edit item) use a surface one step off the canvas, with a hairline edge, because
  a modal needs a boundary over the page. Everything inside follows the same type roles.
- Themes: E's palette becomes the default theme, "Birdbrain" (light, with a dark counterpart). The other
  themes (Night study, High contrast, Dusk) are re-expressed in the same four roles: primary, secondary
  (structure), tertiary, accent. Every text role stays at or above 4.5:1.

## Controlled-skill review (Sep 25, 2026): user decisions

- **Targets:** every control has a 44 × 44 px hit area; the visible size is unchanged ("enlarge click areas only").
- **Type system tightened** ("tighten weights and sizes"):
  - Sans weights 400 / 600 / 800 only: regular text 400; quizzes, labels and buttons 600; exams, overdue
    work and the title 800. Mono weights 300 (headings) and 500 (codes).
  - Sizes on a 1.25 scale from 16px: 12.8 (details, codes, meta) / 16 (items, labels) / 20 (next quiz) /
    25 (next exam) / 31.25 (bins, dialog titles; band headings on phones) / 39 (band headings) / 48.8 (title).
    This supersedes the capsule's 3.4rem title and 2.6rem headings.
- Headings for Completed and Archived; counts read as "N items" to screen readers.

## Human corrections after the first real-page review (Sep 25, 2026)

- **Scan status sits directly under the title** (tertiary, 12.8px; accent when something needs attention).
- **Next exam and next quiz line up with each other**: they share the bands' column grid (next exam over
  Now, next quiz over This week), and their label, title and date rows align even when one title wraps.
- **Thin see-through bars separate the three columns**: 1px, secondary colour at 30% opacity, centred in
  the 3.5rem gutters and running the full height of the columns. When the columns stack, the bars turn
  horizontal between them. These are the page's only rules.

## Frosted glass layout (Sep 25, 2026): user decisions

- The user asked for a complete redesign modelled on their site, caseyleblanc.dev: its frosted glass,
  and the to-do list in three glass columns like the site's blog. Due dates get colour and accents
  by urgency.
- After seeing the previews, the user made **Frosted glass the default layout**. Direction E stays
  available as the **Classic** layout, unchanged and still governed by this file.
- **Every theme is kept** and becomes a colour scheme in the glass layout, each with matching free
  photos: a daytime photo in light mode and a night photo in dark mode. Forest (the site's own look
  and photo) is the new default theme; Birdbrain, Night study, High contrast and Dusk follow.
- Glass rules live in `birdbrain/glass.py`:
  - **Urgency heat, the same in every scheme:** overdue red, today amber, tomorrow yellow, and a
    white edge for items two or three days away.
  - **Exams and quizzes:** marked by a chip in the scheme's own colour, so "what" never competes
    with "how soon".
  - **Legibility:** the glass is darker than the site's so that all text is at least 4.5:1 over
    the brightest part of each photo. This was measured on real pixels for all ten scheme-and-mode
    combinations.

## Proof level

Direction locked. Round 2 artifact system: in progress (list page, dialogs, keyword window, tray icon).
