# Birdbrain: the guide

Birdbrain keeps one list of your assignments, quizzes, exams and events from **Moodle** and **Outlook on the
web** (and Gradescope and McGraw Hill Connect, if you turn them on). The list opens in Birdbrain's own window, and
Birdbrain keeps scanning from the system tray while the window is closed.

> **Birdbrain is a student project. It is not affiliated with, endorsed by or supported by Louisiana State
> University.**

This is the experimental version, 2.0. There is no AI in it and no key or account to set up.

## Install

1. Unzip `Birdbrain-…-windows.zip` anywhere you like, for example your Documents folder.
2. Run `Birdbrain.exe` in the `Birdbrain` folder. Windows may show a warning because the app isn't signed yet:
   choose **More info**, then **Run anyway**.
3. To start it with Windows: press Win+R, run `shell:startup`, and put a shortcut to
   `Birdbrain.exe --background` in that folder. It then starts in the tray without opening the window.

It needs Windows 10 or 11. The window uses Microsoft Edge's WebView2, which both already have; without it, the list
opens in your web browser instead and a notification says why.

To check a copy works without touching your data, run `Birdbrain.exe --selftest result.txt` and read `result.txt`.

## First run

1. **Where are your sites?** Paste your Moodle address (open Moodle, copy the address from the address bar; for
   LSU it is `https://moodle.lsu.edu`) and pick your Outlook: school or work, personal, or none. Tick Gradescope
   or McGraw Hill Connect if your courses use them.
2. **Make it yours.** Pick a layout, Glass or Focus, and a theme. You can change both later.
3. **Sign in.** A window opens with Moodle and Outlook. Sign in as you always do, and choose "Yes" if Microsoft
   asks "Stay signed in?". The window closes by itself once every site is signed in.

The first scan reads every course page, so it takes a few minutes. Your deadlines appear as it goes.

## Where your data stays

- Everything is kept on your computer, in `%APPDATA%\Birdbrain`. There is no Birdbrain server or account, and
  nothing is sent to its author.
- You type your password only into Moodle's and Microsoft's own pages. Birdbrain never sees it. It keeps the
  signed-in session those pages give the browser, as a browser does.
- Plain rules on your computer read your course pages and email previews. Nothing is sent to an AI service.
- Birdbrain only reads. It never opens an email (so nothing gets marked as read), and it never submits or
  changes anything on your sites.
- It connects to the sites you signed in to, and to GitHub to look for a newer version. On first run it also
  downloads, once, the browser it scans with (about 100 MB).

## Your list

The list is the whole window. Three columns:

- **Now**: overdue, today, tomorrow.
- **This week**: the next five days, a group for each day.
- **Later**: everything further out, in date order.

Each card shows the title, the course (CHEM 1212), and the time it is due. Tags say the rest: a red, amber or
yellow time for overdue, today and tomorrow; **exam** or **quiz** on tests, with **in 5 days** while one is still
a few days off; **date unsure** when the day was worked out from words like "Friday" rather than stated. A title
with a dotted underline opens the item in Moodle or Outlook.

- **Tick it off** and it moves to **Completed**. Undo is offered for 6 seconds (or press Ctrl+Z).
- **Archive** hides a card you don't need (point at the card, or tab to it). It waits under **Archived**, where
  **Show on list** brings it back.
- **Details**: press **E** on a card, double-click it, or use its **?**. For something you added, every field can
  be changed: title, type, day, time, class, label, notes. For something from Moodle or your email, the fields are
  shown but locked, except **what it is**: say it is an assignment, a quiz, an exam or an event, and your answer
  sticks. It also goes for the others like it in the same course. Say once that "Biochemical Testing - Oxidase
  Test" is an assignment, and every "Biochemical Testing - …" lab follows.
- **Your own items**: press **Space** and type. See **Quick write** below. A card you added has **Details**,
  with Edit and Delete.

### Moving cards

Drag a card and it lifts and follows the pointer; the cards around it part to show where it will land. On a touch
screen, press and hold first.

- **Within its day**: drop it above or below the others. The order is yours and it stays.
- **To an earlier day**: plan to do it sooner. The card moves to that day and still says when it is really due
  ("due Fri 11:59 PM").
- **Not later than it is due**: something from Moodle or your email can't be planned past its deadline. The card
  shakes, goes back, and says why. Something you added yourself can go to any day: its date changes.
- **Completed** and **Archived** appear at the bottom of the window while you drag. Drop a card on one. To bring one
  back, open that bin and drag the card onto a day.
- **Esc**, or letting go away from the list, puts the card back.
- Every move offers **Undo** for 6 seconds (or press Ctrl+Z).

