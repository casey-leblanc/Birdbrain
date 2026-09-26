# Birdbrain

A Windows system-tray app that keeps a daily list of your assignments, tests
and events from **Moodle** and **Outlook on the web**, using TypeSafe's
**Jev** model to read emails and course text.

## Install (packaged app)

1. Unzip `Birdbrain-1.0.0-windows.zip` anywhere you like, for example
   `%LOCALAPPDATA%\Programs\Birdbrain`.
2. Run `Birdbrain.exe`. No Python is needed. On first run it downloads its
   background browser once (about 100 MB), then carries on.
3. Optional: to start it with Windows, press Win+R, run `shell:startup`, and put a
   shortcut to `Birdbrain.exe` in that folder.

Windows may show a SmartScreen warning because the app isn't code-signed. Choose
"More info", then "Run anyway".

To check a copy works without touching your data, run
`Birdbrain.exe --selftest result.txt` and read `result.txt`.

## Run from source

```
pip install -r requirements.txt
python -m playwright install chromium-headless-shell
setx TYPESAFE_API_KEY "your-key"      # from typesafe.ai; open a new terminal afterwards
pythonw main.py
```

To rebuild the zip, install PyInstaller and run `python build.py` from the
project folder. The zip lands in `dist\`.

On first launch it asks for your Moodle address and Outlook address, then opens
an Edge window (with its own profile). It presses Moodle's single-sign-on
button (for LSU, "LSU Office 365 Authentication") for you. Finish any Microsoft
prompts, choosing "Yes" on "Stay signed in?", and the window closes by itself
once both sites are signed in.

Background scans use Playwright's windowless Chromium, so no windows appear in
Alt+Tab. They reuse the sign-in window's cookies, stored in
`%APPDATA%\Birdbrain\session.json`, and send a normal browser user-agent,
because LSU Moodle returns 403 to "headless" browsers. When a Moodle session
expires, scans press the single-sign-on button themselves. You're only asked to
sign in when Microsoft wants a password or code again.

## What it reads

| Source | How | Jev's role |
|---|---|---|
| Moodle timeline | Moodle's AJAX API via your session (open work with deadlines; submitted work disappears) | Decides whether an activity is an assignment or a test (e.g. an assignment titled "Take-home midterm") |
| Moodle calendar | Course, site and personal calendar events | Decides whether each is a test or an event |
| Moodle courses, **first run / Full rescan only** | Every course's assignment and quiz index, plus all text on the course page | Finds exam dates and deadlines written in prose and reads their dates |
| Outlook inbox | The newest 50 message previews (it never opens a message, so nothing gets marked read) | Decides whether an email describes an assignment, test or event, and reads its date. Relative dates like "due tomorrow" count from the day the email was sent |
| Outlook calendar | Week views over the next 30 days (recurring events are skipped unless they're tests) | Classifies each event |

Jev makes judgments only; the code does the calendar math, following TypeSafe's
date-extraction cookbook. If Jev is unsure (confidence under 0.60), the item gets
an orange **check** tag. With no API key the app falls back to keyword matching.
Each email or text chunk is judged once and then cached.

## Tray menu

- **Show today's list** (or double-click the icon): three columns:
  - **Now**: overdue, today, tomorrow.
  - **This week**: the next five days, grouped by day.
  - **Later**: tests, events and assignments further out.

  The top of the page shows the title, when the last scan finished (highlighted if something needs attention, such as signing in again), then three small panels: today's date with counts of what's overdue, due today and due tomorrow; the **next exam** (exams, tests, midterms and finals); and the **next quiz**, one step lower in urgency.

  The list comes in two layouts (pick in Settings):
  - **Frosted glass** (the default): glass panels over a photo, modelled on caseyleblanc.dev. Due dates are colour-coded by how soon they are: overdue items are red, today's amber and tomorrow's yellow, each with a coloured edge and a solid date chip; items two or three days away get a white edge. Exams have a solid "exam" chip and a bold title; quizzes an outlined "quiz" chip.
  - **Classic**: flat and typographic, with large monospaced column headings. Exams have a red, bold title and an "exam" label; quizzes a semi-bold title and an italic "quiz" label.

  Each entry shows the title, the course code (e.g. CHEM 1212) and the due time. Emails and calendar entries have **Details**, which shows the preview text.

  Birdbrain serves this page itself, at a private address that only this computer can open. The address includes a key that changes each time the app starts, so always open the list from the tray icon. The page updates on its own after each scan.
- **Tick an item off** and it moves to the **Completed** bin, above Archived, and stops counting toward overdue, today and the tray badge. Untick it there to put it back.
- **Add item** (on the list page): your own assignment, exam, quiz or event, with a due date and optionally a time, a course and notes. It appears in the columns like everything else. Open its **Details** to **Edit** it (the same form, pre-filled) or delete it (click Delete twice).
- **Settings** (on the list page):
  - **Layout**: Frosted glass (default) or Classic.
  - **Theme**: Forest (default), Birdbrain, Night study, High contrast or Dusk, each in **Light**, **Dark** or **Match system** (follows Windows). In Frosted glass, each theme is a colour scheme with its own photo, a daytime one in Light and a night one in Dark.
  - **Outlook inbox**: regular scans read your newest 50 emails. "Scan back to" reads older ones too, back to a date you pick. It stops once it's past that date, reading at most 3,000 emails.
  - **Courses**: a color and a nickname for each course tag. It warns you if a color is hard to see on the current theme or matches another course.

  Everything you set on the page (layout, theme, course tags, open bins), ticked items and your own items are saved by Birdbrain, so they carry across restarts and browsers.

  `%APPDATA%\Birdbrain\today.html` is a read-only copy of the list, for when Birdbrain isn't running.
- **Hide entries by keyword…**: entries whose title or course contains a keyword move to the collapsed **Archived** section at the bottom, which also holds duplicates (for example Moodle's own reminder emails). Remove a keyword and its entries come back.
- **Refresh now** / **Full rescan of Moodle**
- **Sign in to Moodle / Outlook…**: use this when a notification says you need to sign in again.
- **Settings…** opens `%APPDATA%\Birdbrain\config.json`: scan interval, how far ahead to look, `browser_channel` (`msedge`/`chrome`), `headless`, and more.

## Start with Windows

Press Win+R, run `shell:startup`, and add a shortcut to
`pythonw.exe "<path>\main.py"`.

## Notes

- Outlook's page layout isn't a public API. If Microsoft changes it, the
  selectors at the top of `outlook.py` may need updating. `Open log` shows errors.
- Thresholds and the model name are in `config.py`. Colors and the font are in `theme.py`.
- The list uses Atkinson Hyperlegible (Braille Institute), bundled in
  `assets/fonts` under the SIL Open Font License (`OFL-AtkinsonHyperlegible.txt`).
- The Frosted glass photos are in `assets/backgrounds`: nine from Unsplash (Unsplash License) and
  the Forest daytime photo from caseyleblanc.dev (Orhan Pergel, Pexels). Photographers are credited in
  `CREDITS.txt` there, and in `licenses\PHOTO-CREDITS.txt` in the packaged app. The glass layout's
  colours are in `glass.py`.

- Birdbrain was called StudyTray before. On its first start it moves your data from `%APPDATA%\StudyTray` to `%APPDATA%\Birdbrain`. If you made a Startup shortcut, point it at the new folder.
