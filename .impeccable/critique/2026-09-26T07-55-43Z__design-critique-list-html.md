---
target: the landing page (main list)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\casey\\OneDrive\\writing and plans\\Documents\\GitHub\\Birdbrain\\design\\critique\\list.html"
target_fingerprint: "sha256:8808bf2fe17942a934500cf7abe3dc4a3b18f0d51a03fea5ff3673cfa114d458"
target_path: "C:\\Users\\casey\\OneDrive\\writing and plans\\Documents\\GitHub\\Birdbrain\\design\\critique\\list.html"
timestamp: 2026-09-26T07-55-43Z
slug: design-critique-list-html
closed: true
---
Method: dual-agent (A: ad722bc18487a54ca · B: a98c7ab12a6f35f9d)

## Critique: Birdbrain list page (Frosted glass, day and night)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | "Updated 2:25 PM" is clear, but "Keyword matching (no TypeSafe key)" sits in the main status slot and reads like an error |
| 2 | Match System / Real World | 3 | Now / This week / Later fits how students think, but "Archived" and "keyword" are system words |
| 3 | User Control and Freedom | 2 | "Moved to Completed" has no Undo; putting an item back means scrolling to a collapsed bin at the bottom |
| 4 | Consistency and Standards | 2 | Later groups by type while the other columns group by time; count chips look pressable but aren't; the white "soon" edge looks like a selection |
| 5 | Error Prevention | 3 | Two-click delete; ticking an item off is easy to reverse |
| 6 | Recognition Rather Than Recall | 3 | Titles link to Moodle but give no cue until hover; courses show as codes unless nicknamed |
| 7 | Flexibility and Efficiency | 1 | No shortcuts, filtering or search; two tab stops per item; the counts don't filter |
| 8 | Aesthetic and Minimalist Design | 2 | Urgency is signalled five ways; the next exam and next quiz appear twice above the fold; 11 font sizes |
| 9 | Error Recovery | 3 | A failed tick reverts with "Couldn't save: …"; sign-in problems turn the status line red |
| 10 | Help and Documentation | 2 | Hints exist in the bins and Settings, but none explain the jargon |
| **Total** | | **24/40** | **Acceptable** |

**Apple HIG checker:** 70/100, "fix before release". Every text passes 4.5:1 over the real photo pixels (lowest: Show/Hide at 4.71, Add item and Settings at 4.87). There are three target failures:
- **Window buttons:** only 46×27 of their 46×32 is clickable, because the top-edge resize strip covers the top 5px.
- **"Details":** its hit area is 53×43, one pixel short of 44.
- **Item title links:** 22px tall on one line.

### Design Specificity Verdict

**Design review:** the skin is authored but the skeleton is generic. The authored parts:
- photo glass tuned by measurement, not guesswork;
- lowercase headings and italic dates from your site;
- Atkinson Hyperlegible;
- the rule that the exam colour and the urgency colours never swap roles;
- the Now / This week / Later model;
- plain copy.

The structure underneath is a stock dashboard: a big centred wordmark, a row of three equal "stat" panels, then three columns of cards with count badges. The generic tells:
- **Card ends:** the coloured stripe on the left of every tile.
- **Badges and pills:** dark count badges beside headings, and seven different chip styles.
- **Course dot:** grey by default, so it tells you nothing until you pick a colour.
- **Bevels:** on every container.
- **Hover:** every tile slides and rises, even though a tile isn't a button.