Without a mouse: press **M** on a card to pick it up, move it with the arrow keys (up and down through the days,
left and right between the columns), **Enter** to drop it, **Esc** to put it back. **D** sends a card to
Completed and **A** to Archived. A screen reader hears each step ("Thursday, second of four").

### Motion

Settings › Look › Motion has three levels. **Full**: cards lift, glide and spring into place, and on Glass a ripple
of light spreads from where a card lands or is ticked, with a soft sheen under the pointer. **Subtle**: cards still
move to show what happened, without the ripple and the sheen. **Off**: nothing moves. If your computer is set to
reduce motion, Birdbrain starts at Off.

In the top corner of the list:

- **The dot** is Birdbrain's status. It breathes slowly while Birdbrain is idle, faster while a scan runs, when it
  also says what it is reading; it turns red, with
  the reason beside it, when something needs you. Point at it to see when the last scan finished. Click it to
  scan now.
- **The menu** (⋯, or press M): Quick write, Add item, Settings, Scan now, Check for updates, Quit.

If a site needs signing in to again, a card at the top of the list says so, with a **Sign in** button.

### Quick write

Press **Space**, type one line, press **Enter**. That's a new item on your list.

    chem lab report fri 5pm #life

Birdbrain reads the line as you type and shows what it understood in chips under it:

- **A day**: `today`, `tmr`, `fri`, `next tue`, `in 3 days`, `11/21`, `nov 21`. No day means today.
- **A time**: `5pm`, `5:30p`, `17:00`, `noon`, `midnight`, `at 5`.
- **A label**: `#life`, `#work`, `#appointment`, `#extracurricular` (the start is enough: `#app`).
- **A class**: `@chem` finds your CHEM course.
- **A type**: start with `quiz` or `exam` ("quiz ch 5 fri").

Everything else is the title. If it reads a word you meant as plain text, press **Backspace** right after the
word and it is handed back. **Ctrl+Enter** saves and stays open for the next one; **Esc** closes. You can fill in
the rest (class, notes) later from the card's Details.

### Labels, and showing only one

Labels are for things that aren't classes: **Life**, **Extracurricular**, **Appointment** and **Work** to begin
with, and your own. A label is a tag on the card, with a small square of its colour.

- Give one in quick write (`#life`) or in a card's details.
- **Click a tag** on a card, a label or a class, to show only those. Or press **#** or **@** and type the start of
  one (`#wo`, `@chem`); the list narrows as you type. **Esc** shows everything again.
- **Settings › Labels** renames, recolours, deletes and adds. Renaming changes the tag on every card. Deleting a
  label takes it off its cards and leaves everything else about them; Undo is offered right there. If a colour
  would blend into the page in some look, Settings says which.

**From anywhere on your PC:** press **Ctrl+Alt+Space**, even with Birdbrain's window closed. A small quick write
line opens on top of whatever you're doing; type, press Enter, and it's gone again. You can change the shortcut or
turn it off in Settings › Keys. If another program already uses it, Settings says so and offers others.

### Keys

| Key | Does |
|---|---|
| Space | Quick write: add something |
| Ctrl+Alt+Space | Quick write from anywhere on your PC |
| M | The menu |
| S | Settings |
| R | Scan now |
| N | Add an item with the full form |
| J | Go to the first item |
| ↓ / J, ↑ / K | Next and previous item, through every day |
| ← / → | The column beside |
| X | Tick the item off, or untick it |
| E | The item's details |
| O | Open the item in Moodle or Outlook |
| A | Archive it, or show it again |
| D | Send it to Completed |
| M | Pick the item up: arrows move it, Enter drops it, Esc puts it back |
| Ctrl+Z | Undo the last change |
| # or @ | Show only one label or class |
| ? | Show every key on one screen |
| Esc | Close a window |

## Notifications

They are on from the start, with nothing to set up. Each is one short line by the clock, never a pile of them:

- **In the morning** (7:30): `Today: Chem Exp 15 Quiz, Pre-lab`. Nothing due, nothing said.
- **In the evening** (7:00): `Due tonight: …`, which reaches to mid-morning tomorrow, so a 7 AM deadline is not a
  surprise.
- **Before a test**: the day before an exam (`Exam tomorrow at 9:30 AM: Math Exam 2`), and three hours before a
  quiz closes.
- **New work** a scan finds, as one line however many there are.

Click a notification and Birdbrain opens on that card. Settings › Notifications changes the two times (clear one
to skip it), turns the test reminder or everything off, and **Show me one** sends a sample. Birdbrain has to be
running, and the PC awake, for a notification to appear.

