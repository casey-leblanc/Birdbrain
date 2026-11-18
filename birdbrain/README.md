# Birdbrain: the guide

Birdbrain keeps one list of your assignments, quizzes, exams and events from **Moodle** and **Outlook on the
web** (and Gradescope and McGraw Hill Connect, if you turn them on). The list opens in Birdbrain's own window, and
Birdbrain keeps scanning from the system tray (on a Mac, the menu bar) while the window is closed.

> **Birdbrain is a student project. It is not affiliated with, endorsed by or supported by Louisiana State
> University.**

This is the experimental version, 2.0. There is no AI in it and no key or account to set up.

## Install

### Windows

1. Unzip `Birdbrain-…-windows.zip` anywhere you like, for example your Documents folder.
2. Run `Birdbrain.exe` in the `Birdbrain` folder. Windows may show a warning because the app isn't signed yet:
   choose **More info**, then **Run anyway**.
3. The welcome page offers **Start Birdbrain with Windows**, already ticked: it then starts in the tray when you
   sign in, so reminders arrive without opening it. Settings › Notifications turns that on or off later.

It needs Windows 10 or 11. The window uses Microsoft Edge's WebView2, which both already have; without it, the list
opens in your web browser instead and a notification says why.

To check a copy works without touching your data, run `Birdbrain.exe --selftest result.txt` and read `result.txt`.

### Mac

1. Open the `.dmg` for your Mac (`arm64` for Apple silicon, `x64` for Intel) and drag **Birdbrain** onto
   **Applications**. Run it from Applications, not from inside the `.dmg`: it can't update itself from there.
2. Open Birdbrain. The first time, macOS says it could not verify the app, because it isn't signed yet. Click
   **Done**. Then open **System Settings › Privacy & Security**, scroll down to **Security**, click **Open Anyway**
   beside "Birdbrain was blocked to protect your Mac", choose **Open Anyway** again, and enter your password or
   use Touch ID. macOS remembers; you do this once. (On macOS 14 and older, right-click Birdbrain in Applications,
   choose **Open**, then **Open**.)
3. The welcome page offers to start Birdbrain when you sign in to your Mac, already ticked.

It needs macOS 12 or newer. What is different on a Mac:

- **Cmd** wherever this guide says Ctrl, and the bird sits in the **menu bar** in place of the tray.
- Birdbrain › Settings… (Cmd+,) and Birdbrain › Quit Birdbrain (Cmd+Q) are in the usual menu. Closing the window
  only hides it; clicking the Dock icon brings it back.
- Sign-in uses Google Chrome if you have it (or Microsoft Edge); otherwise Birdbrain downloads a browser of its
  own for it, once.
- The Telegram token, if you set one, is kept in your Keychain.
- **Not on the Mac yet:** the quick write shortcut that works from anywhere (press Space in Birdbrain's window, or
  choose Quick write from the menu bar icon), and opening a card by clicking its notification. Notifications
  themselves work; macOS shows them as coming from Script Editor the first time and may ask to allow them.

To check a copy: `/Applications/Birdbrain.app/Contents/MacOS/Birdbrain --selftest result.txt` in Terminal.

## First run

It takes under a minute.

1. **Your school.** LSU is already chosen, and that fills in where Moodle and your LSU email are: nothing to
   type. At another school, choose **Another school** and paste your Moodle address (open Moodle, copy the address
   from the address bar) and pick your Outlook: school or work, personal, or none. Tick Gradescope or McGraw Hill
   Connect if your courses use them.
2. **Make it yours.** Pick a layout, Glass or Focus, and a theme. You can change both later.
3. **Sign in.** One window opens with Moodle and Outlook. Sign in as you always do, and choose "Yes" if Microsoft
   asks "Stay signed in?". The window closes by itself once every site is signed in.

With a keyboard, the first two steps are Enter, Enter. The first scan reads every course page, so it takes a few
minutes; meanwhile the list says what it is reading, and your deadlines appear as it goes.

## Where your data stays

