# Testing Birdbrain 2.0 (experimental)

Thank you for trying this. It takes about 25 minutes. You need a Mac or a Windows PC, and your own Moodle and
school email sign-in.

Birdbrain is a student project. It is not affiliated with, endorsed by or supported by Louisiana State University.

## What this is, and what it will touch

Birdbrain keeps one list of what you have due, read from Moodle and your school email. This is a test version.

- It **only reads** your sites. It never submits, changes or marks anything, and it never opens an email.
- You type your password only into Moodle's and Microsoft's own sign-in pages. Birdbrain never sees it.
- Everything stays on your computer. There is no Birdbrain account, and nothing is sent to its author. There is
  no AI in it.
- It puts these on your computer, and nothing else:
  - the app itself, where you put it;
  - its data folder: `%APPDATA%\Birdbrain` on Windows, `~/Library/Application Support/Birdbrain` on a Mac;
  - a browser it scans with, downloaded once on first run (about 150 MB), in a folder called `ms-playwright`;
  - if you leave "Start Birdbrain when I sign in" ticked, one start-up entry for your own account.
- The last run in this guide removes all of it.

**Mac or Windows?** Everything below is for both unless it says otherwise. On a Mac, where the guide says **Ctrl**,
press **Cmd**, and where it says "the tray", look in the **menu bar** at the top right of the screen.

## Get it

Open <https://github.com/casey-leblanc/Birdbrain/releases> and find the newest **Birdbrain experimental** entry (it
is marked "Pre-release"). Under "Assets":

| Your computer | Download |
|---|---|
| Windows 10 or 11 | `Birdbrain-…-windows.zip` |
| Mac with Apple silicon (M1 or later) | `Birdbrain-…-mac-arm64.dmg` |
| Mac with an Intel processor | `Birdbrain-…-mac-x64.dmg` |

Not sure which Mac? Apple menu › About This Mac. "Chip: Apple M…" is Apple silicon. "Processor: Intel" is Intel.

### Install on Windows

1. Right-click the zip › **Extract All**, into your Documents folder.
2. Open the `Birdbrain` folder and double-click `Birdbrain.exe`.
3. Windows shows a blue box: **"Windows protected your PC"**. This is because the app isn't signed yet. Click
   **More info**, then **Run anyway**.

### Install on a Mac

1. Double-click the `.dmg`. A window opens with the bird and an Applications folder. Drag the bird onto
   **Applications**.
2. Open your Applications folder and double-click **Birdbrain**.
3. macOS says **"Birdbrain" Not Opened** (or "can't be opened because Apple cannot check it"). This is because the
   app isn't signed yet. Click **Done**. Then:
   - Open **System Settings › Privacy & Security** and scroll down to **Security**.
   - It says "Birdbrain was blocked to protect your Mac". Click **Open Anyway**, then **Open Anyway** again, and
     enter your password or use Touch ID.
   - On macOS 14 or older, instead: hold **Control**, click Birdbrain in Applications, choose **Open**, then
     **Open**.
4. You only do this once.

> **Install**: [ ] as described  ·  What happened instead:

## First run

| Do this | You should see |
|---|---|
| Wait for the welcome page. | "welcome to birdbrain", with **LSU** already chosen and nothing to type. |
| If your courses use Gradescope or McGraw Hill Connect, tick them. Press **Continue**. | "make it yours": a choice of Glass or Focus, and themes. |
| Pick what you like. Press **Start Birdbrain**. | A sign-in window opens with Moodle (and then Outlook). |
| Sign in the way you always do. If Microsoft asks "Stay signed in?", choose **Yes**. | The sign-in window closes by itself. |
| Look at the list. | "reading your courses", and under it what is being read right now. Your cards appear as it goes. The first scan takes a few minutes. |

> **First run**: [ ] as described  ·  How long did the first scan take?  ·  What happened instead:

You can carry on with the runs below while the first scan finishes.

## The runs

Tick each box if it went as described. If not, write what happened in the gap. A few words is plenty.

### 1. The list

| Do this | You should see |
|---|---|
| Look at the window. | Three columns: **now**, **this week**, **later**. No header, no summary: just cards. |
| Read one card. | Its title, the class (like CHEM 1212), and when it is due. Exams and quizzes have a tag. |
| Look in the top right corner. | One small dot and a **⋯** menu. Nothing else. |
| Compare with Moodle. | Nothing you know is due is missing, and nothing is marked as an exam that isn't one. |

> [ ] as described  ·  Anything missing, extra or wrongly labelled:

