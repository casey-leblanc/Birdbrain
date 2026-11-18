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
- [x] 5. Fill in later: the details sheet for personal cards, and (locked) for scraped ones with "What is this?"
- [x] 6. System-wide hotkey on Windows (Ctrl+Alt+Space), changeable, with a small always-on-top quick write
- [x] 7. Labels: four to begin with plus your own, tags on cards, filter by tag, Settings › Labels
- [x] 8. Keyboard-only UI test of the whole thing, under a second of the page's own time

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
- One details sheet for every card (the old Add item form, with a Label field). A card from one of your sites opens
  it locked; its Type is the one live control and is "What is this?". The separate dialog is gone. The "?" on a
  card, E, and a double-click all open it.
- The shortcut opens its own small window (`/quick`), not the main one. Its page is the quick write line alone and
  saves through the same action. Where Birdbrain has no window of its own (no WebView2), the list comes up with
  quick write open instead. A shortcut that can't be had never replaces one that works.
- The build on GitHub checks Windows gives Birdbrain Ctrl+Alt+Space, then presses it and requires quick write to
  open with no error logged. What the small window looks like, and that typing lands in it, needs a person.
- A label's name is always drawn in the theme's text colour and its colour as a small square with a thin outline,
  so a tag reads in every look whatever colour is picked. Settings also names the looks a colour blends into
  (under 2:1 against the page), checked against every Focus theme, day and night, and the Glass panels.
- Search arrives in project 4. Until then `#` and `@` open a one-line filter; a word without either filters by
  title. The filter is the page's own and stays on while the list rebuilds.
- Undo for a deleted label is in the Settings pane itself: the message at the bottom of the list sits behind
  Settings, where it can't be clicked.
- The keyboard-only test listens for any mouse event on the page and fails if one happens. It times the page's own
  share (opening the line, and saving and showing the card) and requires under a second in total; a second test
  types at about forty words a minute and requires Space-to-saved in under five seconds.

## 3. Drag and motion

- [x] 1. One motion vocabulary (`motion.py`): shared timings and a spring, three levels, only transform and opacity
- [x] 2. Dragging with pointer events: pick up, lift, follow, neighbours part, spring into place, Esc, edge scroll
- [x] 3. Where a card can go: reorder in its day, Completed, Archived, an earlier day; a refused drop says why
- [x] 4. Undo after every drop, and Ctrl+Z
- [x] 5. The same with the keyboard: M, arrows, Enter, Esc, D, A, and what a screen reader hears
- [x] 6. Glass: ripple of light, sheen, the tick, the drop-in, smooth re-flow; Subtle drops ripple and sheen
- [x] 7. Focus: the same feedback, quieter
- [x] 8. Smooth with 200 cards: no long frame, no layout work in the drag loop
- [x] 9. UI tests with real pointer events for items 2 to 5
- [x] 10. A screen recording for the owner, in Glass night and Focus day, with motion on and off

### Decisions

- The level in force is on the page as `data-motion`. With nothing chosen it follows the system (reduce motion
  means Off); a level chosen in Settings wins over the system either way.
- Hover colours no longer fade: only transform and opacity are animated anywhere, in styles and in script. The
  scan bar fills by scaling, the "just added" mark fades an outline drawn once, and a bin opens to its full height
  at once while what is inside fades and slides in.
- Loops and marks that set their own pace (the bird's wings, the scanning dot, the scan bar, the bin's pulse, the
  "just added" mark) keep their own times; everything else uses the five shared ones.
- A card's place is kept as two things of the student's own, which a scan never touches: `planned` (the day they
  mean to do it) and `rank` (its order in that day). The deadline itself never moves for anything from a site.
- A card from a site can't be planned later than it is due: the drop is refused with one line and a shake. One that
  is already overdue can be planned for any day from today. A card the student added just changes its date.
- Completed and Archived come up as a dock at the bottom of the window while a card is carried, because the bins
  themselves are usually off screen in a long list. The Overdue group and the Later column aren't places to drop.
- Days with nothing in them are drawn (hidden) for the next week, and come out as drop zones while a card is carried.
- On a card, M now picks it up (anywhere else M still opens the menu). D sends it to Completed; A was already Archive.
- Touch: press and hold (about a third of a second) picks a card up; a finger that moves first is scrolling.
- The list is no longer rebuilt whole. `rebuild()` in the page changes only what differs, and cards keep their
  identity; the list's clicks are handled by one listener each on the list. That is what keeps a drop under 50 ms
  with 200 cards, and it means focus and running motion survive a refresh.
- "No long frame" is tested as: no long task (over 50 ms of script or layout) while dragging, dropping and
  filtering 200 cards, and not one layout read while the card only follows the pointer (the page counts its own
  reads in `window.birdbrainMeasures`). Frame times in headless Chromium without a GPU say little, so only a loose
  bound (250 ms) is put on them.