- Everything is kept on your computer, in `%APPDATA%\Birdbrain` (on a Mac, `~/Library/Application
  Support/Birdbrain`). There is no Birdbrain server or account, and
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

Beside each day's name is its load in a few words, "3 due · 1 exam", in bold when the day is a heavy one.

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

### Snooze

Press **S** on a card (or point at it and choose **Snooze**) to put it out of sight until **tomorrow**, **next
week**, or a day you pick. It waits in Archived, comes back by itself that morning with a "back from snooze" tag,
and **Wake it now** brings it back sooner. A card never stays hidden past its deadline: ask for a day after it is
due and it comes back the day it is due, and Birdbrain says so. Something due today can't be snoozed.

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
- **The menu** (⋯, or press M): Quick write, Search and commands, Add item, Settings, Scan now, Check for
  updates, Report a problem, Quit.

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
- **How often**: `every mon wed`, `every day`, `weekdays`, `weekly`, `monthly on the 1st`. The item repeats:
  tick it off and the next one appears (`gym every mon wed 6pm`, `rent monthly on the 1st`). There is only ever
  one of it on your list. A card's Details has a **Repeats** box to change it or clear it.

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

### Search and commands

Press **Ctrl+K** or **/** for one line that does two things:

- **Finds cards.** Type a word, `#label` or `@class` and the list narrows as you type. **Enter** keeps it narrowed;
  **Esc** shows everything again.
- **Runs things.** Type `scan`, `settings`, `new label`, `night`, `day`, `focus`, `keys`, `completed`… and the
  commands that answer are listed under the line. The arrow keys choose one and **Enter** runs it. A command is
  chosen for you when what you typed starts its name ("sc" is Scan now).

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
| S | Snooze it until a day (anywhere else, S is Settings) |
| D | Send it to Completed |
| M | Pick the item up: arrows move it, Enter drops it, Esc puts it back |
| Ctrl+Z | Undo the last change |
| Ctrl+K or / | Search, or run a command |
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
- **A heavy day ahead**, once, two or three days before: `Thursday is heavy: 4 due · 1 exam`.
- **New work** a scan finds, as one line however many there are.

Click a notification and Birdbrain opens on that card. Settings › Notifications changes the two times (clear one
to skip it), turns the test reminder or everything off, and **Show me one** sends a sample. Birdbrain has to be
running, and the PC awake, for a notification to appear.

### On your phone too (optional)

Settings › Advanced › Telegram sends the same short lines to your phone, through a Telegram bot of your own. It is
off until you set it up, which is four steps on that page: make a bot with @BotFather, paste its token, send the
bot the code Birdbrain shows, done. Then:

- each message has a button per card: tap it and the card is ticked off on your PC;
- text the bot anything and it is read the way quick write reads it: `dentist tue 3pm #appointment` adds it, and
  the reply says how it was understood, with Undo;
- `/list` sends what is due today and tonight; `/scan` scans now.

There is no AI in it. The bot's token is kept by Windows Credential Manager (on a Mac, your keychain), never in
Birdbrain's settings file, and only the chat you linked is listened to. **Turn off** removes the token. Messages
go from your PC to Telegram and nowhere else, so the PC has to be on.

## Settings

Its sections are listed down the side, in this order:

- **Sign-ins**: sign in to your school sites again; Gradescope and McGraw Hill Connect on or off; Scan now.
- **Look**: Glass (frosted panels over a photo of the sky) or Focus (a calm page with nothing but your list), a
  theme for each, day or night, or follow Windows. **Motion** is Full, Subtle or Off; until you choose, it follows
  your system's reduce-motion setting. **Text size** is Smaller, Standard, Larger or Largest, and scales every
  piece of text at once. **Custom** lets you use your own photos (Glass) or colours (Focus); Birdbrain keeps the
  words readable on whatever you pick.
- **Notifications**: see above; and the sounds.
- **Keys**: every key, and the quick write shortcut that works anywhere on the PC.
- **Labels**: rename, recolour, delete and add the labels for things that aren't classes; and a colour and a
  nickname for each class.
- **Updates**: which build you have, and the Update button.
- **About**, and Quit.
- **Advanced**, last and apart: things most students never need, each folded shut until you open it. Telegram;
  **Backup** (below); your Moodle
  and Outlook addresses; a full rescan of Moodle; "Scan back to", which reads older emails back to a date you
  pick; hidden keywords (anything whose title or course contains one goes straight to Archived); the log and the
  settings file.

## Access

- **Keyboard.** Everything can be done without a mouse: the keys above cover every action on a card, Ctrl+K runs
  everything in the menu, and every window is made of ordinary buttons and boxes that Tab reaches.
- **Focus.** Whatever has the keyboard focus shows a clear ring, on the list and in every window.
- **Contrast.** Text is at least 4.5:1 against what is really behind it (3:1 for large headings), in every
  built-in theme, day and night, including text over the Glass photos. This is measured on each build.
- **Screen readers.** Every control, window and picture has a name; changes are announced (a card ticked off, a
  move, a filter, a scan's trouble); a card's tick box says what the card is and when it is due.
- **Text size** and **Motion** are in Settings › Look. Motion Off stops everything from moving.

## Backup, and moving to another computer

Settings › Advanced › Backup. **Export to a file** saves what is yours, the items you added, your labels, and your
classes' colours and nicknames, as one file in your Downloads folder. On the other computer, install Birdbrain,
sign in, and **Import a file…**. Everything from Moodle and your email comes back by itself, so it isn't in the
file. Importing the same file twice changes nothing.

## Updates

Settings › Updates says which build you have. **Check for updates** asks GitHub for the newest
experimental build; if there is one, **Update and restart** downloads it, checks it arrived intact, makes sure it
starts on your PC, and swaps it in. The version you had is kept until the next update, and put back if anything
goes wrong. Birdbrain also looks a few times a day and tells you once when a build is ready. Your list and your
sign-ins are not touched.

On a Mac the same button replaces `Birdbrain.app` where it is and opens it again. It needs Birdbrain to be in
Applications (or another folder you can write to), not running from the `.dmg`.

To install a build you downloaded yourself: `Birdbrain.exe --install-update <the zip>` (on a Mac,
`Birdbrain.app/Contents/MacOS/Birdbrain --install-update <the mac zip>`).

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

The perched bird, with a red count of what's due today. Left-click opens the window. Right-click for Open, Quick
write, Scan now, Sign in and Quit (on a Mac, click the bird in the menu bar for the same menu); everything else is in the window. Closing the window only hides it; Birdbrain
keeps scanning. Quit stops it.

## If something goes wrong

- **Nothing new is showing up.** Look at the dot and the line beside it. It says what is going on and what to do:
  - *You're offline.* Your list is as it was, and Birdbrain scans again as soon as you're back online.
  - *Moodle needs sign-in.* Use the Sign in card at the top of the list.
  - *Couldn't reach Moodle at …* Check your connection, or the address in Settings › Advanced.
  - *Moodle couldn't be read: its page may have changed.* Your list is as it was. Check for updates in the menu: a
    site that changes needs a newer Birdbrain.
  - *The last scan didn't finish.* Birdbrain tries again by itself; if it keeps happening, use Report a problem.
- **A card is the wrong kind.** Press E on the card and say what it is.
- **A card shouldn't be there.** Archive it, or add a keyword for the whole kind of thing.
- **The window won't open.** Start `Birdbrain.exe` again (on a Mac, click Birdbrain in the Dock or open it from
  Applications): it brings the running copy's window forward.
- Settings › Advanced › Files has **Open log**, which says what each scan did.
- **Report a problem** (in the menu) makes a small zip to send to whoever is helping you: the end of the log, your
  settings, the version, and your own words if you add any. Names, emails, course titles, addresses and tokens are
  taken out first, the window shows you every line that would go in, and the zip is saved to your Downloads
  folder. Birdbrain sends nothing anywhere; you attach the file yourself.

## Credits

The list is set in Atkinson Hyperlegible (Braille Institute), under the SIL Open Font License. The Glass photos
are credited in `licenses\PHOTO-CREDITS.txt`. The sounds and the bird were made for Birdbrain.