### 2. Quick write

Press **Space**, type the line, press **Enter**. Do each of these five:

| Type this | You should see |
|---|---|
| `call mom` | A new card under **today**. |
| `dentist tue 3pm #appointment` | A card under Tuesday, 3:00 PM, with an **Appointment** tag. |
| `chem lab report fri 5pm` | A card under Friday at 5:00 PM. |
| `quiz ch 5 tomorrow` | A card under **tomorrow** with a **quiz** tag. |
| `gym every mon wed 6pm` | A card with a small "every mon, wed" mark. Tick it off: the next one appears. |

Each should take under five seconds, with no mouse.

> [ ] as described  ·  Which line was read wrongly, and how:

### 3. The shortcut from anywhere (Windows only)

| Do this | You should see |
|---|---|
| Close Birdbrain's window with its ✕. Click into another program. Press **Ctrl+Alt+Space**. | A small dark line appears on top of everything, ready to type in. |
| Type `test from anywhere tmr 9am` and press **Enter**. | It says "Added …" and goes away. Birdbrain's window stays closed. |
| Open Birdbrain from its tray icon. | The card is under tomorrow at 9:00 AM. |

> [ ] as described  ·  [ ] I'm on a Mac (skip)  ·  What happened instead:

### 4. Labels

| Do this | You should see |
|---|---|
| Click the **Appointment** tag on the dentist card. | Only cards with that label. A chip at the top says "Only Appointment ✕". |
| Press **Esc**. | Everything is back. |
| Press **S** (with no card selected), choose **Labels**, add a label called `Club`. | It appears in the list of labels with a colour. |
| Close Settings. Press **Space**, type `meeting thu #club`, **Enter**. | The card has a **Club** tag. |

> [ ] as described  ·  What happened instead:

### 5. Five drags

Drag with the mouse or trackpad. A card should lift, follow the pointer, and the others should move apart to show
where it will land.