- Cards outside the window aren't laid out or painted until they're scrolled to (`content-visibility`), so a list
  of hundreds costs what the cards on screen cost. This came from the build machine, where showing 200 cards again
  after a filter took one 52 ms step; it now takes about 3 ms here. The test's limit was left where it was.
- Ripple and sheen are Glass at Full only (`lively()` in `feel.py`), and tuned by five CSS variables at the top of
  that file. The ripple is three discs scaled and faded; the sheen is one disc moved under the pointer: nothing is
  repainted to make either.
- Whenever the list changes (a scan, an add, a filter), what was already there glides to its new place and what is
  new fades in; only cards near the window are animated.
- The film is made by `tests/ui/preview_recording.py` from the frames Chromium hands over (Playwright's own
  recorder wrote nothing here), put together with ffmpeg. It runs 50 seconds, not 40: every kind of move is in it.
  It is sent to the owner and not committed; NEEDS-HUMAN 6 says what is theirs to approve and where to tune it.
- The keys sheet is wider (780px) so the two new keys still fit on one screen.
- The spring is worked out from a damped spring (about 5% past, then settled) and written as CSS `linear()`;
  Safari 16 and anything else without `linear()` gets a `cubic-bezier` with a little overshoot.

## 4. Phone and extras

One test for everything here: does it help a student see what to do and start on it, with no setup?

- [x] 1. Settings in plain order: Sign-ins, Look, Notifications, Keys, Labels, Updates, About; then Advanced, closed
- [x] 2. Notifications on the PC, on with no setup: one short line; morning, evening, and before a test
- [x] 3. Telegram under Advanced, off by default, no AI: one-time code, Done buttons, texting adds an item
- [x] 4. Search and commands: Ctrl+K or `/`
- [x] 5. Snooze: S on a card, until tomorrow, next week or a day; it comes back by itself
- [x] 6. Repeating personal items from quick write
- [x] 7. Each day says its load; a heavy day ahead is called out once
- [x] 8. First run in under a minute: choose LSU, one sign-in window, the list shows what it's reading
- [x] 9. Report a problem: a zip with everything personal removed, shown before it's saved, never uploaded
- [x] 10. The states in between, each in one line
- [x] 11. Backup: export and import personal items and labels
- [x] 12. Access: keyboard, focus, contrast, names, text size
- [x] 13. Anything else worth it, one at a time

### Decisions

- Settings lists its sections down the side instead of along the top: eight names don't fit a row, and a list
  lets Advanced sit last and apart, under a rule. Each part of Advanced is folded shut with one line saying what
  is inside. Site addresses, Full rescan, Older emails, Hidden keywords and Files moved there; course colours and
  nicknames moved into Labels ("Your classes"); Sounds moved into Notifications.
- Notifications: `notices.py` decides what to say and when, and keeps what it has said in the store; `toast.py`
  shows it, one each half minute at most, so several that come due together (after the PC wakes) never arrive as
  a batch. The old "N new items" notification with three lines, and the "N item(s) due today" one at the first
  scan of the day, are gone: the one-line "New: …" and the morning list replace them.
- The morning list says nothing when nothing is due or overdue. A list missed while the PC was off still comes up
  to four hours late, then waits for tomorrow.
- An exam is said 24 hours before it, a quiz three hours before it closes: one reminder per test, said again only
  if the test moves.
- Short names lead with the class ("Chem Exp 15 Quiz"), by its nickname if the student gave one.
- A click on a notification is heard by wrapping the tray icon's own message handler (pystray shows the
  notification but doesn't report the click). The build machine checks the wrapping took on real Windows; nobody
  has clicked a real one (NEEDS-HUMAN 7).
- The very first scan finds everything, so it says nothing as "new".
- Telegram: `telegram.py` and `vault.py` are ported from the private fork (neither had anything of the other
  assistant in it); `phone.py` is written new, since the old one was built around a plan made by AI. What the
  student texts the bot goes through `quickwrite.read`, the same as the Space bar.
- The bot's token is not a setting at all: it lives only in Windows Credential Manager (or the Mac keychain, to be
  tried by the Mac testers). Where there is no such store, Telegram can't be turned on, rather than the token
  going in a file. The packaged app's self-test writes, reads back and removes a throwaway credential on the
  build machine's real Windows.
- The link code is six digits, made when the token is saved, good once, and replaced after five wrong tries.
- The phone gets every notice even if PC notifications are turned off: turning one off shouldn't silence the other.
- The Telegram part of Settings asks the app where the setup has got to when it is opened, and every few seconds
  while a code is waiting, so the page moves to "linked" by itself.
- A real bot has not been tried here (no Telegram account, and Telegram is out of reach from the build): the
  stand-in in `tests/test_phone.py` plays Telegram. NEEDS-HUMAN 8 has the steps.