## Settings

Its sections are listed down the side, in this order:

- **Sign-ins**: sign in to your school sites again; Gradescope and McGraw Hill Connect on or off; Scan now.
- **Look**: Glass (frosted panels over a photo of the sky) or Focus (a calm page with nothing but your list), a
  theme for each, day or night, or follow Windows. **Motion** is Full, Subtle or Off; until you choose, it follows
  your system's reduce-motion setting. **Custom** lets you use your own photos (Glass) or colours
  (Focus); Birdbrain keeps the words readable on whatever you pick.
- **Notifications**: see above; and the sounds.
- **Keys**: every key, and the quick write shortcut that works anywhere on the PC.
- **Labels**: rename, recolour, delete and add the labels for things that aren't classes; and a colour and a
  nickname for each class.
- **Updates**: which build you have, and the Update button.
- **About**, and Quit.
- **Advanced**, last and apart: things most students never need, each folded shut until you open it. Your Moodle
  and Outlook addresses; a full rescan of Moodle; "Scan back to", which reads older emails back to a date you
  pick; hidden keywords (anything whose title or course contains one goes straight to Archived); the log and the
  settings file.

## Updates

Settings › Updates says which build you have. **Check for updates** asks GitHub for the newest
experimental build; if there is one, **Update and restart** downloads it, checks it arrived intact, makes sure it
starts on your PC, and swaps it in. The version you had is kept until the next update, and put back if anything
goes wrong. Birdbrain also looks a few times a day and tells you once when a build is ready. Your list and your
sign-ins are not touched.

To install a build you downloaded yourself: `Birdbrain.exe --install-update <the zip>`.

## What it reads

| Source | What |
|---|---|
| Moodle timeline and calendar | Open work with its exact deadline, and course, site and personal calendar events. Work you submit disappears. |
| Moodle course pages (first scan, and Full rescan) | Every course's assignments and quizzes, and dates written in the page text, such as an exam date in a paragraph. |
| Outlook inbox | The newest 50 message previews. "Due tomorrow" counts from the day the email was sent. |
| Outlook calendar | The next 30 days. Repeating entries are skipped unless they are tests. |
| Gradescope, if on | This term's courses and each assignment's due time. Submitted work is left off. |
| McGraw Hill Connect, if on | Your To Do list and each class's assignments, with their due times. Finished work is left off. |

A few things worth knowing:

- The word "test" alone doesn't make an exam. A lab called "Oxidase Test" is an assignment, and "Exam 2 Review"
  is not the exam. If the rules still get one wrong, the card's details (E) fix it for good.
- A receipt is never listed as work: "Successfully submitted to HW3", or a grade being posted.
- Moodle's own reminder emails, and a Gradescope or Connect copy of the same Moodle assignment, are filed under
  Archived as duplicates, so each piece of work is listed once.
- An 11:59 PM deadline is shown as 11:59 PM. Something with only a day, such as a date read from an email, shows
  no time.
- A PC that was asleep at scan time scans as soon as it wakes, and stays awake until the scan is done.

**McGraw Hill through Moodle.** Many courses open Connect from a link inside the Moodle course. When you sign in,
Birdbrain opens that course with a note: click any McGraw Hill link in it once, and Connect is signed in. If each
Moodle activity links to a single assignment, pick one you have already finished, never a timed quiz or exam.
When Connect signs you out you are asked to do this again, unless you turn on **Renew the sign-in by itself**:
then Birdbrain re-opens the link you last clicked. McGraw Hill sees that as you opening that assignment, so leave
it off if that link is a timed quiz or exam.

## The tray icon

The perched bird, with a red count of what's due today. Left-click opens the window. Right-click for Open, Refresh
now, Full rescan of Moodle, keywords, Sign in, the settings file, the log and Quit. Closing the window only hides
it; Birdbrain keeps scanning. Quit stops it.

## If something goes wrong

- **Nothing new is showing up.** Look at the dot: red means a site needs signing in to, or couldn't be reached.
- **A card is the wrong kind.** Press E on the card and say what it is.
- **A card shouldn't be there.** Archive it, or add a keyword for the whole kind of thing.
- **The window won't open.** Start `Birdbrain.exe` again: it brings the running copy's window forward.
- Settings › Advanced › Files has **Open log**, which says what each scan did.

## Credits

The list is set in Atkinson Hyperlegible (Braille Institute), under the SIL Open Font License. The Glass photos
are credited in `licenses\PHOTO-CREDITS.txt`. The sounds and the bird were made for Birdbrain.