| Do this | You should see |
|---|---|
| a. Drag a card above another card in the **same day**. | It stays where you dropped it. |
| b. Drag a card from later in the week onto **today**. | It moves to today and now says "due" with its real day. |
| c. Drag something from Moodle that is **due today** onto **tomorrow**. | It shakes, goes back, and a line says it can't be planned later than it's due. |
| d. Drag the `call mom` card onto another day. | It moves, and its date changes (it's yours, so it can go anywhere). |
| e. Start dragging any card. Two boxes appear at the bottom. Drop it on **Completed**. | It goes to Completed. |

> [ ] a  [ ] b  [ ] c  [ ] d  [ ] e  ·  Did the dragging feel smooth?  ·  What happened instead:

### 6. Undo

| Do this | You should see |
|---|---|
| Right after drag **e**, click **Undo** in the message at the bottom (you have six seconds). | The card is back where it was. |
| Tick any card off. Then press **Ctrl+Z**. | It comes back. |

> [ ] as described  ·  What happened instead:

### 7. Motion: Full, then Off

| Do this | You should see |
|---|---|
| Press **S**, choose **Look**, set **Motion** to **Full**. In the Glass layout, tick a card off. | A ripple of light where you clicked, the tick is drawn, and the card flies to Completed. A soft light follows your pointer over the cards. |
| Set **Motion** to **Off**. Tick another card off. | Nothing moves. The card is simply in Completed. Everything still works. |
| Set it back to what you prefer. | |

> [ ] as described  ·  Was Full pleasant, too much, or too little?

### 8. A scan after sleep

| Do this | You should see |
|---|---|
| Put your computer to sleep for a minute or two. Wake it. Open Birdbrain. | Within a minute the dot in the corner starts breathing and says it is scanning. Then "Updated" with the time. |

> [ ] as described  ·  What happened instead:

### 9. A notification

| Do this | You should see |
|---|---|
| Press **S**, choose **Notifications**, press **Show me one**. | One notification near the clock, like "Due tonight: …", one line. |
| Windows only: close Birdbrain's window, then click the notification. | Birdbrain opens with that card outlined. |

> [ ] as described  ·  What happened instead:

### 10. Search and commands

| Do this | You should see |
|---|---|
| Press **Ctrl+K**. Type part of a card's title. | The list narrows as you type. |
| Press **Esc**. | Everything is back. |
| Press **Ctrl+K**, type `night`, press **Enter**. | The look switches to night. (`day` switches back.) |

> [ ] as described  ·  What happened instead:

### 11. Snooze

| Do this | You should see |
|---|---|
| Click a card that is **not** due today, so it has an outline. Press **S**, then **T**. | "Snoozed until tomorrow". The card is gone from the list. |
| Scroll down and open **Archived**. | The card is there: "Snoozed until tomorrow", with **Wake it now**. |
| Press **Wake it now**. | It is back on the list. |

> [ ] as described  ·  What happened instead:

### 12. An update

| Do this | You should see |
|---|---|
| Press **S**, choose **Updates**, press **Check for updates**. | Either "You have the newest version", or a newer one with an **Update and restart** button. |
| If there is a newer one, press **Update and restart**. | Birdbrain closes, and comes back by itself within a minute, with the new version shown under Updates. Your list is still there. |

> [ ] up to date  ·  [ ] updated and came back  ·  What happened instead:

### 13. Quit and reopen

| Do this | You should see |
|---|---|
| Close the window with its ✕ (the red button on a Mac). | The window goes. The bird icon is still in the tray (menu bar). |
| Click the bird icon (on a Mac you can also click Birdbrain in the Dock). | The window comes back. |
| Open the **⋯** menu, choose **Quit Birdbrain**, and confirm. | The window and the bird icon both go. |
| Start Birdbrain again. | Your list is as you left it, with no sign-in asked for. |

> [ ] as described  ·  What happened instead:

### 14. Telegram (optional, about 5 minutes extra)

Only if you use Telegram and want reminders on your phone.

| Do this | You should see |
|---|---|
| Press **S**, choose **Advanced**, open **Telegram**, and follow its four steps. | After you send the bot the code, the page moves to step 4 by itself. |
| Press **Send a test**. | A message on your phone with a button under it. |
| Text the bot `dentist tue 3pm`. | It answers "Added: Dentist …", and the card is on your computer's list. |
| Press **Turn off** twice. | Telegram is off. |

> [ ] as described  ·  [ ] skipped  ·  What happened instead:

### 15. Remove it

Before you do this, do "What to send back" below.

**Windows**

1. Press **S** › **Notifications** and untick **Start Birdbrain too**. Then **⋯** › **Quit Birdbrain**.
2. Delete the `Birdbrain` folder you extracted.
3. Press Win+R, type `%APPDATA%`, press Enter, and delete the `Birdbrain` folder there.
4. Press Win+R, type `%LOCALAPPDATA%`, press Enter, and delete `Birdbrain-update` and `ms-playwright` if they are
   there.

**Mac**

1. Press **S** › **Notifications** and untick **Start Birdbrain too**. Then **Birdbrain** menu › **Quit Birdbrain**.
2. Drag Birdbrain from Applications to the Trash.
3. In Finder choose **Go › Go to Folder…**, type `~/Library/Application Support`, and delete the `Birdbrain` folder.
4. The same way, open `~/Library/Caches` and delete `Birdbrain-update` and `ms-playwright` if they are there.

> [ ] removed without trouble  ·  What happened instead:

## What to send back

1. **This guide, with your boxes and notes filled in.** Copying the lines that start with `>` into a message is
   enough.
2. **A problem report**, even if nothing went wrong: open the **⋯** menu, choose **Report a problem**, write a line
   about anything odd, and press **Save the zip**. It lands in your Downloads folder. Birdbrain sends nothing by
   itself. Names, emails, course titles and addresses are taken out first, and the window shows you every line
   before you save, so you can check.
3. Which computer you used (for example "MacBook Air M2, macOS 15" or "Windows 11 laptop").

Send all three to whoever asked you to test.

## Known rough edges

- **Not signed yet.** That is why Windows and macOS both warn you the first time. It will be signed before a
  wider release.
- **Mac: no shortcut from anywhere yet.** Ctrl+Alt+Space is Windows only. On a Mac, quick write is **Space** in
  Birdbrain's window, or **Quick write** in the bird's menu.
- **Mac: clicking a notification doesn't open the card yet.** The notification still appears. macOS may show it as
  coming from "Script Editor".
- **Mac: the first notification may ask permission**, or may not appear until you allow notifications for
  "Script Editor" in System Settings › Notifications.
- **Mac: sign-in uses Chrome if you have it**, else Edge, else a browser Birdbrain downloads the first time (a
  short extra wait).
- **The first scan is slow** (a few minutes): it reads every course page once.
- **A wrong label can happen.** The rules that decide what is an exam are plain rules. If one is wrong, press **E**
  on the card and say what it is; it sticks.
- **Reminders only come while Birdbrain is running**, and the computer is awake.