- Search and commands is the same line that `#` and `@` already opened, grown: Ctrl+K or `/` open it empty. It
  filters the list as you type, as before, and lists the commands that answer under it (`commands.py`).
- A command is chosen automatically only when the typed text starts its name or one of its other words and is at
  least two letters, so searching for a word that happens to sit inside a command's name still just filters.
- Commands so far: scan, quick write, add, settings, new label, night, day, Glass, Focus, show everything,
  Completed, Archived, notifications, sign in, keys, updates, Telegram, quit. Later items add their own.
- A key pressed in the instant after a window closes (Esc then `/`) was being swallowed by the box that had just
  closed; shortcuts now ignore a focused box inside a closed window.
- Snooze keeps one date on the card ("hidden until"). The day it is reached the card shows "back from snooze";
  the day after, nothing. A scan never changes it.
- A snoozed card waits in Archived ("Snoozed until Friday", Wake it now) rather than in a fourth bin.
- "Never past a deadline without saying so" is done by not letting it happen at all: a day after the deadline is
  brought forward to the deadline's day, the choice says so before it is picked and the toast says so after.
  Something due today can't be snoozed; overdue work can sleep to any day.
- "Next week" is the coming Monday (on a Sunday, the Monday after tomorrow's).
- A sleeping card is left out of notifications, like anything else that isn't on the list.
- S on a card snoozes; anywhere else S is still Settings. The card's Snooze button is hidden until the card is
  pointed at or focused, like Archive, so cards stay clean.
- The list now also rebuilds itself when the date changes, so cards come back from snooze (and Today becomes
  yesterday) without anything else having to happen.
- Repeating items: the rule is a short string on the card (`daily`, `weekly:0,2`, `monthly:1`). There is only ever
  one card of a repeating item: ticking it makes the next (in the store, so the PC, a drag to Completed and the
  phone all do it), unticking takes that one away again. A late tick never makes a card for a day gone by.
- With no day typed, a repeating item starts the first time it comes round (today, if today is one of its days and
  its time hasn't passed). "weekly" and "monthly" alone take their day from the item's own date.
- "Every other week" and the like are not read; the words stay in the title rather than being half understood.
- The Repeats box in Details takes the same words as quick write, instead of a second way of saying it.
- A day's load is drawn beside its name by the stylesheet (from `data-load`), so the heading's own text stays the
  day's name for screen readers' "Thursday, second of four" and for everything that looks a day up by name.
  A day with one card says nothing: the card says it.
- Heavy is four points: a thing to hand in or a quiz is one, an exam two; things to attend don't count. A heavy
  day is said once, two or three days ahead, with the morning list (so not at all if that is turned off), and its
  load is bold on the page. Today and tomorrow are never "heavy ahead": the morning and evening lines cover them.
- First run: LSU is chosen already (it is who the app is for), which fills in `https://moodle.lsu.edu` and the
  school Outlook; the address boxes only appear for "Another school". Known schools live in `schools.py`. The
  page still says, right there, that Birdbrain is not LSU's.
- Enter on step 1 continues and Enter on step 2 starts, so a keyboard gets from the welcome page to the sign-in
  window in two presses. The sign-in window was already one window for every site.
- While the first scan runs, the empty list itself says what is being read (the same words as the status dot),
  kept current as the scan goes.
- The welcome page had no browser test before; `tests/ui/test_first_run.py` is one.
- Report a problem (`trouble.py`) has no way to send anything: it imports nothing that talks to a network, and a
  test holds it to that. The zip holds about.txt (version, system, card counts as numbers), settings.txt, the last
  400 lines of the log, and the student's own words if any.
- Scrubbing is by two means: every title, course name and note in the store is replaced wherever it appears, and
  the rest goes by shape (emails, web addresses and hosts, bot tokens and long keys, @names, "for A. Teacher",
  course codes, the computer's user name and home folder). Settings that say where the student studies or what
  they hide are blanked whole. Rules can miss something oddly written, so the window shows every line and asks the
  student to look before saving, and what is saved is exactly what was shown.
- The zip goes to Downloads and is shown there, selected; nothing opens an email or a web page.
- The states in between (`states.py`): a failed scan of a site is one of three things, each with its own line:
  needs sign-in; couldn't be reached (check the connection or the address); or answered but couldn't be read (the
  page may have changed: check for updates). "Scan failed (see log)" is gone.
- When every site is out of reach at once, that is the computer being offline: it is said once ("You're offline.
  Your list is as it was…"), the dot stays calm rather than red, no sign-in card or notification follows, and the
  next scan comes in five minutes instead of an hour.
- The list's own in-between states were already there and are now held by tests: nothing due today, nothing left
  for today, all clear with what is next, and the first scan saying what it is reading.
- Backup (`backup.py`) holds only what no scan can bring back: the student's own items (open and done), their
  labels, and their classes' colours and nicknames. It is plain JSON in Downloads. Import adds what isn't there:
  an item with the same title, time and label is left alone, so importing twice changes nothing, and what is
  already set on the new computer is never overwritten.
- Access was done by measuring first. Contrast is measured in the browser against what is really drawn behind
  each piece of text (the page is photographed with its text made invisible, so glass over a photo counts as it
  looks): `tests/ui/contrast.py`. All 28 looks (5 Glass and 9 Focus themes, day and night) passed for the list,
  Settings and quick write once the measuring was right; the lowest found was 5.6:1. A test deliberately makes
  text unreadable to show the audit catches it. Nothing had to be recoloured.
- Every control, window and picture already had a name, and every tab stop already showed a ring; both are now
  held by tests that walk the list and every Settings section with Tab.
- Keyboard: one test does a whole sitting with no mouse. On a card, M moves the card, so the menu from a card is
  Ctrl+K (which runs everything the menu has) or M after leaving the card.
- Text size is new: Smaller, Standard, Larger, Largest (90, 100, 115, 130%), in Settings › Look. The page's sizes
  were already in rem, so it is one number on the root.
- Commands now also answer to the plain word a student would try ("keys", "completed", "archived", "updates",
  "telegram", "everything").
- Item 13, added: **start with Windows**. Reminders only come while Birdbrain runs, so a student who has to
  remember to open it gets none: that fails "no setup". The welcome page offers it already ticked; Settings ›
  Notifications turns it on or off. It is one value under the student's own Run key, pointing at this copy with
  `--background`, and only an installed copy on Windows offers it. The packaged self-test writes, reads back and
  removes a throwaway value in the build machine's real registry. Mac comes with project 5.
- Item 13, added: **a tray menu that matches the window**. Open, Quick write, Scan now, Sign in, Quit. Full rescan,
  the keyword window, the settings file and the log are in Settings › Advanced now, so the separate keyword window
  (`keyword_dialog.py`) is gone.
- Item 13, considered and left out, each for failing the test "does it help a student see what to do and start on
  it, with no setup": a countdown on cards ("in 2 h": the page would need redrawing every minute to stay true, and
  the time is already on the card); an "in progress" state (a third state to keep up by hand); a weekly summary
  notification (the heavy-day call and the morning list already say it, and one more notification is one more to
  ignore); a calendar file export (it has to be imported somewhere, which is setup).
- Not drawing off-screen cards (project 3) now applies only to a long list, over 80 cards. On a short list it
  gained nothing, and a card the browser hadn't drawn yet could report no text for a moment, which two tests met
  on the slower build machine.

## 5. Mac and test pack

- [ ] 1. One platform module with a Windows half and a Mac half; both halves' pure logic tested on Linux
- [ ] 2. The window and the menu bar: window, menu bar icon, Dock icon reopens, Cmd for Ctrl, the standard menu
- [ ] 3. `build.py` makes `Birdbrain.app`, ad-hoc signed, as a `.dmg` and a zip, for Apple silicon and Intel
- [ ] 4. Mac jobs in the workflow: tests, build, self-test, start, a second copy hands over; files join the pre-release
- [ ] 5. The self-updater replaces the `.app` and restarts it, proven on GitHub's Mac
- [ ] 6. Not signed yet, said plainly; what the owner needs to sign both platforms
- [ ] 7. `TESTING.md`: the one guide for student testers
- [ ] 8. `CHANGES.md`; release notes link both; the README covers Mac install
- [ ] 9. A last check of the whole branch
- [ ] 10. One short message to the owner

### Decisions

- The platform module is `system.py`, which is whichever of `system_win.py` and `system_mac.py` fits. The feature
  modules (`vault`, `autostart`, `power`, `instance`, `toast`, `updater`) keep their own rules and ask `system`
  for the part that differs; a test fails if any other module reaches for the system directly.
- The Mac half talks to the Mac through its own command-line tools (`security`, `caffeinate`, `afplay`,
  `osascript`, `open`, `ditto`) rather than through libraries, so what it asks them can be tested on Linux, and the
  update script is run for real there with ordinary tools standing in for `ditto` and `open`.
- Not on the Mac yet, switched off in its half so the app hides them: the shortcut that works anywhere on the
  computer (it needs either Carbon calls nobody here can try, or the Accessibility permission), the small
  always-on-top quick write window, and going to a card by clicking its notification (macOS shows a notification
  sent this way as coming from its own script runner).
- Sign-in on a Mac uses Chrome if it is installed, else Edge, else the Chromium Birdbrain downloads.
- Two Mac builds, Apple silicon and Intel, not one universal: the browser driver inside is built for one or the
  other.
- On a Mac the window is an ordinary Mac window with the system's own title bar, not the one Birdbrain draws for
  itself on Windows.