**Detector:** 26 findings by day and 27 at night, and it agrees with the review on the main problem:
- **Nested cards (8):** the date, next-exam and next-quiz panels, three columns and two bins, all inside the frame. The layering is intentional (it's the "Three Panes Rule") but it is the density problem.
- **Cramped padding (4):** the count badges, which have no vertical padding (borderline, but real).
- **Width animation (1):** the scrollbar.
- **Drift from `DESIGN.md` (13):** 7 font sizes not in its type scale, 3 colours, 1 radius, and 2 font flags. One font flag is a false positive (it read "Birdbrain Sans" as "sans"); the other flags Windows' icon font in the window buttons.

**Overlay:** the detector did run inside the page, but in a headless browser, so no overlay is visible to you.

### Overall Impression

The contrast work is genuinely strong: over 5.4:1 on the brightest photo pixels everywhere. What undermines it is quantity: three layers of glass, five urgency signals and eleven type sizes.

On a 1366×768 laptop the header takes 369px, and the first item sits 474px down, so 62% of the screen passes before anything that's due. The frame covers 1325 of 1440px, so the "lookout" photo is only a 58px border. The biggest opportunity is to subtract: fewer layers, one urgency signal set, and a shorter header.

### What's Working
- **Measured glass.** Every text passes on real photos in both modes, so the translucency never costs readability.
- **What-versus-when colour.** Lavender says exam and the heat colours say when, and urgency is always stated in words too. Colour-blind students lose nothing.
- **The time model and voice.** Italic day labels and calm empty states ("Nothing due right now.") match how a student plans the week.

### Priority Issues

**[P1] Too much glass, and urgency said five ways.**
- **What:**
  - Each item sits in a glass tile, in a glass column, in a glass frame, all with bevels.
  - Urgency repeats as a card end, a tint, a chip, a dot and a count.
  - Every row slides and lifts on hover, and hovering an overdue tile clears its red tint.
- **Why it matters:** this is where the cramped, generated feel comes from. HIG puts glass on controls, not stacked on content.
- **Fix:**
  - Remove the card ends, including the white "soon" edge.
  - Make tiles clear at rest, with a faint wash only on hover.
  - Keep the red tint for overdue only, and stop hover from clearing it.
  - Drop the default grey course dot and the outlined "soon" chip.
  - Don't slide or lift rows; they aren't buttons.
- **Command:** `/impeccable distill`, then `/impeccable quieter`

**[P1] The header strip buries the list.**
- **What:**
  - The wordmark and the three panels take 369px.
  - The date panel is 164px tall for one row of counts.
  - The next exam and next quiz repeat items already in the columns.
- **Why it matters:** in a tool you glance at, what's due today falls below the fold.
- **Fix:**
  - Put the date and counts on one line.
  - Make the wordmark smaller, or move it into the title bar.
  - Show the next quiz only when it isn't already in Now.
  - Aim for a header of 160px or less.
- **Command:** `/impeccable layout`

**[P1] Keyboard and screen-reader users lose their place.**
- **What:** after every tick, and on the 20-second auto-refresh, the list is rebuilt, which throws away keyboard focus. There is no Undo.
- **Why it matters:** a keyboard user loses their place mid-list, and a mistaken tick has no quick undo.
- **Fix:**
  - Put focus back on the next row.
  - Skip auto-refresh while focus is inside the list.
  - Add an Undo to the toast for 6 seconds.
- **Command:** `/impeccable harden`

**[P2] Spacing is off-grid and tight inside tiles.**
- **What:**
  - Tiles have 9px top and bottom padding, 5px from title to meta, and 12.8px meta text.
  - The frame uses 30px padding and 25/20px gaps; about 60% of values are off a 4-point grid.
- **Why it matters:** it looks cramped even though the gaps between groups are fine.
- **Fix:** move to an 8-point rhythm:
  - frame padding 32px, gutters 24px;
  - tiles 12px by 16px;
  - group labels 24px above and 8px below.
- **Command:** `/impeccable layout`

**[P2] The type scale is muddy.**
- **What:** 11 sizes, most important text small:
  - the date chip, the most important text on a tile, is 12.8px;
  - headings are 24px against 16px titles;
  - several sizes are only 0.8px apart, too close to tell apart.
- **Why it matters:** hierarchy can't lead the eye when neighbouring sizes look the same.
- **Fix:**
  - Cut to five sizes: 13, 16, 20, 28, plus the wordmark.
  - Raise meta text to 13px.
  - Course code weight 700 → 600 so the date chip leads.
- **Command:** `/impeccable typeset`

### Persona Red Flags

**Alex (impatient power user)**
- No shortcuts, even for "new item" or "scan now".
- The counts can't be clicked to filter.
- 30+ tab stops to reach Later.
- The header strip has to be scrolled past.
- No Undo.

**Sam (keyboard, screen reader, low vision)**
- Focus is wiped after a tick and on every auto-refresh.
- "Next exam" and the date are paragraphs, not headings, so heading navigation skips them.
- Meta text is 12.8px.
- Title links are 22px tall.
- The status line isn't announced when it changes.

**A stressed student between classes (1366×768 laptop)**
- Sees the logo, then red, then only three items in Now.
- The same quiz appears twice.
- "no TypeSafe key" reads as if something is broken.

### Minor Observations
- Later sorts by type, so an October 4 event appears under an October 14 exam.
- The Completed pulse plays off-screen.
- At a 900px-wide window, Later's tiles stretch to 720px with empty space on the right.
- The count badges' numbers sit flush against their top and bottom edges.
- The scrollbar animates its width.

### Questions to Consider
- If the photo only shows as a 58px border around a 76%-opaque slab, is it earning its place? Should the glass shrink and let the view in?
- Why say "overdue" five ways but give no way to act on "2 overdue"?
- Would students rather see Later in date order, like the other two columns?
