# Birdbrain

A Windows app that keeps a daily list of your assignments, tests and events
from **Moodle** and **Outlook on the web**, using TypeSafe's **Jev** model to read
emails and course text. The list opens in Birdbrain's own window, and Birdbrain
keeps scanning from the system tray while the window is closed.

## Install (packaged app)

1. Unzip `Birdbrain-1.1.0-windows.zip` anywhere you like, for example
   `%LOCALAPPDATA%\Programs\Birdbrain`.
2. Run `Birdbrain.exe`. No Python is needed. Its window opens; the first time, it
   welcomes you and asks where your Moodle and Outlook are (see **First run** below).
   On first run it also downloads its background browser once (about 100 MB).
3. Optional: to start it with Windows, press Win+R, run `shell:startup`, and put a
   shortcut to `Birdbrain.exe --background` in that folder. It then starts in the
   tray without opening the window.

The window needs the Microsoft Edge WebView2 Runtime, which comes with Windows 11
and current Windows 10. Without it, the list opens in your web browser instead, and a
notification says why. (A zip downloaded from the internet marks every file in it as
downloaded, which used to stop the window loading; Birdbrain now clears that mark from
its own files when it starts.)

Windows may show a SmartScreen warning because the app isn't code-signed. Choose
"More info", then "Run anyway".

To check a copy works without touching your data, run
`Birdbrain.exe --selftest result.txt` and read `result.txt`.

## First run

Birdbrain's window opens on a welcome page (even when started with `--background`) with two
short steps. First it asks for two addresses, each with a short "How do I find…?" guide:

- **Moodle address**: open Moodle in your browser, copy the address from the address
  bar and paste it in. Any Moodle page works; Birdbrain keeps just the start, such as
  `https://moodle.lsu.edu` (a Moodle in a folder, like `https://school.edu/moodle`, keeps
  its folder).
- **Outlook**: pick **School or work** (`https://outlook.office.com`), **Personal**
  (Outlook.com and Hotmail, `https://outlook.live.com`) or **I don't use Outlook**. If
  your Outlook on the web address starts differently (for example
  `https://outlook.cloud.microsoft`), paste it instead.
- **Also check** (optional): tick **Gradescope** or **McGraw Hill Connect** if your
  courses use them. You sign in to them in the same window as Moodle and Outlook.

Continue checks the addresses. The second step, **Make it yours**, lets you pick a layout
(**Glass** or **Focus**) and a theme, day or night; the welcome page itself changes as you
choose, so you see each look before you start. **Start Birdbrain** saves your choice, and
**Skip for now** keeps the default (Glass, Forest). You can change either later in Settings.

Then Birdbrain opens an Edge window (with its own profile) for signing in. It presses
Moodle's single-sign-on button (for LSU, "LSU Office 365 Authentication") for you.
Finish any Microsoft prompts, choosing "Yes" on "Stay signed in?", and the window
closes by itself once both sites are signed in. You sign in on Moodle's and
Microsoft's own pages; Birdbrain never sees your password. While the first full scan runs,
the list says it's reading your courses; your deadlines appear when it's done.

## Run from source

```
pip install -r requirements.txt
python -m playwright install chromium-headless-shell
setx TYPESAFE_API_KEY "your-key"      # from typesafe.ai; open a new terminal afterwards
pythonw main.py
```

To rebuild the zip, install PyInstaller and run `python build.py` from the
project folder. The zip lands in `dist\`.

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
| Gradescope, **if turned on** | This term's courses on your Gradescope dashboard, and each course's assignment list with its exact due time. Anything already submitted or graded is left off, and taken off once you submit it; Moodle's own entry for the same assignment, if it has one, is ticked off too | None: Gradescope gives exact dates |
| McGraw Hill Connect, **if turned on** | Connect's To Do list (the next few days) and each class's own page (every assignment), read as assignment cards: the name, the class and the due time. Work showing **See report**, a score or Completed is left off, and so is anything locked once its due date has passed (it can't be done any more); an assignment that's locked because it hasn't opened yet is listed | None |

**McGraw Hill through Moodle.** Many courses open Connect from a McGraw Hill link inside the
Moodle course, and Moodle doesn't hold those assignments' due dates; only Connect does. With
McGraw Hill Connect on and **From a link in a Moodle course** chosen (the default, in Settings ›
Scanning), **Sign in to your school sites** opens your Moodle course with a note: click any McGraw
Hill link in it once. Moodle signs Birdbrain's browser in to Connect, Birdbrain notes which link
you used and the class page it opened on, the note on the Moodle page says Connect is signed in,
and the window closes once every site is. Scans then read Connect's To Do list. When Connect signs you
out, you're asked to sign in again the same way, unless you turn on **Renew the sign-in by
itself**: then Birdbrain re-opens the link you last clicked, in the background. McGraw Hill sees
that as you opening that assignment, so leave it off if that link is a timed quiz or exam.

Receipts are never listed as work: an email that confirms a submission ("Successfully
submitted to HW3") or says a grade is out is skipped, whatever dates it mentions.
A Gradescope or Connect copy of a Moodle assignment only counts as a duplicate when it's
strictly the same work (same course, due within two days, matching title), so different
work due the same day is never hidden.

Jev makes judgments only; the code does the calendar math, following TypeSafe's
date-extraction cookbook. If Jev is unsure (confidence under 0.60), the item gets
an orange **check** tag. With no API key the app falls back to keyword matching.
Each email or text chunk is judged once and then cached.

## Tray menu

## The app window

- **Open it**: left-click the tray icon, or start `Birdbrain.exe` again (a pinned
  taskbar icon works too). Closing the window only hides it; Birdbrain keeps
  scanning in the tray. To stop Birdbrain completely, use **Quit Birdbrain** in
  Settings or **Quit** in the tray icon's right-click menu.
- The window has no Windows title bar. Its own bar is see-through, so the theme's photo
  or colour runs to the top edge, and it frosts over once you scroll. Drag it to move the
  window (dragging to a screen edge snaps as usual), double-click it to maximise, and use
  its minimise, maximise and close buttons. Drag the top edge to resize. The scrollbar is
  Birdbrain's own too: frosted glass in the Glass layout, the theme's colour in Focus.
- Links to Moodle and Outlook open in your usual web browser.

## Your list

- The list has three columns:
  - **Now**: overdue, today, tomorrow.
  - **This week**: the next five days, grouped by day.
  - **Later**: everything further out, in date order, under a label naming the day it starts from, with exams and quizzes marked.

  The top of the page is one row: today's date with counts of what's overdue, due today and due tomorrow (shown once the first scan has finished, so an empty list never reads as nothing due); the title, with when the last scan finished beneath it (highlighted if something needs attention, such as signing in again); and the Add item and Settings buttons. Below it, a slim strip names the **next exam** (exams, tests, midterms and finals) and the **next quiz**, one step lower in urgency. The next quiz is left out when it's already listed under Now.

  The list comes in two layouts (pick in Settings):
  - **Glass** (the default): frosted panels overlooking the open sky, modelled on caseyleblanc.dev and meant to feel vast, with the freedom of a bird's view. Items sit clear on the glass until something makes them urgent. Overdue, today and tomorrow each give the date a solid red, amber or yellow chip, and overdue items are also tinted red. Exams have a solid "exam" chip and a bold title; quizzes an outlined "quiz" chip.
  - **Focus**: a calm, roomy page with nothing but your list. The day is the headline, the next exam and quiz share one line under it, and the columns sit straight on the page with wide space between them, divided by thin lines, with no panels. The same heat colours as Glass mark how soon things are due, as flat chips softened to suit each theme: overdue in the theme's own red, today amber, tomorrow yellow. Exams have a solid "exam" chip in the theme's heading colour and a bold title; quizzes an outlined "quiz" chip.

  Each entry shows the title, the course code (e.g. CHEM 1212, with a dot of its colour once you pick one) and the due time. A title with a faint dotted underline opens the entry in Moodle or Outlook, in a new tab. Emails and calendar entries have **Details**, which shows the preview text.

  Birdbrain serves this page itself, at a private address that only this computer can open. The address includes a key that changes each time the app starts. The page updates on its own after each scan.
- **Tick an item off** and it flies into the **Completed** bin, above Archived, and stops counting toward overdue, today and the tray badge; the items below slide up into its place. For 6 seconds the message at the bottom offers **Undo** (or press Ctrl+Z), which flies it back; after that, untick it in Completed to put it back (and that has an Undo too). Ticking from the keyboard moves focus to the next item.
- **Archive an item** you don't need to see: point at it (or tab to it) and choose **Archive**, and it moves to the **Archived** section at the bottom. Anything in Archived, whether you archived it or a keyword or duplicate put it there, has **Show on list** to bring it back, and it then stays on your list even if it matches a keyword.
- **Keyboard shortcuts:** **N** adds an item, **S** opens Settings, **R** scans now, **J** jumps to the first item and **?** lists the shortcuts (in Settings › App). On an item, **↓**/**J** and **↑**/**K** move to the next and previous, **←**/**→** to the column beside, **O** (or Enter on its tick box) opens it, **A** archives it (or, in Archived, shows it again), **E** edits one you added and Space ticks it off. Ctrl+Z undoes the last change and Esc closes a window. Single keys work whenever no window is open and you aren't typing.
- **Every change to the list can be undone** from the message at the bottom for 6 seconds: ticking off or putting back, archiving or showing, adding, editing and deleting your own items.
- **Finish today's list** (tick off the last thing that's overdue or due today) and a bird flies in to land on the empty branch in the Now column, with a chirp if sounds are on. When Now is empty it says **all clear** and names the next thing coming. If Windows is set to reduce animations, nothing flies; the list and the message at the bottom still show what happened.
- **Add item** (on the list page): your own assignment, exam, quiz or event, with a due date and optionally a time, a course and notes. It appears in the columns like everything else. Open its **Details** to **Edit** it (the same form, pre-filled) or delete it (click Delete twice; Undo brings it back).
- **Settings** (on the list page) has five tabs, one for each kind of thing you'd come to change. Arrow keys move between them, and Settings reopens on the tab you used last.
  - **Look**: the layout, Glass (default) or Focus; in Glass, **Frame** chooses Full width or Narrow, which leaves more of the photo showing. Then the theme: each layout has its own themes and remembers its own choice. Each theme card has a day half and a night half; click either to switch to that version. Tick **Follow Windows' light and dark mode** to switch between day and night with Windows.
    - Glass: Forest (default), Birdbrain, Cloudy, High contrast and Dusk, each with its own photo for day and for night. Cloudy is towering white cumulus by day and a sea of clouds under the moon by night.
    - Focus: Forest (default), Paper, Slate, Ocean, Birdbrain, Dusk, Cloudy, Sunrise and High contrast, each its own set of colours for day and night.
    - **Custom**, in both. In Glass, choose your own day and night pictures (JPEG, PNG or WebP, up to 25 MB) and an accent colour for the title and exam chips. Birdbrain keeps its own copy in `%APPDATA%\Birdbrain\photos`, tints the glass to match each picture, and darkens it as much as that picture needs to keep every word readable. In Focus, choose four colours for day and four for night (background, text, headings with courses and exams, and overdue); Birdbrain works out the softer shades and warns you if a colour won't read on your background.
  - **Scanning**: **Scan now** and **Full rescan of Moodle** (every course page, not just the timeline); **Other sites** (turn Gradescope or McGraw Hill Connect on or off; for Connect, choose whether you open it from a link in Moodle or at connect.mheducation.com, and whether Birdbrain may renew that sign-in by itself); **Sign in to your school sites** (a window with Moodle, Outlook and any other sites you use) for when a notification says you need to sign in again; and **Older emails**: regular scans read your newest 50 emails, and "Scan back to" reads older ones too, back to a date you pick. It stops once it's past that date, reading at most 3,000 emails. **Stop** ends it early (or cancels it if it hasn't started); anything it has already found stays, and emails it hadn't got to are read next time.
  - **Courses**: a color and a nickname for each course tag. It warns you if a color is hard to see on the current theme or matches another course.
  - **Keywords**: entries whose title or course contains a keyword move to the collapsed **Archived** section at the bottom, which also holds duplicates (for example Moodle's own reminder emails). Each keyword shows how many entries it hides; remove it and they come back. Adding or removing one says what changed right there, with an **Undo**.
  - **App**: **Sounds** (a soft two-note call whenever a scan finds new assignments, exams or events, and a chirp as the bird lands when you finish today's list; on by default, and **Play the call** lets you hear it), **Open settings file** (`%APPDATA%\Birdbrain\config.json`: scan interval, how far ahead to look, `browser_channel` (`msedge`/`chrome`), `headless`, and more), **Open log**, and **Quit Birdbrain** (click twice).

  Everything you set on the page (layout, themes, your Custom theme, course tags, open bins), ticked items and your own items are saved by Birdbrain, so they carry across restarts and browsers.

  `%APPDATA%\Birdbrain\today.html` is a read-only copy of the list, for when Birdbrain isn't running.

## Tray icon

Birdbrain's icon (in the tray, on the window and on `Birdbrain.exe`) is the perched bird from the
list's "all clear" drawing, white on violet. In the tray it carries a red count of what's due today,
at the top left. Left-click opens the window. The right-click menu has the same actions as Settings:
**Open Birdbrain**, **Refresh now**, **Full rescan of Moodle**, **Hide entries by
keyword…**, **Sign in to your school sites…**, **Settings…** (the settings file),
**Open log** and **Quit**.

## Start with Windows

Press Win+R, run `shell:startup`, and add a shortcut to
`Birdbrain.exe --background` (or, from source, `pythonw.exe "<path>\main.py" --background`).
Birdbrain then starts in the tray; left-click the icon to open the window.

## Notes

- Outlook's page layout isn't a public API. If Microsoft changes it, the
  selectors at the top of `outlook.py` may need updating. `Open log` shows errors.
- Thresholds and the model name are in `config.py`. Colors and the font are in `theme.py`.
- The list uses Atkinson Hyperlegible (Braille Institute), bundled in
  `assets/fonts` under the SIL Open Font License (`OFL-AtkinsonHyperlegible.txt`).
- The Glass photos are in `assets/backgrounds`: nine from Unsplash (Unsplash License) and
  the Forest daytime photo from caseyleblanc.dev (Orhan Pergel, Pexels). Photographers are credited in
  `CREDITS.txt` there, and in `licenses\PHOTO-CREDITS.txt` in the packaged app. The call
  and the chirp (`assets/sounds`) were synthesised for Birdbrain, and the bird drawings on the page were drawn for it. The Glass layout's
  colours are in `glass.py`, the Focus themes in `theme.py`, and the Custom theme's workings in `custom.py`.

- Birdbrain was called StudyTray before. On its first start it moves your data from `%APPDATA%\StudyTray` to `%APPDATA%\Birdbrain`. If you made a Startup shortcut, point it at the new folder.
